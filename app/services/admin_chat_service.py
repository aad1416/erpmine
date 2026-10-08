import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from types import SimpleNamespace
from app.services.memory_service import MemoryService
from app.services.persona_service import PersonaService
from app.services.rag_service import RAGService
from app.services.agent_service import AgentService
from app.config.setting import settings
from app.prompts import (
    get_intent_detection_prompt,
    get_persona_update_prompt,
    get_response_synthesis_prompt,
    get_intent_detection_persona,
    get_synthesis_persona,
)
from app.db.models.Message import Message
from app.db.models.Persona import Persona
from app.schemas.personas import PersonaUpdate
from fastapi import HTTPException


class AdminChatService:
    """
    Admin Chat Service - Multi-Agent Orchestration Layer

    Responsibilities:
    - Orchestrate 3-step admin chat flow with multiple LLM calls
    - Step 1: Intent Detection (detect behavior_change and rag_data needs)
    - Step 2: Persona Update (conditional, if behavior_change=true)
    - Step 3: Response Synthesis (combine all results into final response)
    - Handle message persistence
    - Return comprehensive metadata

    Use Case:
    - Admins can modify feature personas through natural language conversation
    - Admins can query data while simultaneously updating persona
    - All actions are tracked in chat history
    """

    def __init__(
        self,
        memory_service: MemoryService,
        persona_service: PersonaService,
        rag_service: RAGService,
        agent_service: AgentService,
    ):
        """
        Initialize Admin Chat Service with injected dependencies

        Args:
            memory_service: Service for chat history management
            persona_service: Service for persona retrieval and updates
            rag_service: Service for data retrieval (RAG)
            agent_service: Service for LLM generation
        """
        self.memory_service = memory_service
        self.persona_service = persona_service
        self.rag_service = rag_service
        self.agent_service = agent_service

    async def process_admin_message(
        self, chat_id: int, user_message: str, feature_id: int, admin_user_id: str
    ) -> Dict[str, Any]:
        """
        Process an admin chat message with multi-agent orchestration

        Flow (3 LLM Calls):
        1. Intent Detection: Detect if user wants behavior change and/or data
        2. Persona Update: Generate and save new persona (if behavior_change=true)
        3. Response Synthesis: Combine all results into natural language response

        Args:
            chat_id: ID of the chat
            user_message: Admin's message content
            feature_id: Feature ID for context/persona
            admin_user_id: Admin user ID for tracking updates

        Returns:
            Dict containing:
            {
                "response": "Synthesized response",
                "intent": {"behavior_change": bool, "rag_data": bool},
                "persona_update": {"updated": bool, "old_prompt": str, "new_prompt": str} or None,
                "sources": [...] (if RAG used),
                "user_message_id": int,
                "assistant_message_id": int
            }

        Raises:
            HTTPException: If processing fails
        """
        try:
            # Validate message
            if not user_message or not user_message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty")

            # Get current persona for feature (needed for synthesis)
            current_persona = self.persona_service.get_persona_for_feature(feature_id)
            if not current_persona:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona not found for feature {feature_id}",
                )

            # Load prior messages so admin chat maintains conversation context
            history = self.memory_service.get_chat_history(chat_id)

            # ===== STEP 1: INTENT DETECTION =====
            intent_result = await self._detect_intent(user_message, history=history)
            behavior_change = intent_result.get("behavior_change", False)
            rag_data = intent_result.get("rag_data", False)

            # ===== STEP 2: PERSONA UPDATE (Conditional) =====
            persona_update_result = None
            if behavior_change:
                persona_update_result = await self._update_persona(
                    feature_id=feature_id,
                    user_request=user_message,
                    admin_user_id=admin_user_id,
                    history=history,
                )

            # ===== STEP 3: RAG DATA RETRIEVAL (Conditional) =====
            rag_result = None
            sources = []
            if rag_data:
                rag_result = await self.rag_service.retrieve_async(
                    query=user_message,
                    feature_id=feature_id,
                    top_k=5,
                    similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
                )
                sources = rag_result.get("sources", [])

            # ===== STEP 4: RESPONSE SYNTHESIS =====
            synthesized_response = await self._synthesize_response(
                intent=intent_result,
                persona_update=persona_update_result,
                rag_data=rag_result.get("formatted", "") if rag_result else None,
                user_query=user_message,
                current_persona_prompt=current_persona.prompt_text,
                history=history,
            )

            # ===== STEP 5: SAVE MESSAGES =====
            user_msg = await self._save_user_message(chat_id, user_message)
            assistant_msg = await self._save_assistant_message(
                chat_id, synthesized_response
            )

            # ===== STEP 6: RETURN RESPONSE WITH METADATA =====
            return {
                "response": synthesized_response,
                "intent": intent_result,
                "persona_update": persona_update_result,
                "sources": sources,
                "user_message_id": user_msg.id,
                "assistant_message_id": assistant_msg.id,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to process admin message: {str(e)}"
            )

    async def _detect_intent(
        self, user_message: str, history: Optional[List] = None
    ) -> Dict[str, bool]:
        """
        Step 1: Detect user intent using LLM (GPT-3.5-turbo for speed)

        Args:
            user_message: User's message content

        Returns:
            Dict with {"behavior_change": bool, "rag_data": bool}
        """
        # Get intent detection prompt from prompts module
        intent_prompt = get_intent_detection_prompt(user_message, history=history)

        # Get persona configuration for intent detection
        # Create a simple temporary persona object (not a DB model)
        persona_config = get_intent_detection_persona()
        temp_persona = SimpleNamespace(
            prompt_text=persona_config["prompt_text"],
            model_name=persona_config["model_name"],
        )

        try:
            intent_response = await self.agent_service.generate_async(
                prompt=intent_prompt, persona=temp_persona
            )

            # Parse JSON response
            # Clean response (remove markdown code blocks if present)
            intent_response = intent_response.strip()
            if intent_response.startswith("```"):
                # Remove markdown code blocks
                lines = intent_response.split("\n")
                intent_response = "\n".join(
                    [l for l in lines if not l.startswith("```")]
                )
                intent_response = intent_response.strip()

            intent_json = json.loads(intent_response)

            return {
                "behavior_change": bool(intent_json.get("behavior_change", False)),
                "rag_data": bool(intent_json.get("rag_data", False)),
            }
        except json.JSONDecodeError as e:
            # Fallback: assume general conversation
            return {"behavior_change": False, "rag_data": False}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Intent detection failed: {str(e)}"
            )

    async def _update_persona(
        self,
        feature_id: int,
        user_request: str,
        admin_user_id: str,
        history: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        Step 2: Generate new persona prompt and save to database

        Args:
            feature_id: Feature ID
            user_request: Admin's request for persona change
            admin_user_id: Admin user ID for tracking

        Returns:
            Dict with {"updated": bool, "old_prompt": str, "new_prompt": str}
        """
        try:
            # Get current persona
            current_persona = self.persona_service.get_persona_for_feature(feature_id)
            if not current_persona:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona not found for feature {feature_id}",
                )

            old_prompt = current_persona.prompt_text

            # Get persona update prompt from prompts module
            update_prompt = get_persona_update_prompt(
                old_prompt, user_request, history=history
            )

            # Use feature's model for persona generation
            # Create a simple temporary persona object (not a DB model)
            temp_persona = SimpleNamespace(
                prompt_text="You are a helpful assistant.",
                model_name=current_persona.model_name,  # Use same model as feature
            )

            new_prompt = await self.agent_service.generate_async(
                prompt=update_prompt, persona=temp_persona
            )

            # Clean new prompt (remove quotes if wrapped)
            new_prompt = new_prompt.strip()
            if new_prompt.startswith('"""') and new_prompt.endswith('"""'):
                new_prompt = new_prompt[3:-3].strip()
            elif new_prompt.startswith('"') and new_prompt.endswith('"'):
                new_prompt = new_prompt[1:-1].strip()

            # Update persona in database using PersonaUpdate schema
            persona_update = PersonaUpdate(
                prompt_text=new_prompt,
                model_name=current_persona.model_name,
                updated_by_user_id=admin_user_id,
            )

            updated_persona = self.persona_service.update_persona(
                persona_id=current_persona.id, persona_update=persona_update
            )

            return {"updated": True, "old_prompt": old_prompt, "new_prompt": new_prompt}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Persona update failed: {str(e)}"
            )

    async def _synthesize_response(
        self,
        intent: Dict[str, bool],
        persona_update: Optional[Dict[str, Any]],
        rag_data: Optional[str],
        user_query: str,
        current_persona_prompt: str,
        history: Optional[List] = None,
    ) -> str:
        """
        Step 3: Synthesize final response combining all results

        Always uses the current persona (or new one if updated) to respond,
        ensuring consistent tone and behavior aligned with the feature's persona.

        Args:
            intent: Intent detection result
            persona_update: Persona update result (if any)
            rag_data: RAG retrieved data (if any)
            user_query: Original user query
            current_persona_prompt: Current persona prompt for the feature

        Returns:
            Natural language synthesized response
        """
        # Get synthesis prompt from prompts module
        synthesis_prompt = get_response_synthesis_prompt(
            intent=intent,
            persona_updated=(
                persona_update.get("updated", False) if persona_update else False
            ),
            old_prompt=persona_update.get("old_prompt") if persona_update else None,
            new_prompt=persona_update.get("new_prompt") if persona_update else None,
            rag_data=rag_data,
            user_query=user_query,
            current_persona_prompt=current_persona_prompt,
            history=history,
        )

        # Always use a minimal system prompt - the persona is in the synthesis_prompt itself
        # This allows the prompt to properly use either the current or new persona
        temp_persona = SimpleNamespace(
            prompt_text="You are a helpful assistant.",
            model_name="gpt-3.5-turbo",
        )

        synthesized_response = await self.agent_service.generate_async(
            prompt=synthesis_prompt, persona=temp_persona
        )

        return synthesized_response

    async def _save_user_message(self, chat_id: int, content: str) -> Message:
        """Save user message to database"""
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
                status_code=500, detail=f"Failed to save user message: {str(e)}"
            )

    async def _save_assistant_message(self, chat_id: int, content: str) -> Message:
        """Save assistant message to database"""
        try:
            message = Message(
                chat_id=chat_id,
                role="assistant",
                content=content,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            return self.memory_service.save_message(chat_id, message)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save assistant message: {str(e)}"
            )
