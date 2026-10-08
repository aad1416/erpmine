from datetime import datetime
from typing import List, Optional
from app.db.models.Persona import Persona
from app.repositories.personas import PersonaRepository
from app.schemas.personas import PersonaUpdate


class PersonaService:
    def __init__(self, persona_repository: PersonaRepository):
        self.persona_repository = persona_repository

    def get_persona_by_id(self, persona_id: int) -> Optional[Persona]:
        """Get a persona by ID."""
        return self.persona_repository.get_by_id(persona_id)

    def get_persona_for_feature(self, feature_id: int) -> Optional[Persona]:
        """Get persona for a specific feature."""
        return self.persona_repository.get_by_feature_id(feature_id)

    def list_all_personas(self) -> List[Persona]:
        """List all personas."""
        return self.persona_repository.get_all()

    def update_persona(self, persona_id: int, persona_update: PersonaUpdate) -> Optional[Persona]:
        """Update an existing persona."""
        persona = self.persona_repository.get_by_id(persona_id)
        if not persona:
            return None
        
        if persona_update.prompt_text is not None:
            persona.prompt_text = persona_update.prompt_text
        if persona_update.model_name is not None:
            persona.model_name = persona_update.model_name
        if persona_update.updated_by_user_id is not None:
            persona.updated_by_user_id = persona_update.updated_by_user_id
            
        persona.updated_at = datetime.now()
        return self.persona_repository.update(persona)

    def reset_persona_to_original(self, persona_id: int, user_id: str) -> Optional[Persona]:
        """Reset persona prompt to original prompt text."""
        persona = self.persona_repository.get_by_id(persona_id)
        if not persona:
            return None
            
        persona.prompt_text = persona.original_prompt_text
        persona.updated_by_user_id = user_id
        persona.updated_at = datetime.now()
        return self.persona_repository.update(persona)

    def get_llm_client(self, persona_id: int):
        """
        Placeholder for LLM client selection based on persona.model_name.
        This would return an initialized LangChain model or similar.
        """
        persona = self.persona_repository.get_by_id(persona_id)
        if not persona:
            return None
            
        model_name = persona.model_name
        # Logic to select LLM based on model_name
        # e.g., if "gpt-4" -> OpenAI, if "claude-3" -> Anthropic, etc.
        return f"Client for model: {model_name}"

