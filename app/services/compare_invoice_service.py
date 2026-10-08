from types import SimpleNamespace
from typing import Union

from fastapi import HTTPException, UploadFile, status

from app.config.setting import settings
from app.prompts.compare_invoice import (
    COMPARE_INVOICE_SYSTEM_PROMPT,
    get_compare_invoice_prompt,
)
from app.schemas.compare_invoice import InvoiceDocumentType
from app.services.agent_service import AgentService
from app.utils.document_parser import DocumentParser
from app.utils.fast_document_parser import FastDocumentParser
from app.utils.file_to_text import convert_upload_to_text


class CompareInvoiceService:
    def __init__(
        self,
        agent_service: AgentService,
        parser: Union[DocumentParser, FastDocumentParser],
    ):
        self.agent_service = agent_service
        self.parser = parser

    async def compare_invoice(
        self,
        invoice_a: UploadFile,
        invoice_a_type: InvoiceDocumentType,
        invoice_b: UploadFile,
        invoice_b_type: InvoiceDocumentType,
    ) -> str:
        try:
            doc_a_text = await convert_upload_to_text(invoice_a, self.parser)
            doc_b_text = await convert_upload_to_text(invoice_b, self.parser)
            prompt = get_compare_invoice_prompt(
                doc_a_type=invoice_a_type,
                doc_b_type=invoice_b_type,
                doc_a_text=doc_a_text,
                doc_b_text=doc_b_text,
            )
            persona = SimpleNamespace(
                prompt_text=COMPARE_INVOICE_SYSTEM_PROMPT,
                model_name=settings.COMPARE_INVOICE_MODEL,
            )
            return await self.agent_service.generate_async(
                prompt=prompt,
                persona=persona,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error: {exc}",
            ) from exc
