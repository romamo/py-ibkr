import xml.etree.ElementTree as ET
from typing import Any

from pydantic import BaseModel

from .enums import Code
from .models import CashReportCurrency, CashTransaction, FlexQueryResponse, FlexStatement, Trade

# IBKR Date/Time Formats
# Dates: yyyyMMdd or yyyy-MM-dd
# Times: HHmmss or HH:mm:ss
# Datetime: date;time (semicolon separator)
from .utils import parse_bool, parse_date, parse_datetime, parse_decimal, parse_time


def clean_attributes(attrs: dict[str, str], model_class: type[BaseModel]) -> dict[str, Any]:
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
    cash_reports = []

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
            # Pydantic should handle string to Enum if values match
            cash_transactions.append(CashTransaction(**cash_attrs))


    # Parse CashReports (official tag: CashReportCurrency)
    cash_report_container = elem.find("CashReport")
    if cash_report_container is not None:
        for cash_report_elem in cash_report_container.findall("CashReportCurrency"):
            cash_report_attrs = clean_attributes(
                cash_report_elem.attrib, CashReportCurrency
            )
            cash_reports.append(CashReportCurrency(**cash_report_attrs))
        
        # Backward compatibility / fallback for non-standard files
        if not cash_reports:
             for tag in ["CashReport", "CashReportInfo"]:
                 for cash_report_elem in cash_report_container.findall(tag):
                    cash_report_attrs = clean_attributes(
                        cash_report_elem.attrib, CashReportCurrency
                    )
                    cash_reports.append(CashReportCurrency(**cash_report_attrs))

    attrs["Trades"] = trades
    attrs["CashTransactions"] = cash_transactions
    attrs["CashReport"] = cash_reports

    return FlexStatement(**attrs)
