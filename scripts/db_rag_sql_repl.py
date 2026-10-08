import asyncio
import json
import os
import sys
from typing import Optional

# Add project root to path so we can import app
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


def _print_rows(rows: list[dict], max_rows: Optional[int]) -> None:
    if max_rows is not None and max_rows > 0:
        display_rows = rows[:max_rows]
    else:
        display_rows = rows

    print(json.dumps(display_rows, indent=2, default=str, ensure_ascii=True))

    if len(display_rows) < len(rows):
        print(f"... showing {len(display_rows)} of {len(rows)} row(s)")


async def _handle_query(
    user_query: str,
    retrieval_service: DBRagRetrievalService,
    query_service: DBRagQueryService,
    lyndom_repo: LyndomDBRepository,
    store_id: Optional[str],
) -> None:
    retrieval_result = await retrieval_service.get_relevant_schemas(
        user_message=user_query,
        feature_id=0,
    )
    selected_tables = retrieval_result.get("selected_tables", [])
    schema_markdown = retrieval_result.get("schema_markdown", "")


    generation_result = await query_service.generate_queries(
        user_message=user_query,
        schema_markdown=schema_markdown,
        store_id=store_id,
        selected_tables=selected_tables,
    )

    print("\n[Step 3] SQL Generation + Execution")
    queries = generation_result.get("queries", [])
    if not queries:
        print("No SQL queries were generated.")
        return

    for index, q in enumerate(queries, start=1):
        print(f"\nQuery {index}: {q.get('intent', 'Database Query')}")
        sql = q.get("sql", "")
        is_valid = q.get("is_valid", False)
        validation_error = q.get("validation_error")

        print("SQL:")
        print(sql or "N/A")

        if not is_valid:
            print(f"Skipped (invalid): {validation_error or 'Unknown validation error'}")
            continue

        try:
            rows = lyndom_repo.execute_query(sql)
            print(f"Executed successfully. Returned {len(rows)} row(s).")
            _print_rows(rows, settings.DB_RAG_MAX_ROWS)
        except Exception as exc:
            print(f"Execution failed: {exc}")


async def main() -> None:
    if not settings.lyndom_db_url:
        raise ValueError("lyndom_db_url is not configured in environment")

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

    store_id = os.getenv("DB_RAG_STORE_ID")

    print("DB-RAG SQL REPL")
    print("Flow: Retrieval -> SQL Generation -> Execute on Lyndom DB")
    print("Type 'exit' or 'quit' to stop.\n")
    if store_id:
        print(f"Using store_id from DB_RAG_STORE_ID={store_id}\n")

    while True:
        user_query = input("query> ").strip()
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        try:
            await _handle_query(
                user_query=user_query,
                retrieval_service=retrieval_service,
                query_service=query_service,
                lyndom_repo=lyndom_repo,
                store_id=store_id,
            )
        except KeyboardInterrupt:
            print("\nInterrupted. Type 'exit' to quit.")
        except Exception as exc:
            print(f"Failed to process query: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
