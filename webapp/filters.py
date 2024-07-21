from datetime import datetime

from database.models import BaseModel


def format_title(title: str) -> str:
    return f"{title} – " if title else ""


def link_format(obj: BaseModel, template):
    return template.format(**obj.to_dict())


def format_date_diff(actual_date: datetime, initial_date: datetime) -> str:
    if not actual_date or not initial_date:
        return str(actual_date)
    days_diff = (actual_date - initial_date).days
    if days_diff == 0:
        return str(actual_date)
    return f"{actual_date} ({days_diff:+})"
