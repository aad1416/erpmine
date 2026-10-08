from typing import Annotated

from fastapi import Depends

from app.dependencies.agent import get_agent_service
from app.services.agent_service import AgentService
from app.services.field_service_ticket_summary_service import (
    FieldServiceTicketSummaryService,
)
from app.services.unit_ticket_client import UnitTicketClient


def get_unit_ticket_client() -> UnitTicketClient:
    return UnitTicketClient()


def get_field_service_ticket_summary_service(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    unit_ticket_client: Annotated[UnitTicketClient, Depends(get_unit_ticket_client)],
) -> FieldServiceTicketSummaryService:
    return FieldServiceTicketSummaryService(
        agent_service=agent_service,
        unit_ticket_client=unit_ticket_client,
    )
