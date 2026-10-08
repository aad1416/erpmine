from app.services.agent_service import agent_service, AgentService


def get_agent_service() -> AgentService:
    """
    Dependency injection for Agent Service
    
    Returns singleton instance of AgentService
    """
    return agent_service

