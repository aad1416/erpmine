from enum import StrEnum

from pydantic import BaseModel


class InvoiceDocumentType(StrEnum):
    CUSTOMER_PO = "customer_po"
    SALES_ORDER = "sales_order"
    QUOTE = "quote"
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"


class CompareInvoiceResponse(BaseModel):
    """Markdown comparison report from the compare-invoice tool."""

    detail: str
