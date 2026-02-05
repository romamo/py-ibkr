from datetime import date, datetime, time
from decimal import Decimal


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
