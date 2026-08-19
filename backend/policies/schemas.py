from uuid import UUID
from pydantic import BaseModel, Field

class PolicyCreate(BaseModel):
    organization_id: UUID
    policy_name: str = Field(min_length=1, max_length=150)
    policy_description: str = Field(min_length=1)
    related_service_id: UUID | None = None

class PolicyUpdate(BaseModel):
    policy_name: str | None = None
    policy_description: str | None = None
    related_service_id: UUID | None = None
