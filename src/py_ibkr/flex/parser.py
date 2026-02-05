import xml.etree.ElementTree as ET
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from .enums import Code
from .models import CashTransaction, FlexQueryResponse, FlexStatement, Trade

# IBKR Date/Time Formats
# Dates: yyyyMMdd or yyyy-MM-dd
# Times: HHmmss or HH:mm:ss
# Datetime: date;time (semicolon separator)


def parse_date(value: str) -> date | None:
    if not value or value in ("0", "N/A", ""):
        return None
    try:
        if len(value) == 8:
            return datetime.strptime(value, "%Y%m%d").date()
        elif "-" in value:
            return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        pass
    return None


def parse_time(value: str) -> time | None:
    if not value or value in ("0", "N/A", ""):
        return None
    try:
        if len(value) == 6:
            return datetime.strptime(value, "%H%M%S").time()
        elif ":" in value:
            return datetime.strptime(value, "%H:%M:%S").time()
    except ValueError:
        pass
    return None


def parse_datetime(value: str) -> datetime | None:
    if not value or value in ("0", "N/A", ""):
        return None

    # Handle semicolon separator
    if ";" in value:
        d_str, t_str = value.split(";")
        d = parse_date(d_str)
        t = parse_time(t_str)
        if d and t:
            return datetime.combine(d, t)
    # Handle comma separator (legacy)
    elif "," in value:
        d_str, t_str = value.split(",")
        d = parse_date(d_str)
        t = parse_time(t_str.strip())
        if d and t:
            return datetime.combine(d, t)
    # Handle single string format if applicable
    elif len(value) == 8:  # Just date?
        d = parse_date(value)
        if d:
            return datetime.combine(d, time.min)

    return None


def parse_bool(value: str) -> bool | None:
    if not value:
        return None
    if value.upper() == "Y":
        return True
    if value.upper() == "N":
        return False
    return None


def parse_decimal(value: str) -> Decimal | None:
    if not value or value in ("N/A", ""):
        return None
    try:
        return Decimal(value.replace(",", ""))
    except Exception:
        return None


def clean_attributes(attrs: dict[str, str], model_class: type) -> dict[str, Any]:
    """Convert string attributes to types expected by the model."""
    cleaned: dict[str, Any] = {}

    for key, value in attrs.items():
        if key not in model_class.model_fields:
            # Skip unknown fields to avoid crashing, matching our "extra=ignore" policy
            # But we could also log them if we wanted to discover new fields
            continue

        field_info = model_class.model_fields[key]
        annotation = field_info.annotation

        # Determine target type
        # Simplify references to Optional[Type] etc.
        # This is a basic conversion, Pydantic does validation too.
        # But we format data so Pydantic is happy.

        # Check specific conversions
        if key in ("notes", "code"):
            # Handle code sequences (sep = ; or ,)
            if not value:
                cleaned[key] = []
            else:
                sep = ";" if ";" in value else ","
                codes = [Code(v) for v in value.split(sep) if v]
                cleaned[key] = codes

        # Legacy Enum Fixups
        elif key == "type" and value == "Deposits/Withdrawals":
            cleaned[key] = "Deposits & Withdrawals"
        elif key == "type" and value == "ACAT":
            cleaned[key] = "ACATS"
        elif key == "orderType" and ";" in value:
            cleaned[key] = "MULTIPLE"

        elif "datetime" in str(annotation):
            cleaned[key] = parse_datetime(value)
        elif "date" in str(annotation):
            cleaned[key] = parse_date(value)
        elif "time" in str(annotation):
            cleaned[key] = parse_time(value)
        elif "bool" in str(annotation):
            cleaned[key] = parse_bool(value)
        elif "Decimal" in str(annotation):
            cleaned[key] = parse_decimal(value)
        elif "List[Code]" in str(annotation):
            # Handle code sequences (sep = ; or ,)
            sep = ";" if ";" in value else ","
            codes = [Code(v) for v in value.split(sep) if v]
            cleaned[key] = codes
        else:
            # Enums and strings
            if not value:
                cleaned[key] = None
            else:
                cleaned[key] = value

    return cleaned


def parse_xml_file(file_path: str) -> FlexQueryResponse:
    tree = ET.parse(file_path)
    root = tree.getroot()

    if root.tag != "FlexQueryResponse":
        raise ValueError("Not a FlexQueryResponse XML file")

    return parse_flex_query_response(root)


def parse_flex_query_response(elem: ET.Element) -> FlexQueryResponse:
    attrs = clean_attributes(elem.attrib, FlexQueryResponse)

    statements = []

    # Check for FlexStatements container
    flex_statements_elem = elem.find("FlexStatements")
    if flex_statements_elem is not None:
        for stmt_elem in flex_statements_elem.findall("FlexStatement"):
            statements.append(parse_flex_statement(stmt_elem))

    attrs["FlexStatements"] = statements
    return FlexQueryResponse(**attrs)


def parse_flex_statement(elem: ET.Element) -> FlexStatement:
    attrs = clean_attributes(elem.attrib, FlexStatement)

    trades = []
    cash_transactions = []

    # Parse Trades
    trades_container = elem.find("Trades")
    if trades_container is not None:
        for trade_elem in trades_container.findall("Trade"):
            trade_attrs = clean_attributes(trade_elem.attrib, Trade)
            trades.append(Trade(**trade_attrs))

    # Parse CashTransactions
    cash_container = elem.find("CashTransactions")
    if cash_container is not None:
        for cash_elem in cash_container.findall("CashTransaction"):
            cash_attrs = clean_attributes(cash_elem.attrib, CashTransaction)
            # Handle special enum conversion if needed (e.g. types with spaces)
            # Pydantic should handle string to Enum if values match
            cash_transactions.append(CashTransaction(**cash_attrs))

    attrs["Trades"] = trades
    attrs["CashTransactions"] = cash_transactions

    return FlexStatement(**attrs)
