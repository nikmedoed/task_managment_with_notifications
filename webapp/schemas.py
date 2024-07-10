from pydantic import create_model
from sqlalchemy.inspection import inspect
from sqlalchemy import Column, String, Integer, Float, Boolean
from database.models import TaskType, Object, Organization


def sqlalchemy_to_pydantic_create(schema):
    mapper = inspect(schema)
    fields = {}
    for column in mapper.attrs:
        if isinstance(column, Column):
            python_type = column.type.python_type
            default_value = ... if column.nullable else None
            fields[column.key] = (python_type, default_value)
    return create_model(f'{schema.__name__}Create', **fields)


TaskTypeCreate = sqlalchemy_to_pydantic_create(TaskType)
OrganizationCreate = sqlalchemy_to_pydantic_create(Organization)
ObjectCreate = sqlalchemy_to_pydantic_create(Object)
