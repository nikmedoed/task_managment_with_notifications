from pydantic import create_model
from sqlalchemy.inspection import inspect
from database.models import TaskType, Object, Organization
from sqlalchemy import Column


def sqlalchemy_to_pydantic_create(schema):
    mapper = inspect(schema)
    fields = {column.key: (column.type.python_type, ...) for column in mapper.attrs if isinstance(column, Column)}
    return create_model(f'{schema.__name__}Create', **fields)


TaskTypeCreate = sqlalchemy_to_pydantic_create(TaskType)
OrganizationCreate = sqlalchemy_to_pydantic_create(Organization)
ObjectCreate = sqlalchemy_to_pydantic_create(Object)
