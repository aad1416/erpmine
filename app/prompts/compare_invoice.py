"""Prompt templates for the compare-invoice tool."""

from app.schemas.compare_invoice import InvoiceDocumentType

COMPARE_INVOICE_SYSTEM_PROMPT = "You are a helpful assistant."

DOCUMENT_TYPE_LABELS: dict[InvoiceDocumentType, tuple[str, str]] = {
    InvoiceDocumentType.CUSTOMER_PO: ("Customer Purchase Order", "PO"),
    InvoiceDocumentType.SALES_ORDER: ("Sales Order", "SO"),
    InvoiceDocumentType.QUOTE: ("Quote", "Quote"),
    InvoiceDocumentType.INVOICE: ("Invoice", "Invoice"),
    InvoiceDocumentType.PURCHASE_ORDER: ("Purchase Order", "PO"),
}

# Updated prompt to tolerate differing line‑item names.  It now:
# • Focuses on totals equality as a primary check.
# • Treats mismatched names as acceptable when amounts match.
# • Adds a “Notes” section that lists items whose names differ.
COMPARE_INVOICE_PROMPT_TEMPLATE = """Compare the {doc_a_label} and the {doc_b_label}. Do the following:
1. At the very top, state clearly if the {doc_a_label} and {doc_b_label} match or if there are differences. If they match, show a 👍 icon.
2. Provide a summary table comparing:
   - Line items (product descriptions, quantities, unit prices, and amounts). **Do not require identical item names**; treat items as matching when their quantities, unit prices, and amounts are equal even if the names differ.
   - Tariff fees, shipping, expedited fees, and any other charges.
   - Terms (payment terms, shipping terms, etc.).
   - Totals.
3. Highlight any discrepancies in red (or call them out clearly if formatting is plain text).
4. At the bottom, show:
   {doc_a_short} Total = [value]
   {doc_b_short} Total = [value]
5. Add a **Notes** section that lists any line‑item name differences you observed, even if their amounts match.
6. Provide a step‑by‑step breakdown of where they align or differ.
7. End with a short summary stating whether everything is aligned or what issues need to be resolved.
---
Example output structure when you give me files:
# 👍 {doc_a_label} and {doc_b_label} Match
## Comparison Table

| Item (may have different names) | {doc_a_short} Value | {doc_b_short} Value | Match? |
|--------------------------------|---------------------|---------------------|--------|
| Product A (Qty/Price)          | $1,000.00           | $1,000.00           | ✅     |
| Service B (Qty/Price)          | $500.00             | $500.00             | ✅     |
| Tariff Fee                     | $100.00             | $100.00             | ✅     |
| Payment Terms                  | Net 30              | ACH (3.5% fee)      | ⚠️     |

## Notes on Name Differences
- "Product A" in {doc_a_label} corresponds to "Item Alpha" in {doc_b_label} (amounts match).
- "Service B" vs "Service Beta" – names differ but totals align.

## Totals
- **{doc_a_short} Total:** $1,600.00
- **{doc_b_short} Total:** $1,600.00

## Step‑By‑Step Review
- Line‑item amounts match despite name differences (listed in Notes).
- Fees match.
- Totals match.
- Payment terms differ.

## Summary
✅ Overall aligned on amounts. Pay attention to the noted name differences and payment‑term mismatch.
---

{doc_a_label}: `{doc_a_text}`
{doc_b_label}: `{doc_b_text}`"""


def get_compare_invoice_prompt(
    doc_a_type: InvoiceDocumentType,
    doc_b_type: InvoiceDocumentType,
    doc_a_text: str,
    doc_b_text: str,
) -> str:
    doc_a_label, doc_a_short = DOCUMENT_TYPE_LABELS[doc_a_type]
    doc_b_label, doc_b_short = DOCUMENT_TYPE_LABELS[doc_b_type]
    return COMPARE_INVOICE_PROMPT_TEMPLATE.format(
        doc_a_label=doc_a_label,
        doc_b_label=doc_b_label,
        doc_a_short=doc_a_short,
        doc_b_short=doc_b_short,
        doc_a_text=doc_a_text,
        doc_b_text=doc_b_text,
    )
