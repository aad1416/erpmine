"""Pure-function tests for the column-type inference helper shared by create_table
and (later) export_excel (ticket 06/07 decision): currency for numeric
total|value|spend|amount|cost columns, date for *date* columns, else number/string;
labels are humanised column names."""

from app.utils.column_typing import (
    excel_number_format,
    humanize_column_label,
    infer_column_type,
    is_percent_column,
)


def test_date_pattern_wins_even_over_a_numeric_sample():
    assert infer_column_type("purchase_date", [1234567890]) == "date"


def test_currency_pattern_requires_a_numeric_sample():
    assert infer_column_type("order_total", [100.0, 50.0]) == "currency"
    assert infer_column_type("order_total", ["N/A", None]) == "string"


def test_currency_synonyms():
    for name in ["total_value", "vendor_spend", "line_amount", "shipping_cost"]:
        assert infer_column_type(name, [10]) == "currency"


def test_plain_numeric_column_is_number():
    assert infer_column_type("quantity", [1, 2, 3]) == "number"


def test_non_numeric_column_is_string():
    assert infer_column_type("vendor_name", ["Acme", "Globex"]) == "string"


def test_boolean_values_are_not_numeric():
    assert infer_column_type("is_active", [True, False]) == "string"


def test_all_null_column_defaults_to_string():
    assert infer_column_type("mystery", [None, None]) == "string"


def test_leading_nulls_are_skipped_when_sampling():
    assert infer_column_type("order_total", [None, None, 42.0]) == "currency"


def test_humanize_column_label():
    assert humanize_column_label("shipping_address_state") == "Shipping Address State"
    assert humanize_column_label("id") == "Id"
    assert humanize_column_label("order_total") == "Order Total"


def test_is_percent_column_matches_pct_suffix_and_bare_pct():
    assert is_percent_column("share_pct")
    assert is_percent_column("change_pct")
    assert is_percent_column("pct")
    assert not is_percent_column("percentage")
    assert not is_percent_column("pctile")


def test_excel_number_format_pct_column_is_plain_number_not_percent():
    assert excel_number_format("share_pct", "number", [23.5, 76.5]) == "#,##0.0"


def test_excel_number_format_currency():
    assert excel_number_format("order_total", "currency", [10.0]) == "$#,##0.00"


def test_excel_number_format_number_decimal_vs_integer():
    assert excel_number_format("avg_days", "number", [1.5, 2.0]) == "#,##0.00"
    assert excel_number_format("quantity", "number", [1, 2, 3]) == "#,##0"


def test_excel_number_format_date():
    assert excel_number_format("purchase_date", "date", []) == "yyyy-mm-dd"


def test_excel_number_format_string_has_no_format():
    assert excel_number_format("vendor_name", "string", ["Acme"]) is None
