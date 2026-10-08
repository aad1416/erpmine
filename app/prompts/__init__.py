"""
Prompt Templates Module

This module contains all prompt templates used throughout the application.
Prompts are organized by feature/functionality for easy maintenance and testing.
"""

from app.prompts.admin_chat import (
    get_intent_detection_prompt,
    get_persona_update_prompt,
    get_response_synthesis_prompt,
    get_intent_detection_persona,
    get_synthesis_persona,
    INTENT_DETECTION_MODEL,
    INTENT_DETECTION_SYSTEM_PROMPT,
    SYNTHESIS_MODEL,
    SYNTHESIS_SYSTEM_PROMPT,
)
from app.prompts.db_rag import (
    get_query_expansion_prompt,
    get_db_rag_intent_prompt,
    get_table_selection_prompt,
    get_sql_generation_prompt,
    get_db_rag_query_expansion_persona,
    get_db_rag_intent_persona,
    get_db_rag_table_selection_persona,
    get_db_rag_query_gen_persona,
    DB_RAG_QUERY_EXPANSION_SYSTEM_PROMPT,
    DB_RAG_INTENT_SYSTEM_PROMPT,
    DB_RAG_TABLE_SELECTION_SYSTEM_PROMPT,
    DB_RAG_SQL_GENERATION_SYSTEM_PROMPT,
)

__all__ = [
    # Admin Chat Prompts
    "get_intent_detection_prompt",
    "get_persona_update_prompt",
    "get_response_synthesis_prompt",
    "get_intent_detection_persona",
    "get_synthesis_persona",
    # Admin Chat Constants
    "INTENT_DETECTION_MODEL",
    "INTENT_DETECTION_SYSTEM_PROMPT",
    "SYNTHESIS_MODEL",
    "SYNTHESIS_SYSTEM_PROMPT",
    # DB-RAG Prompts
    "get_query_expansion_prompt",
    "get_db_rag_intent_prompt",
    "get_table_selection_prompt",
    "get_sql_generation_prompt",
    # DB-RAG Persona Factories
    "get_db_rag_query_expansion_persona",
    "get_db_rag_intent_persona",
    "get_db_rag_table_selection_persona",
    "get_db_rag_query_gen_persona",
    # DB-RAG Constants
    "DB_RAG_QUERY_EXPANSION_SYSTEM_PROMPT",
    "DB_RAG_INTENT_SYSTEM_PROMPT",
    "DB_RAG_TABLE_SELECTION_SYSTEM_PROMPT",
    "DB_RAG_SQL_GENERATION_SYSTEM_PROMPT",
]

