from typing import Dict, Any, Optional, Union
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from app.db.models.Persona import Persona
from app.config.setting import settings

DEFAULT_LLM_TEMPERATURE = 0.7


class AgentService:
    """
    Agent Service - LLM Client Factory
    
    Responsibilities:
    - Construct LLM clients based on persona.model_name
    - Apply persona prompt internally as system message
    - Generate responses using LangChain
    - No orchestration (ChatService handles that)
    """
    
    def __init__(self):
        self.llm_cache: Dict[str, BaseChatModel] = {}
    
    def _create_openai_client(self, model_name: str, temperature: float) -> BaseChatModel:
        """Create OpenAI LLM client"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is not installed. "
                "Please install it with: pip install langchain-openai"
            )
        
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
        )
    
    def _create_anthropic_client(self, model_name: str, temperature: float) -> BaseChatModel:
        """Create Anthropic Claude LLM client"""
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is not installed. "
                "Please install it with: pip install langchain-anthropic"
            )
        
        anthropic_api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in settings")
        
        return ChatAnthropic(
            model=model_name,
            api_key=anthropic_api_key,
            temperature=temperature,
        )
    
    def _create_google_client(self, model_name: str, temperature: float) -> BaseChatModel:
        """Create Google Gemini LLM client"""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is not installed. "
                "Please install it with: pip install langchain-google-genai"
            )
        
        google_api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in settings")
        
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=temperature,
        )
    
    def _create_xai_client(self, model_name: str, temperature: float) -> BaseChatModel:
        """Create xAI (Grok) LLM client using OpenAI-compatible API"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is not installed. "
                "Please install it with: pip install langchain-openai"
            )
        
        if not settings.GROK_API_KEY:
            raise ValueError("GROK_API_KEY not found in settings")
        
        return ChatOpenAI(
            model=model_name,
            api_key=settings.GROK_API_KEY,
            base_url="https://api.x.ai/v1",
            temperature=temperature,
        )
    
    @staticmethod
    def _cache_key(model_name: str, temperature: float) -> str:
        return f"{model_name}:{temperature}"

    def _get_llm_client(
        self,
        model_name: str,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
    ) -> BaseChatModel:
        """
        Factory method to create LLM client based on model name and temperature.

        Supports:
        - OpenAI: gpt-4, gpt-4-turbo, gpt-3.5-turbo, etc.
        - Anthropic: claude-3-opus, claude-3-sonnet, claude-3-haiku, etc.
        - Google: gemini-pro, gemini-1.5-pro, etc.
        - xAI: grok-beta, grok-2, etc.
        """
        cache_key = self._cache_key(model_name, temperature)
        if cache_key in self.llm_cache:
            return self.llm_cache[cache_key]

        model_lower = model_name.lower()

        if model_lower.startswith('gpt-'):
            llm = self._create_openai_client(model_name, temperature)
        elif model_lower.startswith('claude-'):
            llm = self._create_anthropic_client(model_name, temperature)
        elif model_lower.startswith('gemini-'):
            llm = self._create_google_client(model_name, temperature)
        elif model_lower.startswith('grok-'):
            llm = self._create_xai_client(model_name, temperature)
        else:
            llm = self._create_openai_client(model_name, temperature)

        self.llm_cache[cache_key] = llm
        return llm
    
    def generate(
        self,
        prompt: str,
        persona: Union[Persona, Any],
        stream: bool = False,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate response using LLM
        
        Args:
            prompt: The user prompt (built by ChatService with history + RAG data + query)
            persona: Persona object containing prompt_text and model_name
            stream: Whether to stream the response (optional, for future use)
            temperature: Sampling temperature for the LLM client (default 0.7)
            **kwargs: Additional arguments to pass to LLM invoke
        
        Returns:
            Generated response as string
        """
        llm = self._get_llm_client(
            persona.model_name,
            temperature=temperature if temperature is not None else DEFAULT_LLM_TEMPERATURE,
        )
        
        # Build messages with persona prompt as system message
        messages = [
            SystemMessage(content=persona.prompt_text),
            HumanMessage(content=prompt)
        ]
        
        # Generate response
        response = llm.invoke(messages, **kwargs)
        
        # Extract content from response
        if hasattr(response, 'content'):
            return response.content
        else:
            return str(response)
    
    async def generate_async(
        self,
        prompt: str,
        persona: Union[Persona, Any],
        stream: bool = False,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Async version of generate method
        
        Args:
            prompt: The user prompt (built by ChatService with history + RAG data + query)
            persona: Persona object containing prompt_text and model_name
            stream: Whether to stream the response (optional, for future use)
            temperature: Sampling temperature for the LLM client (default 0.7)
            **kwargs: Additional arguments to pass to LLM ainvoke
        
        Returns:
            Generated response as string
        """
        llm = self._get_llm_client(
            persona.model_name,
            temperature=temperature if temperature is not None else DEFAULT_LLM_TEMPERATURE,
        )
        
        # Build messages with persona prompt as system message
        messages = [
            SystemMessage(content=persona.prompt_text),
            HumanMessage(content=prompt)
        ]
        
        # Generate response asynchronously
        response = await llm.ainvoke(messages, **kwargs)
        
        # Extract content from response
        if hasattr(response, 'content'):
            return response.content
        else:
            return str(response)
    
    def clear_cache(self):
        """Clear LLM client cache"""
        self.llm_cache.clear()


# Create singleton instance
agent_service = AgentService()

