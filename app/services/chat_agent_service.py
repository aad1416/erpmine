from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import tiktoken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.models.Feature import Feature
from app.db.models.Message import Message
from app.prompts.chat_agent import build_agent_instructions, build_run_input
from app.schemas.chats import Attachment
from app.services.chat_agent_runner import ChatAgentRunner, ChatToolContext
from app.services.chat_sdk_model import supports_openai_agents_sdk
from app.services.chat_service import ChatService
from app.services.database_query_tool_service import DatabaseQueryToolService
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
from app.services.files import FilesService
from app.services.memory_service import MemoryService
from app.services.persona_service import PersonaService
from app.services.reports_agent_runner import ReportsAgentRunner, ReportsToolContext
from app.utils.eval_logger import eval_logger

# Feature.entity_id slug that routes chat traffic to ReportsAgentRunner instead of
# ChatAgentRunner (map decision D2/D8).
REPORTS_ENTITY_ID = "reports"


logger = logging.getLogger(__name__)


class ChatAgentService:
    """
    Orchestrates chat using OpenAI Agents SDK (tools for RAG + DB) when persona model is OpenAI.
    Falls back to legacy ChatService (LangChain) for other providers.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        persona_service: PersonaService,
        legacy_chat_service: ChatService,
        chat_agent_runner: ChatAgentRunner,
        document_retrieval_tool_service: DocumentRetrievalToolService,
        database_query_tool_service: Optional[DatabaseQueryToolService] = None,
        db_session_factory: Optional[Callable[[], Session]] = None,
        reports_agent_runner: Optional[ReportsAgentRunner] = None,
        files_service: Optional[FilesService] = None,
    ):
        self.memory_service = memory_service
        self.persona_service = persona_service
        self.legacy_chat_service = legacy_chat_service
        self.chat_agent_runner = chat_agent_runner
        self.document_retrieval_tool_service = document_retrieval_tool_service
        self.database_query_tool_service = database_query_tool_service
        self.db_session_factory = db_session_factory
        self.reports_agent_runner = reports_agent_runner
        self.files_service = files_service

    def _resolve_feature(self, feature_id: int) -> Optional[Feature]:
        if not self.db_session_factory:
            return None
        db_session = self.db_session_factory()
        try:
            return db_session.query(Feature).filter(Feature.id == feature_id).first()
        finally:
            db_session.close()

    def _resolve_store_id(self, feature_id: int) -> Optional[str]:
        feature_record = self._resolve_feature(feature_id)
        return feature_record.store_id if feature_record else None

    async def process_message(
        self,
        chat_id: int,
        user_message: str,
        feature_id: int,
        user_id: str,
        use_rag: bool = True,
        use_db: bool = False,
        rag_top_k: int = 5,
        user_accesses: List[str] = None,
        user_store_id: str = "",
    ) -> Dict[str, Any]:
        if not user_message or not user_message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        persona = self.persona_service.get_persona_for_feature(feature_id)
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"Persona not found for feature {feature_id}",
            )

        if not supports_openai_agents_sdk(persona.model_name):
            logger.info(
                "Model %s uses legacy ChatService path (non-OpenAI Agents SDK)",
                persona.model_name,
            )
            return await self.legacy_chat_service.process_message(
                chat_id=chat_id,
                user_message=user_message,
                feature_id=feature_id,
                user_id=user_id,
                use_rag=use_rag,
                rag_top_k=rag_top_k,
            )

        start_time = time.time()
        history = self.memory_service.get_chat_history(chat_id)
        feature_record = self._resolve_feature(feature_id)
        # Use the store_id from the user's JWT token; fall back to the feature record.
        store_id = user_store_id or (feature_record.store_id if feature_record else None)

        run_input = build_run_input(history, user_message)

        if feature_record is not None and feature_record.entity_id == REPORTS_ENTITY_ID:
            return await self._process_reports_turn(
                chat_id=chat_id,
                user_message=user_message,
                feature_id=feature_id,
                user_id=user_id,
                persona=persona,
                store_id=store_id,
                user_accesses=user_accesses or [],
                run_input=run_input,
            )

        instructions = build_agent_instructions(
            persona.prompt_text, use_rag=use_rag, use_db=use_db and settings.DB_RAG_ENABLED
        )

        tool_ctx = ChatToolContext(
            feature_id=feature_id,
            rag_top_k=rag_top_k,
            store_id=store_id,
            document_retrieval_tool_service=self.document_retrieval_tool_service,
            database_query_tool_service=self.database_query_tool_service,
            user_accesses=user_accesses or [],
        )

        try:
            assistant_response, sources, db_audit = await self.chat_agent_runner.run(
                persona_prompt_text=persona.prompt_text,
                model_name=persona.model_name,
                run_input=run_input,
                ctx=tool_ctx,
                use_rag=use_rag,
                use_db_request=use_db,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ChatAgentRunner failed")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to run agent: {exc}",
            ) from exc

        user_msg = await self._save_user_message(chat_id=chat_id, content=user_message)
        assistant_msg = await self._save_assistant_message(
            chat_id=chat_id,
            content=assistant_response,
        )

        duration_seconds = time.time() - start_time
        input_tokens = 0
        output_tokens = 0
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            full_input = instructions + "\n" + run_input
            input_tokens = len(enc.encode(full_input))
            output_tokens = len(enc.encode(assistant_response))
        except Exception:
            pass

        file_id = "unknown"
        file_name = "unknown"
        retrieved_chunk_refs: List[str] = []
        if sources:
            file_id = str(
                sources[0].get("file_id") or sources[0].get("document_id") or "unknown"
            )
            file_name = str(sources[0].get("filename", "unknown"))
            for s in sources:
                doc_id = s.get("document_id", "?")
                c_idx = s.get("chunk_index", "?")
                retrieved_chunk_refs.append(f"{doc_id}-chunk{c_idx}")

        try:
            eval_logger.log_chat_interaction(
                chat_id=chat_id,
                file_id=file_id,
                file_name=file_name,
                question=user_message,
                answer=assistant_response,
                retrieved_chunks=retrieved_chunk_refs,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_seconds=duration_seconds,
            )
        except Exception as e:
            print(f"[EvalLogger error]: {e}")

        return {
            "response": assistant_response,
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "sources": sources if use_rag else [],
            "persona_model": persona.model_name,
            "db_query_result": db_audit if use_db else None,
        }

    async def _process_reports_turn(
        self,
        *,
        chat_id: int,
        user_message: str,
        feature_id: int,
        user_id: str,
        persona,
        store_id: Optional[str],
        user_accesses: List[str],
        run_input: str,
    ) -> Dict[str, Any]:
        """`reports` Feature dispatch (map decision D2/D8): always runs all five
        report tools via ReportsAgentRunner, ignoring use_rag/use_db."""
        if not self.reports_agent_runner:
            raise HTTPException(
                status_code=500,
                detail="Reports agent runner is not configured.",
            )

        tool_ctx = ReportsToolContext(
            feature_id=feature_id,
            store_id=store_id,
            user_id=user_id,
            user_accesses=user_accesses,
            database_query_tool_service=self.database_query_tool_service,
            files_service=self.files_service,
        )

        try:
            assistant_response, attachments, db_audit = await self.reports_agent_runner.run(
                persona_prompt_text=persona.prompt_text,
                model_name=persona.model_name,
                run_input=run_input,
                ctx=tool_ctx,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ReportsAgentRunner failed")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to run reports agent: {exc}",
            ) from exc

        user_msg = await self._save_user_message(chat_id=chat_id, content=user_message)
        assistant_msg = await self._save_assistant_message(
            chat_id=chat_id,
            content=assistant_response,
            attachments=attachments,
        )

        return {
            "response": assistant_response,
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "sources": [],
            "persona_model": persona.model_name,
            "db_query_result": db_audit,
            "attachments": attachments,
        }

    async def _save_user_message(self, chat_id: int, content: str) -> Message:
        try:
            message = Message(
                chat_id=chat_id,
                role="user",
                content=content,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            return self.memory_service.save_message(chat_id, message)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save user message: {str(e)}",
            ) from e

    async def _save_assistant_message(
        self,
        chat_id: int,
        content: str,
        attachments: Optional[List[Attachment]] = None,
    ) -> Message:
        try:
            message = Message(
                chat_id=chat_id,
                role="assistant",
                content=content,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                attachments=[a.model_dump(mode="json") for a in attachments]
                if attachments
                else None,
            )
            return self.memory_service.save_message(chat_id, message)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save assistant message: {str(e)}",
            ) from e

    def process_message_sync(
        self,
        chat_id: int,
        user_message: str,
        feature_id: int,
        user_id: str,
        use_rag: bool = True,
        use_db: bool = False,
        rag_top_k: int = 5,
        user_accesses: List[str] = None,
        user_store_id: str = "",
    ) -> Dict[str, Any]:
        return asyncio.run(
            self.process_message(
                chat_id=chat_id,
                user_message=user_message,
                feature_id=feature_id,
                user_id=user_id,
                use_rag=use_rag,
                use_db=use_db,
                rag_top_k=rag_top_k,
                user_accesses=user_accesses,
                user_store_id=user_store_id,
            )
        )
