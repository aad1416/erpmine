from __future__ import annotations
from typing import Optional, Dict, Any, Callable, List, TYPE_CHECKING
from sqlalchemy import text
if TYPE_CHECKING:
    from app.services.db_rag_retrieval_service import DBRagRetrievalService
    from app.services.db_rag_query_service import DBRagQueryService
from sqlalchemy.orm import Session
from datetime import datetime
import time
import tiktoken
from app.utils.eval_logger import eval_logger
from app.services.memory_service import MemoryService
from app.services.persona_service import PersonaService
from app.services.rag_service import RAGService
from app.services.agent_service import AgentService
from app.config.setting import settings
from app.db.models.Message import Message
from app.db.models.Persona import Persona
from fastapi import HTTPException


class ChatService:
    """
    Chat Service - Orchestration Layer
    
    Responsibilities:
    - Orchestrate the entire chat message processing flow
    - Coordinate MemoryService, PersonaService, RAGService, and AgentService
    - Build prompts from chat history + RAG data + user query (NO persona prompt)
    - Handle message persistence
    - Return responses to routes
    
    What ChatService Does NOT Do:
    - Generate responses (AgentService does this)
    - Apply persona prompts (AgentService does this)
    - Retrieve data (RAGService does this)
    """
    
    def __init__(
        self,
        memory_service: MemoryService,
        persona_service: PersonaService,
        rag_service: RAGService,
        agent_service: AgentService,
        db_rag_retrieval_service: Optional[DBRagRetrievalService] = None,
        db_rag_query_service: Optional[DBRagQueryService] = None,
        db_session_factory: Optional[Callable[[], Session]] = None,
    ):
        """
        Initialize Chat Service with injected dependencies
        
        Args:
            memory_service: Service for chat history management
            persona_service: Service for persona retrieval
            rag_service: Service for data retrieval (RAG)
            agent_service: Service for LLM generation
            db_rag_intent_service: Optional service for routing
            db_rag_retrieval_service: Optional service for fetching DB schema
            db_rag_query_service: Optional service for executing generated DB queries
            db_session_factory: Factory function returning DB Session
        """
        self.memory_service = memory_service
        self.persona_service = persona_service
        self.rag_service = rag_service
        self.agent_service = agent_service
        self.db_rag_retrieval_service = db_rag_retrieval_service
        self.db_rag_query_service = db_rag_query_service
        self.db_session_factory = db_session_factory
    
    async def process_message(
        self,
        chat_id: int,
        user_message: str,
        feature_id: int,
        user_id: str,
        use_rag: bool = True,
        rag_top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Process a chat message - Main orchestration method
        
        Flow:
        1. Validate chat exists and belongs to user
        2. Retrieve chat history from MemoryService
        3. Retrieve persona from PersonaService
        4. Retrieve relevant data from RAGService (if enabled)
        5. Build prompt (history + RAG data + query) - NO persona prompt
        6. Pass to AgentService for generation
        7. Save user message and assistant response
        8. Return response
        
        Args:
            chat_id: ID of the chat
            user_message: User's message content
            feature_id: Feature ID for context/persona
            user_id: User ID for validation
            use_rag: Whether to use RAG for retrieval (default: True)
            rag_top_k: Number of documents to retrieve (default: 5)
        
        Returns:
            Dict containing:
            {
                "response": "Assistant's response",
                "user_message_id": int,
                "assistant_message_id": int,
                "sources": [...] (if RAG used)
            }
        
        Raises:
            HTTPException: If chat not found, persona not found, or processing fails
        """
        try:
            start_time = time.time()
            
            # Step 1: Validate message
            if not user_message or not user_message.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Message cannot be empty"
                )
            
            # Step 2: Get chat history
            history = self.memory_service.get_chat_history(chat_id)
            
            # Step 3: Get persona for feature
            persona = self.persona_service.get_persona_for_feature(feature_id)
            if not persona:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona not found for feature {feature_id}"
                )
            
            # Step 4: Intent Detection (Removed)
            # Logic proceeds to process RAG queries directly without explicit classification.

            # Step 5: Retrieve relevant data from RAG (if enabled and applicable)
            rag_data = None
            sources = []
            if use_rag:
                rag_result = await self.rag_service.retrieve_async(
                    query=user_message,
                    feature_id=feature_id,
                    top_k=rag_top_k,
                    similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
                )
                rag_data = rag_result.get("formatted", "")
                sources = rag_result.get("sources", [])

            # Step 6: [NEW] DB-RAG retrieval + query (if applicable)
            db_rag_data = None
            db_query_result = None
            if settings.DB_RAG_ENABLED:
                if self.db_rag_retrieval_service and self.db_rag_query_service and self.db_session_factory:
                    schema_result = await self.db_rag_retrieval_service.get_relevant_schemas(
                        user_message=user_message,
                        feature_id=feature_id
                    )
                    
                    if schema_result.get("schema_markdown"):
                        db_session = self.db_session_factory()
                        try:
                            from app.db.models.Feature import Feature
                            feature_record = db_session.query(Feature).filter(Feature.id == feature_id).first()
                            current_store_id = feature_record.store_id if feature_record else None
                            import logging
                            logging.getLogger(__name__).info(f"Resolved store_id: '{current_store_id}' for feature_id: {feature_id}")

                            sql_gen_result = await self.db_rag_query_service.generate_queries(
                                user_message=user_message,
                                schema_markdown=schema_result["schema_markdown"],
                                store_id=current_store_id,
                                selected_tables=schema_result.get("selected_tables", [])
                            )
                            
                            # Decoupled: Passing only the planned query intention into the AI context for logical tracking.
                            valid_queries = [f"Intent: {q['intent']}\nSQL: {q['sql']}" for q in sql_gen_result["queries"] if q.get("is_valid")]
                            db_rag_data = "\n\n".join(valid_queries)
                        finally:
                            db_session.close()

            # Step 7: Build prompt (history + RAG data + query)
            # NOTE: NO persona prompt here - AgentService handles that
            prompt = self._build_prompt(
                history=history,
                rag_data=rag_data,
                db_rag_data=db_rag_data,
                user_query=user_message
            )
            
            # Step 6: Generate response using AgentService
            # AgentService will apply persona.prompt_text internally
            assistant_response = await self.agent_service.generate_async(
                prompt=prompt,
                persona=persona
            )
            
            # Step 7: Save messages
            user_msg = await self._save_user_message(
                chat_id=chat_id,
                content=user_message
            )
            
            assistant_msg = await self._save_assistant_message(
                chat_id=chat_id,
                content=assistant_response
            )
            
            # Step 8: Log Evaluation Metrics and Return
            end_time = time.time()
            duration_seconds = end_time - start_time
            
            input_tokens = 0
            output_tokens = 0
            try:
                # Basic token counting approximation for eval
                enc = tiktoken.get_encoding("cl100k_base")
                # Combine persona system prompt and built prompt
                full_input = persona.prompt_text + "\n" + prompt
                input_tokens = len(enc.encode(full_input))
                output_tokens = len(enc.encode(assistant_response))
            except Exception:
                pass
                
            file_id = "unknown"
            file_name = "unknown"
            retrieved_chunk_refs = []
            
            if sources:
                file_id = str(sources[0].get("file_id") or sources[0].get("document_id") or "unknown")
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
                    duration_seconds=duration_seconds
                )
            except Exception as e:
                print(f"[EvalLogger error]: {e}")

            return {
                "response": assistant_response,
                "user_message_id": user_msg.id,
                "assistant_message_id": assistant_msg.id,
                "sources": sources if use_rag else [],
                "persona_model": persona.model_name,
                "db_query_result": db_query_result
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process message: {str(e)}"
            )
    
    def _build_prompt(
        self,
        history: list,
        rag_data: Optional[str],
        db_rag_data: Optional[str],
        user_query: str
    ) -> str:
        """
        Build prompt from chat history + RAG data + DB_RAG data + user query
        
        NOTE: Does NOT include persona prompt - that's handled by AgentService
        
        Args:
            history: List of Message objects from chat history
            rag_data: RAG retrieved data (markdown formatted)
            db_rag_data: DB RAG query results (markdown formatted)
            user_query: Current user query
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # Add chat history (if exists)
        if history and len(history) > 0:
            prompt_parts.append("## Chat History\n")
            
            # Format last N messages (limit to avoid token limits)
            max_history = 10
            recent_history = history[-max_history:] if len(history) > max_history else history
            
            for msg in recent_history:
                role = "User" if msg.role == "user" else "Assistant"
                prompt_parts.append(f"**{role}:** {msg.content}\n")
            
            prompt_parts.append("\n")
        
        # Add RAG retrieved data (if available)
        if rag_data:
            prompt_parts.append("## Retrieved Context\n")
            prompt_parts.append(rag_data)
            prompt_parts.append("\n")

        # Add DB RAG results (if available)
        if db_rag_data:
            prompt_parts.append("## Database Results\n")
            prompt_parts.append(db_rag_data)
            prompt_parts.append("\n")
        
        # Add current user query
        prompt_parts.append("## Current Query\n")
        prompt_parts.append(f"**User:** {user_query}\n")
        
        # Add instruction
        prompt_parts.append("\n## Instructions\n")
        if rag_data or db_rag_data:
            prompt_parts.append(
                "Please provide a helpful response based on the chat history "
                "and the retrieved context/data above. "
            )
            if rag_data:
                prompt_parts.append("Cite sources when using information from documentation. ")
            if db_rag_data:
                prompt_parts.append("You may use the database results to answer transactional questions.")
        else:
            prompt_parts.append(
                "Please provide a helpful response based on the chat history."
            )
        
        return "".join(prompt_parts)
    
    async def _save_user_message(self, chat_id: int, content: str) -> Message:
        """Save user message to database"""
        try:
            message = Message(
                chat_id=chat_id,
                role="user",
                content=content,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            return self.memory_service.save_message(chat_id, message)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save user message: {str(e)}"
            )
    
    async def _save_assistant_message(self, chat_id: int, content: str) -> Message:
        """Save assistant message to database"""
        try:
            message = Message(
                chat_id=chat_id,
                role="assistant",
                content=content,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            return self.memory_service.save_message(chat_id, message)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save assistant message: {str(e)}"
            )
    
    def process_message_sync(
        self,
        chat_id: int,
        user_message: str,
        feature_id: int,
        user_id: str,
        use_rag: bool = True,
        rag_top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Synchronous version of process_message
        
        For compatibility with non-async contexts
        """
        try:
            # Validate
            if not user_message or not user_message.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Message cannot be empty"
                )
            
            # Get chat history
            history = self.memory_service.get_chat_history(chat_id)
            
            # Get persona
            persona = self.persona_service.get_persona_for_feature(feature_id)
            if not persona:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona not found for feature {feature_id}"
                )
            
            # Retrieve RAG data
            rag_data = None
            sources = []
            if use_rag:
                rag_result = self.rag_service.retrieve(
                    query=user_message,
                    feature_id=feature_id,
                    top_k=rag_top_k,
                    similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
                )
                rag_data = rag_result.get("formatted", "")
                sources = rag_result.get("sources", [])
            
            # Build prompt
            prompt = self._build_prompt(
                history=history,
                rag_data=rag_data,
                db_rag_data=None, # Sync context omits DB-RAG
                user_query=user_message
            )
            
            # Generate response (sync)
            assistant_response = self.agent_service.generate(
                prompt=prompt,
                persona=persona
            )
            
            # Save messages
            user_msg = Message(
                chat_id=chat_id,
                role="user",
                content=user_message,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            user_msg = self.memory_service.save_message(chat_id, user_msg)
            
            assistant_msg = Message(
                chat_id=chat_id,
                role="assistant",
                content=assistant_response,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            assistant_msg = self.memory_service.save_message(chat_id, assistant_msg)
            
            return {
                "response": assistant_response,
                "user_message_id": user_msg.id,
                "assistant_message_id": assistant_msg.id,
                "sources": sources if use_rag else [],
                "persona_model": persona.model_name
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process message: {str(e)}"
            )

