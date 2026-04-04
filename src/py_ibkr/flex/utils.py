from datetime import date, datetime, time
from decimal import Decimal


def parse_date(value: str) -> date | None:
    if not value or value in ("0", "N/A", ""):
        return None

    if len(value) == 8:
        return datetime.strptime(value, "%Y%m%d").date()
    if "-" in value:
        return datetime.strptime(value, "%Y-%m-%d").date()

    raise ValueError(f"Unsupported date format: {value}")


def parse_time(value: str) -> time | None:
    if not value or value in ("0", "N/A", ""):
        return None

    if len(value) == 6:
        return datetime.strptime(value, "%H%M%S").time()
    if ":" in value:
        return datetime.strptime(value, "%H:%M:%S").time()

    raise ValueError(f"Unsupported time format: {value}")


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
        raise ValueError(f"Unsupported datetime format: {value}")
    # Handle comma separator (legacy)
    if "," in value:
        d_str, t_str = value.split(",")
        d = parse_date(d_str)
        t = parse_time(t_str.strip())
        if d and t:
            return datetime.combine(d, t)
    # Handle single string format if applicable
    if len(value) == 8:  # Just date?
        d = parse_date(value)
        if d:
            return datetime.combine(d, time.min)

    raise ValueError(f"Unsupported datetime format: {value}")


def parse_bool(value: str) -> bool | None:
    if not value:
        return None
    upper = value.upper()
    if upper == "Y":
        return True
    if upper == "N":
        return False
    raise ValueError(f"Unsupported boolean format: {value}")


def parse_decimal(value: str) -> Decimal | None:
    if not value or value in ("N/A", ""):
        return None
    return Decimal(value.replace(",", ""))
