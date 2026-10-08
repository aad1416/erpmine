"""Pure schema tests for app/schemas/chats.py (map decisions D9, D5):
ChartSpec validation against the chart-spec prototype's 7 valid / 6 malformed
examples, the Attachment discriminated union, and the NULL -> [] contract on
MessageResponse / SendMessageResponse."""

from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from app.db.models.Message import Message
from app.schemas.chats import (
    AdminMessageResponse,
    Attachment,
    ChartSpec,
    IntentDetectionResult,
    MAX_CATEGORIES,
    MessageResponse,
    OutputProvenance,
    SendMessageResponse,
)


# ---------------------------------------------------------------------------
# ChartSpec — the 7 valid / 6 malformed examples from
# prototypes/chart_spec/chart_spec_proto.py (chart_spec_proto.EXAMPLES / INVALID).
# ---------------------------------------------------------------------------

VALID_CHART_SPECS = {
    "sales_by_state_dual_axis": {
        "type": "bar",
        "title": "Sales by state, 2025",
        "x": {"label": "State", "values": ["TX", "CA", "FL", "NY", "IL", "OH", "Other"]},
        "series": [
            {
                "name": "Total value",
                "values": [412500, 388200, 201750, 154300, 98400, 61250, 143900],
                "format": "currency",
                "unit": "USD",
                "axis": "primary",
            },
            {
                "name": "Orders",
                "values": [318, 254, 190, 121, 96, 57, 168],
                "format": "integer",
                "unit": "orders",
                "axis": "secondary",
            },
        ],
        "y_label": "Total value",
        "y2_label": "Orders",
        "note": "Sales orders dated 2025; excludes CANCELLED and REVISED. State from shipping address.",
    },
    "sales_by_state_value_only": {
        "type": "bar",
        "title": "Sales value by state, 2025",
        "x": {"label": "State", "values": ["TX", "CA", "FL", "NY", "IL", "OH", "Other"]},
        "series": [
            {
                "name": "Total value",
                "values": [412500, 388200, 201750, 154300, 98400, 61250, 143900],
                "format": "currency",
                "unit": "USD",
            },
        ],
        "note": "Sales orders dated 2025; excludes CANCELLED and REVISED. State from shipping address.",
    },
    "sales_by_state_count_only": {
        "type": "bar",
        "title": "Order count by state, 2025",
        "x": {"label": "State", "values": ["TX", "CA", "FL", "NY", "IL", "OH", "Other"]},
        "series": [
            {"name": "Orders", "values": [318, 254, 190, 121, 96, 57, 168], "format": "integer", "unit": "orders"},
        ],
    },
    "monthly_sales_two_years": {
        "type": "line",
        "title": "Monthly sales, 2024 vs 2025",
        "x": {
            "label": "Month",
            "values": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        },
        "series": [
            {
                "name": "2024",
                "values": [81200, 76400, 90100, 95800, 102300, 99700, 88900, 91200, 104500, 110800, 97600, 84300],
                "format": "currency",
                "unit": "USD",
            },
            {
                "name": "2025",
                "values": [88700, 82100, 97300, 101200, 109800, 105400, 94100, 98600, None, None, None, None],
                "format": "currency",
                "unit": "USD",
            },
        ],
        "y_label": "Net sales",
        "note": "Net of tax and freight. 2025 data through August.",
    },
    "top_vendors": {
        "type": "bar",
        "title": "Top 5 vendors by purchase value, last 12 months",
        "x": {
            "label": "Vendor",
            "values": [
                "Acme Industrial Supply Co.",
                "Northwind Fasteners",
                "Gulf Coast Steel & Alloys",
                "Brightline Electrical",
                "Summit Packaging",
                "Other (14 vendors)",
            ],
        },
        "series": [
            {
                "name": "Purchase value",
                "values": [612400, 455900, 398250, 210700, 164300, 287650],
                "format": "currency",
                "unit": "USD",
            },
        ],
        "horizontal": True,
        "note": "Purchase orders excluding CANCELLED and inactive.",
    },
    "vendor_delay_buckets": {
        "type": "bar",
        "title": "Delivery vs expected lead time, by vendor",
        "x": {"label": "Vendor", "values": ["Acme Industrial", "Northwind", "Gulf Coast Steel", "Brightline", "Summit"]},
        "series": [
            {"name": "Early / on time", "values": [42, 30, 18, 25, 12], "format": "integer", "unit": "POs"},
            {"name": "1–7 days late", "values": [9, 14, 11, 4, 6], "format": "integer", "unit": "POs"},
            {"name": "8–30 days late", "values": [3, 6, 9, 1, 2], "format": "integer", "unit": "POs"},
            {"name": "30+ days late", "values": [0, 2, 4, 0, 1], "format": "integer", "unit": "POs"},
        ],
        "y_label": "Purchase orders",
        "stacked": True,
        "note": "Expected = purchase date + line lead time; actual = last receipt on the PO. POs with no receipt excluded.",
    },
    "inventory_aging": {
        "type": "pie",
        "title": "On-hand inventory value by age",
        "x": {"label": "Age since receipt", "values": ["< 90 days", "90–180 days", "180–365 days", "1–2 years", "2+ years"]},
        "series": [
            {"name": "On-hand value", "values": [184300, 96200, 71850, 43900, 28400], "format": "currency", "unit": "USD"},
        ],
        "note": "Age from receipt date; 'used' = issued via goods issue.",
    },
}

