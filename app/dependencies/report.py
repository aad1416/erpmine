from typing import Annotated

from fastapi import Depends

from app.dependencies.agent import get_agent_service
from app.services.agent_service import AgentService
from app.services.report_service import ReportService


def get_report_service(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ReportService:
    return ReportService(agent_service=agent_service)
