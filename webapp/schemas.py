from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from database.models import Statuses


class ModelWithActive(BaseModel):
    active: Optional[bool] = True

    @field_validator('active', mode='before')
    def parse_bool(cls, v):
        if isinstance(v, str):
            if v.lower() == 'true':
                return True
            elif v.lower() == 'false':
                return False
        return v


class OrganizationCreate(ModelWithActive):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None


class TaskTypeCreate(ModelWithActive):
    name: str
    active: Optional[bool] = True


class ObjectCreate(ModelWithActive):
    name: str
    organization_id: int
    description: Optional[str] = None
    address: Optional[str] = None
    area_sq_meters: Optional[float] = None
    num_apartments: Optional[int] = None

    @field_validator('area_sq_meters', 'num_apartments', mode='before')
    def parse_number(cls, v):
        if not v:
            return None
        if isinstance(v, str):
            try:
                return float(v) if '.' in v else int(v)
            except ValueError:
                raise ValueError(f'Invalid value: {v}')
        return v


class UserSchema(BaseModel):
    last_name: str = Field(..., max_length=100)
    first_name: str = Field(..., max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr]
    phone_number: Optional[str] = Field(None, max_length=15)
    telegram_nick: Optional[str] = Field(None, max_length=50)
    position: str = Field(..., max_length=100)
    verificated: bool = False
    active: bool = True
    admin: bool = False

    @field_validator('verificated', 'active', 'admin', mode='before')
    def parse_bool(cls, v):
        if isinstance(v, str):
            if v.lower() == 'true':
                return True
            elif v.lower() == 'false':
                return False
        return v


class TaskCreate(BaseModel):
    task_type_id: int
    status: Statuses = Field(...)
    object_id: int
    supplier_id: int
    supervisor_id: int
    executor_id: int
    initial_plan_date: datetime
    description: str
    important: bool
    actual_plan_date: datetime = Field(None)

    @field_validator('status')
    def check_status(cls, value):
        if value not in {Statuses.DRAFT, Statuses.PLANNING}:
            raise ValueError("Должно быть 'Черновик' или 'Планирование'")
        return value

    @field_validator('actual_plan_date', mode='before')
    def set_actual_plan_date(cls, value, values):
        return values.get('initial_plan_date')
