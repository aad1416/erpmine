"""
Run DB-RAG (retrieval -> SQL generation -> execute) for natural-language queries from a file.

Input file format: one query per line. Empty lines and lines starting with # or -- are ignored.

Usage:
    python scripts/db_rag_sql_batch.py --input scripts/queries.txt --log results.log
    python scripts/db_rag_sql_batch.py -i scripts/queries.txt -l results.log --concurrency 5

Optional: set DB_RAG_STORE_ID to a branch UUID for tenant-scoped SQL generation.
Branch-named queries (e.g. DSPM) should use stores.name in SQL when store_id is unset.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config.setting import settings
from app.dependencies.agent import get_agent_service
from app.dependencies.embeddings import get_embedding_service
from app.repositories.lyndom_db import LyndomDBRepository
from app.services.db_rag_query_service import DBRagQueryService
from app.services.db_rag_retrieval_service import DBRagRetrievalService
from app.vector_db.chroma_client import ChromaClient


def parse_queries_file(path: str) -> list[str]:
    """Read natural-language queries (one per line)."""
    queries: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("--"):
                continue
            queries.append(stripped)
    return queries


def _truncate_rows(rows: list[dict], max_rows: Optional[int]) -> tuple[list[dict], bool]:
    if max_rows is not None and max_rows > 0 and len(rows) > max_rows:
        return rows[:max_rows], True
    return rows, False


def _setup_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("db_rag_sql_batch")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


async def _process_query(
    user_query: str,
    retrieval_service: DBRagRetrievalService,
    query_service: DBRagQueryService,
    lyndom_repo: LyndomDBRepository,
    store_id: Optional[str],
    max_rows: Optional[int],
) -> dict:
    """Run retrieval -> SQL generation -> execution; return a log-friendly dict."""
    entry: dict = {
        "user_query": user_query,
        "selected_tables": [],
        "generated_queries": [],
        "status": "ok",
    }

    retrieval_result = await retrieval_service.get_relevant_schemas(
        user_message=user_query,
        feature_id=0,
    )
    selected_tables = retrieval_result.get("selected_tables", [])
    schema_markdown = retrieval_result.get("schema_markdown", "")

    entry["selected_tables"] = selected_tables

    if not schema_markdown.strip():
        entry["status"] = "no_schema"
        entry["error"] = "No schema context found"
        return entry

    generation_result = await query_service.generate_queries(
        user_message=user_query,
        schema_markdown=schema_markdown,
        store_id=store_id,
        selected_tables=selected_tables,
    )

    sql_queries = generation_result.get("queries", [])
    if not sql_queries:
        entry["status"] = "no_sql_generated"
        entry["error"] = "No SQL queries were generated"
        return entry

    had_failure = False
    for q in sql_queries:
        sql_entry: dict = {
            "intent": q.get("intent", "Database Query"),
            "sql": q.get("sql", ""),
            "is_valid": q.get("is_valid", False),
            "validation_error": q.get("validation_error"),
        }

        if not q.get("is_valid"):
            sql_entry["status"] = "invalid"
            had_failure = True
            entry["generated_queries"].append(sql_entry)
            continue

        try:
            rows = await asyncio.to_thread(
                lyndom_repo.execute_query, sql_entry["sql"]
            )
            display_rows, truncated = _truncate_rows(rows, max_rows)
            sql_entry["status"] = "ok"
            sql_entry["row_count"] = len(rows)
            sql_entry["rows"] = display_rows
            if truncated:
                sql_entry["truncated"] = True
                sql_entry["shown_rows"] = len(display_rows)
        except Exception as exc:
            sql_entry["status"] = "error"
            sql_entry["error"] = str(exc)
            had_failure = True

        entry["generated_queries"].append(sql_entry)

    if had_failure:
        entry["status"] = "partial_failure" if any(
            g.get("status") == "ok" for g in entry["generated_queries"]
        ) else "failed"

    return entry


def _is_failure(result: dict) -> bool:
    return result.get("status") != "ok"


def _print_result(index: int, total: int, user_query: str, result: dict) -> None:
    print(f"[{index}/{total}] {user_query}")
    if _is_failure(result):
        print(f"  {result.get('status')}: {result.get('error', '')}")
        return
    for g in result.get("generated_queries", []):
        if g.get("status") == "ok":
            print(f"  {g.get('intent')}: {g.get('row_count', 0)} row(s)")
        else:
            print(f"  {g.get('intent')}: {g.get('status')}")


async def _run_query_task(
    index: int,
    user_query: str,
    total: int,
    semaphore: asyncio.Semaphore,
    retrieval_service: DBRagRetrievalService,
    query_service: DBRagQueryService,
    lyndom_repo: LyndomDBRepository,
    store_id: Optional[str],
    max_rows: Optional[int],
) -> tuple[int, dict, bool]:
    async with semaphore:
        try:
            result = await _process_query(
                user_query=user_query,
                retrieval_service=retrieval_service,
                query_service=query_service,
                lyndom_repo=lyndom_repo,
                store_id=store_id,
                max_rows=max_rows,
            )
            return index, result, _is_failure(result)
        except Exception as exc:
            return (
                index,
                {
                    "user_query": user_query,
                    "status": "error",
                    "error": str(exc),
                },
                True,
            )


async def run_batch(
    input_path: str,
    log_path: str,
    store_id: Optional[str],
    concurrency: int,
) -> int:
    if not settings.lyndom_db_url:
        raise ValueError("lyndom_db_url is not configured in environment")

    user_queries = parse_queries_file(input_path)
    if not user_queries:
        print(f"No queries found in {input_path}")
        return 1

    logger = _setup_logger(log_path)
    max_rows = settings.DB_RAG_MAX_ROWS

    agent_service = get_agent_service()
    embedding_service = get_embedding_service()
    chroma_client = ChromaClient()

    retrieval_service = DBRagRetrievalService(
        chroma_client=chroma_client,
        embedding_service=embedding_service,
        agent_service=agent_service,
    )
    query_service = DBRagQueryService(agent_service=agent_service)
    lyndom_repo = LyndomDBRepository(settings.lyndom_db_url)

    started_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        json.dumps(
            {
                "event": "batch_start",
                "started_at": started_at,
                "input": os.path.abspath(input_path),
                "query_count": len(user_queries),
                "store_id": store_id,
                "concurrency": concurrency,
            },
            ensure_ascii=True,
        )
    )

    total = len(user_queries)
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        _run_query_task(
            index=index,
            user_query=user_query,
            total=total,
            semaphore=semaphore,
            retrieval_service=retrieval_service,
            query_service=query_service,
            lyndom_repo=lyndom_repo,
            store_id=store_id,
            max_rows=max_rows,
        )
        for index, user_query in enumerate(user_queries, start=1)
    ]
    outcomes = await asyncio.gather(*tasks)

    failures = 0
    for index, result, failed in sorted(outcomes, key=lambda item: item[0]):
        if failed:
            failures += 1
        _print_result(index, total, result["user_query"], result)
        log_entry = {
            "event": "query_result",
            "index": index,
            "total": total,
            **result,
        }
        logger.info(json.dumps(log_entry, default=str, ensure_ascii=True))

    finished_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "event": "batch_end",
        "finished_at": finished_at,
        "queries": len(user_queries),
        "failures": failures,
        "successes": len(user_queries) - failures,
    }
    logger.info(json.dumps(summary, ensure_ascii=True))
    print(f"\nDone. {summary['successes']} succeeded, {failures} failed.")
    print(f"Log written to {os.path.abspath(log_path)}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run DB-RAG for natural-language queries from a file and log results."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Text file with one natural-language query per line",
    )
    parser.add_argument(
        "--log",
        "-l",
        default="db_rag_sql_batch.log",
        help="Path to the log file (default: db_rag_sql_batch.log)",
    )
    parser.add_argument(
        "--concurrency",
        "-j",
        type=int,
        default=3,
        metavar="N",
        help="Max queries to run in parallel (default: 3, use 1 for sequential)",
    )
    args = parser.parse_args()

    if args.concurrency < 1:
        print("concurrency must be at least 1")
        sys.exit(1)

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    log_path = os.path.abspath(args.log)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    store_id = os.getenv("DB_RAG_STORE_ID")
    if store_id:
        print(f"Using store_id from DB_RAG_STORE_ID={store_id}")
    print(f"Concurrency: {args.concurrency}\n")

    try:
        exit_code = asyncio.run(
            run_batch(input_path, log_path, store_id, args.concurrency)
        )
    except Exception as exc:
        print(f"Batch failed: {exc}")
        sys.exit(1)
    else:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
