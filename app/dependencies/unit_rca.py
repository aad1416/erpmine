from typing import Annotated

from fastapi import Depends

from app.dependencies.chat import get_document_retrieval_tool_service
from app.dependencies.features import get_feature_service
from app.dependencies.field_service_ticket_summary import get_unit_ticket_client
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
from app.services.feature_service import FeatureService
from app.services.unit_rca_agent_runner import UnitRCAAgentRunner
from app.services.unit_rca_service import UnitRCAService
from app.services.unit_ticket_client import UnitTicketClient

_unit_rca_agent_runner_singleton: UnitRCAAgentRunner | None = None


def get_unit_rca_agent_runner() -> UnitRCAAgentRunner:
    # Stateless wrapper; reused across requests like get_chat_agent_runner.
    global _unit_rca_agent_runner_singleton
    if _unit_rca_agent_runner_singleton is None:
        _unit_rca_agent_runner_singleton = UnitRCAAgentRunner()
    return _unit_rca_agent_runner_singleton


def get_unit_rca_service(
    feature_service: Annotated[FeatureService, Depends(get_feature_service)],
    unit_ticket_client: Annotated[UnitTicketClient, Depends(get_unit_ticket_client)],
    document_retrieval_tool_service: Annotated[
        DocumentRetrievalToolService, Depends(get_document_retrieval_tool_service)
    ],
    agent_runner: Annotated[UnitRCAAgentRunner, Depends(get_unit_rca_agent_runner)],
) -> UnitRCAService:
    return UnitRCAService(
        feature_service=feature_service,
        unit_ticket_client=unit_ticket_client,
        document_retrieval_tool_service=document_retrieval_tool_service,
        agent_runner=agent_runner,
    )
