import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, TypedDict
from types import SimpleNamespace

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config.setting import settings
from app.services.agent_service import AgentService
from app.prompts.db_rag import (
    get_sql_generation_prompt,
    get_db_rag_query_gen_persona,
)
from app.utils.db_schema_markdown import parse_allowed_schema, validate_sql_identifiers

logger = logging.getLogger(__name__)


class GeneratedQuery(TypedDict):
    intent: str
    sql: str
    is_valid: bool
    validation_error: Optional[str]


class SqlGenerationResult(TypedDict):
    queries: List[GeneratedQuery]
    has_errors: bool
    tables_used: List[str]


class DBRagQueryService:
    """
    Service responsible ONLY for generating SQL queries and validating them statically.
    Encapsulates validation blocklist and LLM communication.
    """

    # Static validation blocklist
    BLOCKED_KEYWORDS = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "EXEC",
        "EXECUTE",
    }

    def __init__(self, agent_service: AgentService):
        self.agent_service = agent_service

    async def generate_queries(
        self,
        user_message: str,
        schema_markdown: str,
        store_id: Optional[str] = None,
        selected_tables: List[str] = None,
        accessible_tables: Optional[Set[str]] = None,
        mgmt_tables: Optional[Set[str]] = None,
    ) -> SqlGenerationResult:
        """
        Takes user input and schema documentation, asks the LLM to generate one or more SQL queries,
        and returns statically validated queries.

        Args:
            user_message: Raw user query
            schema_markdown: The available DB schema context
            store_id: The active store ID for scoping checks
            selected_tables: Optional list of table names identified by retrieval

        Returns:
            A SqlGenerationResult holding generated, validated queries.
        """
        # Step 1: SQL Generation via prompt
        prompt = get_sql_generation_prompt(
            user_message, schema_markdown, store_id,
            accessible_tables=accessible_tables,
            mgmt_tables=mgmt_tables,
        )
        persona = SimpleNamespace(**get_db_rag_query_gen_persona())

        try:
            response_text = await self.agent_service.generate_async(
                prompt=prompt,
                persona=persona,
                temperature=1,
            )

            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            parsed = json.loads(cleaned.strip())
            queries = parsed.get("queries", [])
        except Exception as e:
            logger.error(f"Failed to generate or parse SQL JSON: {e}")
            return {
                "queries": [
                    {
                        "intent": "Parsing LLM generation",
                        "sql": "N/A",
                        "is_valid": False,
                        "validation_error": f"LLM parsing failed: {e}",
                    }
                ],
                "has_errors": True,
                "tables_used": selected_tables or [],
            }

        # Step 2: Static Validation Loop
        final_queries: List[GeneratedQuery] = []
        has_errors = False

        for q_obj in queries:
            intent = q_obj.get("intent", "Database Query")
            sql = q_obj.get("sql", "").strip()

            if not sql:
                final_queries.append(
                    {
                        "intent": intent,
                        "sql": "",
                        "is_valid": False,
                        "validation_error": "Empty SQL statement generated",
                    }
                )
                has_errors = True
                continue

            # Cleanup accidental LLM fences inside the text
            if sql.startswith("```sql"):
                sql = sql[6:]
            elif sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()

            # Static safety + schema grounding check
            try:
                self._validate_sql(sql)
                allowed = parse_allowed_schema(schema_markdown)
                if schema_markdown.strip() and not allowed:
                    logger.warning(
                        "Schema markdown provided but no ## Columns tables parsed; "
                        "skipping column whitelist validation"
                    )
                validate_sql_identifiers(sql, allowed)
                final_queries.append(
                    {
                        "intent": intent,
                        "sql": sql,
                        "is_valid": True,
                        "validation_error": None,
                    }
                )
            except ValueError as ve:
                has_errors = True
                logger.warning(f"Static SQL Validation Failed: {ve}\nSQL: {sql}")
                final_queries.append(
                    {
                        "intent": intent,
                        "sql": sql,
                        "is_valid": False,
                        "validation_error": str(ve),
                    }
                )

        return {
            "queries": final_queries,
            "has_errors": has_errors,
            "tables_used": selected_tables or [],
        }

    def _validate_sql(self, sql: str) -> None:
        """
        Static validation to reject unsafe SQL statements.
        """
        if "--" in sql:
            raise ValueError(
                "Unsafe SQL rejected: comment injection ('--') is not allowed"
            )
        if "/*" in sql:
            raise ValueError(
                "Unsafe SQL rejected: block comment injection ('/*') is not allowed"
            )

        if ";" in sql[:-1]:
            raise ValueError(
                "Unsafe SQL rejected: multi-statement queries (';') are not allowed"
            )

        if re.search(r"\$\d+", sql):
            raise ValueError(
                "Positional bind placeholders ($1, $2, …) are not allowed. "
                "Use literal store_id values or JOIN stores ON stores.name for branch filters."
            )

        upper_sql = sql.upper()
        for kw in self.BLOCKED_KEYWORDS:
            if re.search(r"\b" + kw + r"\b", upper_sql):
                raise ValueError(
                    f"Unsafe SQL rejected: keyword '{kw}' is not allowed (read-only queries only)"
                )
