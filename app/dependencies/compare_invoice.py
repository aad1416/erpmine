from typing import Annotated, Union

from fastapi import Depends

from app.dependencies.agent import get_agent_service
from app.dependencies.documents import get_document_parser
from app.services.agent_service import AgentService
from app.services.compare_invoice_service import CompareInvoiceService
from app.utils.document_parser import DocumentParser
from app.utils.fast_document_parser import FastDocumentParser


def get_compare_invoice_service(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    parser: Annotated[
        Union[DocumentParser, FastDocumentParser], Depends(get_document_parser)
    ],
) -> CompareInvoiceService:
    return CompareInvoiceService(agent_service=agent_service, parser=parser)
