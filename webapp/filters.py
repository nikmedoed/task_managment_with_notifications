from database.models import BaseModel


def format_title(title: str) -> str:
    return f"{title} – " if title else ""


def link_format(obj: BaseModel, template):
    return template.format(**obj.to_dict())
