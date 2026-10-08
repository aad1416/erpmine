from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.Feature import Feature
from app.db.models.Message import Message
from app.prompts.chat_agent import build_run_input
from app.schemas.chats import Attachment
from app.services.admin_chat_agent_runner import (
    AdminChatAgentRunner,
    AdminChatToolContext,
)
from app.services.admin_chat_service import AdminChatService
from app.services.chat_agent_service import REPORTS_ENTITY_ID
from app.services.chat_sdk_model import supports_openai_agents_sdk
from app.services.database_query_tool_service import DatabaseQueryToolService
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
from app.services.files import FilesService
from app.services.memory_service import MemoryService
from app.services.persona_service import PersonaService
from app.services.reports_agent_runner import ReportsAgentRunner, ReportsToolContext


logger = logging.getLogger(__name__)


class AdminChatAgentService:
    """
    Orchestrates admin chat using OpenAI Agents SDK (tools for persona update,
    RAG, and DB) when the feature's persona model is OpenAI.
    Falls back to the legacy AdminChatService (3-step orchestration) for other providers.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        persona_service: PersonaService,
        legacy_admin_chat_service: AdminChatService,
        admin_chat_agent_runner: AdminChatAgentRunner,
        document_retrieval_tool_service: DocumentRetrievalToolService,
        database_query_tool_service: Optional[DatabaseQueryToolService] = None,
        db_session_factory: Optional[Callable[[], Session]] = None,
        reports_agent_runner: Optional[ReportsAgentRunner] = None,
        files_service: Optional[FilesService] = None,
    ):
        self.memory_service = memory_service
        self.persona_service = persona_service
        self.legacy_admin_chat_service = legacy_admin_chat_service
        self.admin_chat_agent_runner = admin_chat_agent_runner
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

    async def process_admin_message(
        self,
        chat_id: int,
        user_message: str,
        feature_id: int,
        admin_user_id: str,
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
                "Model %s uses legacy AdminChatService path (non-OpenAI Agents SDK)",
                persona.model_name,
            )
            return await self.legacy_admin_chat_service.process_admin_message(
                chat_id=chat_id,
                user_message=user_message,
                feature_id=feature_id,
                admin_user_id=admin_user_id,
            )

        history = self.memory_service.get_chat_history(chat_id)
        feature_record = self._resolve_feature(feature_id)
        # Use the store_id from the admin's JWT token; fall back to the feature record.
        store_id = user_store_id or (feature_record.store_id if feature_record else None)

        run_input = build_run_input(history, user_message)

        if feature_record is not None and feature_record.entity_id == REPORTS_ENTITY_ID:
            return await self._process_reports_admin_message(
                chat_id=chat_id,
                user_message=user_message,
                feature_id=feature_id,
                admin_user_id=admin_user_id,
                persona=persona,
                store_id=store_id,
                user_accesses=user_accesses or [],
                run_input=run_input,
            )

        tool_ctx = AdminChatToolContext(
            feature_id=feature_id,
            rag_top_k=5,
            store_id=store_id,
            admin_user_id=admin_user_id,
            document_retrieval_tool_service=self.document_retrieval_tool_service,
            database_query_tool_service=self.database_query_tool_service,
            persona_service=self.persona_service,
            user_accesses=user_accesses or [],
        )

        try:
            (
                assistant_response,
                sources,
                db_audit,
                persona_update_result,
                documents_tool_called,
            ) = await self.admin_chat_agent_runner.run(
                persona_prompt_text=persona.prompt_text,
                model_name=persona.model_name,
                run_input=run_input,
                ctx=tool_ctx,
                use_db_request=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("AdminChatAgentRunner failed")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to run admin agent: {exc}",
            ) from exc

        user_msg = await self._save_user_message(chat_id=chat_id, content=user_message)
        assistant_msg = await self._save_assistant_message(
            chat_id=chat_id,
            content=assistant_response,
        )

        return {
            "response": assistant_response,
            "intent": {
                "behavior_change": persona_update_result is not None,
                "rag_data": documents_tool_called,
            },
            "persona_update": persona_update_result,
            "sources": sources,
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "db_query_result": db_audit or None,
        }

    async def _process_reports_admin_message(
        self,
        *,
        chat_id: int,
        user_message: str,
        feature_id: int,
        admin_user_id: str,
        persona,
        store_id: Optional[str],
        user_accesses: List[str],
        run_input: str,
    ) -> Dict[str, Any]:
        """`reports` Feature dispatch (mirrors `ChatAgentService._process_reports_turn`):
        always runs all five report tools via ReportsAgentRunner."""
        if not self.reports_agent_runner:
            raise HTTPException(
                status_code=500,
                detail="Reports agent runner is not configured.",
            )

        tool_ctx = ReportsToolContext(
            feature_id=feature_id,
            store_id=store_id,
            user_id=admin_user_id,
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
            "intent": {"behavior_change": False, "rag_data": True},
            "persona_update": None,
            "sources": [],
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
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