INVALID_CHART_SPECS = {
    "series_length_mismatch": {
        "type": "bar",
        "title": "Bad",
        "x": {"values": ["A", "B", "C"]},
        "series": [{"name": "s", "values": [1, 2]}],
    },
    "pie_with_two_series": {
        "type": "pie",
        "title": "Bad",
        "x": {"values": ["A", "B"]},
        "series": [{"name": "s1", "values": [1, 2]}, {"name": "s2", "values": [3, 4]}],
    },
    "stacked_line": {
        "type": "line",
        "title": "Bad",
        "x": {"values": ["A", "B"]},
        "series": [{"name": "s", "values": [1, 2]}],
        "stacked": True,
    },
    "all_series_secondary": {
        "type": "bar",
        "title": "Bad",
        "x": {"values": ["A"]},
        "series": [{"name": "s", "values": [1], "axis": "secondary"}],
    },
    "too_many_categories": {
        "type": "bar",
        "title": "Bad",
        "x": {"values": [f"c{i}" for i in range(MAX_CATEGORIES + 1)]},
        "series": [{"name": "s", "values": [1] * (MAX_CATEGORIES + 1)}],
    },
    "unknown_type": {
        "type": "scatter",
        "title": "Bad",
        "x": {"values": ["A"]},
        "series": [{"name": "s", "values": [1]}],
    },
}


@pytest.mark.parametrize("name", list(VALID_CHART_SPECS))
def test_chart_spec_accepts_prototype_valid_examples(name):
    ChartSpec.model_validate(VALID_CHART_SPECS[name])


@pytest.mark.parametrize("name", list(INVALID_CHART_SPECS))
def test_chart_spec_rejects_prototype_malformed_examples(name):
    with pytest.raises(ValidationError):
        ChartSpec.model_validate(INVALID_CHART_SPECS[name])


# ---------------------------------------------------------------------------
# Attachment union
# ---------------------------------------------------------------------------

_ATTACHMENT_ADAPTER: TypeAdapter = TypeAdapter(Attachment)

_PROVENANCE = {
    "sql": "SELECT 1",
    "transforms": [],
    "row_count": 1,
    "generated_at": "2026-09-15T00:00:00Z",
}


def test_attachment_union_parses_chart_kind():
    attachment = _ATTACHMENT_ADAPTER.validate_python(
        {
            "kind": "chart",
            "title": "Chart",
            "spec": VALID_CHART_SPECS["inventory_aging"],
            "provenance": _PROVENANCE,
        }
    )
    assert attachment.kind == "chart"


def test_attachment_union_parses_table_kind():
    attachment = _ATTACHMENT_ADAPTER.validate_python(
        {
            "kind": "table",
            "title": "Table",
            "columns": [{"key": "a", "label": "A", "type": "string"}],
            "rows": [["x"]],
            "row_count": 1,
            "truncated": False,
            "provenance": _PROVENANCE,
        }
    )
    assert attachment.kind == "table"


def test_attachment_union_parses_file_kind():
    attachment = _ATTACHMENT_ADAPTER.validate_python(
        {
            "kind": "file",
            "title": "File",
            "file_id": "f-1",
            "filename": "export.xlsx",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "size": 10,
            "provenance": _PROVENANCE,
        }
    )
    assert attachment.kind == "file"


def test_attachment_union_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        _ATTACHMENT_ADAPTER.validate_python(
            {
                "kind": "graph",
                "title": "Bad",
                "provenance": _PROVENANCE,
            }
        )


def test_output_provenance_transforms_is_list_of_steps_and_defaults_empty():
    raw = OutputProvenance.model_validate(_PROVENANCE)
    assert raw.transforms == []

    chained = OutputProvenance.model_validate(
        {**_PROVENANCE, "transforms": [{"transform": "top_n", "params": {"n": 5}}]}
    )
    assert chained.transforms[0].transform == "top_n"
    assert chained.transforms[0].params == {"n": 5}


# ---------------------------------------------------------------------------
# NULL -> [] contract (D5 / ticket 04)
# ---------------------------------------------------------------------------

def test_message_response_defaults_attachments_to_empty_list():
    response = MessageResponse(
        id=1,
        chat_id=1,
        role="assistant",
        content="hi",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert response.attachments == []


def test_message_response_serialises_null_orm_attachments_as_empty_list():
    message = Message(
        id=1,
        chat_id=1,
        role="assistant",
        content="hi",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        attachments=None,
    )

    response = MessageResponse.model_validate(message, from_attributes=True)

    assert response.attachments == []


def test_send_message_response_defaults_attachments_to_empty_list():
    response = SendMessageResponse(
        message="hi",
        user_message_id=1,
        assistant_message_id=2,
        persona_model="gpt-4o",
        chat_id=1,
    )
    assert response.attachments == []
    assert response.db_query_result is None


def test_admin_message_response_defaults_attachments_to_empty_list():
    response = AdminMessageResponse(
        response="hi",
        intent=IntentDetectionResult(behavior_change=False, rag_data=False),
        user_message_id=1,
        assistant_message_id=2,
        chat_id=1,
    )
    assert response.attachments == []


def test_admin_message_response_coerces_null_attachments_to_empty_list():
    response = AdminMessageResponse(
        response="hi",
        intent=IntentDetectionResult(behavior_change=False, rag_data=False),
        user_message_id=1,
        assistant_message_id=2,
        chat_id=1,
        attachments=None,
    )
    assert response.attachments == []
