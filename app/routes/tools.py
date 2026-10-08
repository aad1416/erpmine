from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.dependencies.auth import get_current_user
from app.dependencies.compare_invoice import get_compare_invoice_service
from app.dependencies.field_service_ticket_summary import (
    get_field_service_ticket_summary_service,
)
from app.dependencies.make_post import get_make_post_service
from app.dependencies.report import get_report_service
from app.dependencies.unit_rca import get_unit_rca_service
from app.db.models.Users import User
from app.schemas.compare_invoice import CompareInvoiceResponse, InvoiceDocumentType
from app.schemas.field_service_ticket_summary import (
    FieldServiceTicketSummaryRequest,
    FieldServiceTicketSummaryResponse,
)
from app.schemas.make_post import MakePostResponse
from app.schemas.report import ReportRequest, ReportResponse
from app.schemas.unit_rca import UnitRCARequest, UnitRCAResponse
from app.services.compare_invoice_service import CompareInvoiceService
from app.services.field_service_ticket_summary_service import (
    FieldServiceTicketSummaryService,
)
from app.services.make_post_service import MakePostService
from app.services.report_service import ReportService
from app.services.unit_rca_service import UnitRCAService

tools_router = APIRouter(prefix="/tools", tags=["tools"])


@tools_router.post(
    "/make-post",
    response_model=MakePostResponse,
    status_code=status.HTTP_200_OK,
)
async def make_post(
    document: Annotated[UploadFile, File(description="Source document for the post")],
    _: Annotated[User, Depends(get_current_user)],
    make_post_service: Annotated[MakePostService, Depends(get_make_post_service)],
    current_post: Annotated[
        str, Form(description="Existing post HTML, or empty for a new post")
    ] = "",
):
    """Generate or update an HTML post by merging an uploaded document into current_post."""
    detail = await make_post_service.make_post(
        document=document,
        current_post=current_post,
    )
    return MakePostResponse(detail=detail)


@tools_router.post(
    "/compare-invoice",
    response_model=CompareInvoiceResponse,
    status_code=status.HTTP_200_OK,
)
async def compare_invoice(
    invoice_a: Annotated[UploadFile, File(description="First document to compare")],
    invoice_a_type: Annotated[
        InvoiceDocumentType, Form(description="Document type for invoice_a")
    ],
    invoice_b: Annotated[UploadFile, File(description="Second document to compare")],
    invoice_b_type: Annotated[
        InvoiceDocumentType, Form(description="Document type for invoice_b")
    ],
    _: Annotated[User, Depends(get_current_user)],
    compare_invoice_service: Annotated[
        CompareInvoiceService, Depends(get_compare_invoice_service)
    ],
):
    """Compare two business documents and return a Markdown comparison report."""
    detail = await compare_invoice_service.compare_invoice(
        invoice_a=invoice_a,
        invoice_a_type=invoice_a_type,
        invoice_b=invoice_b,
        invoice_b_type=invoice_b_type,
    )
    return CompareInvoiceResponse(detail=detail)


@tools_router.post(
    "/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
)
async def report(
    body: ReportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
):
    """Generate a structured professional report from a narrative and metadata."""
    detail = await report_service.generate_report(
        narrative=body.narrative,
        info=body.info,
        user=current_user,
    )
    return ReportResponse(detail=detail)


@tools_router.post(
    "/field-service-ticket-summary",
    response_model=FieldServiceTicketSummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def field_service_ticket_summary(
    body: FieldServiceTicketSummaryRequest,
    _: Annotated[User, Depends(get_current_user)],
    field_service_ticket_summary_service: Annotated[
        FieldServiceTicketSummaryService,
        Depends(get_field_service_ticket_summary_service),
    ],
):
    """Summarize a unit's field service tickets into a Markdown problem/resolution history."""
    detail = await field_service_ticket_summary_service.summarize(
        unit_id=body.unit_id,
    )
    return FieldServiceTicketSummaryResponse(detail=detail)


@tools_router.post(
    "/unit-rca",
    response_model=UnitRCAResponse,
    status_code=status.HTTP_200_OK,
)
async def unit_rca(
    body: UnitRCARequest,
    current_user: Annotated[User, Depends(get_current_user)],
    unit_rca_service: Annotated[UnitRCAService, Depends(get_unit_rca_service)],
):
    """Root-cause a field service ticket against the unit's history and the store's
    equipment documentation, and write the RCA report back onto the ticket."""
    return await unit_rca_service.analyze(
        unit_id=body.unit_id,
        ticket_id=body.ticket_id,
        store_id=current_user.store_id,
    )
