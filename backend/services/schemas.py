from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class ServiceCreate(BaseModel):
    organization_id: UUID
    service_name: str = Field(min_length=1, max_length=150)
    sub_service_name: str | None = None
    service_description: str = Field(min_length=1)
    service_price: Decimal | None = None
    service_requirements: str = Field(min_length=1)

class ServiceUpdate(BaseModel):
    service_name: str | None = None
    sub_service_name: str | None = None
    service_description: str | None = None
    service_price: Decimal | None = None
    service_requirements: str | None = None
