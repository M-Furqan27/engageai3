from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class OrganizationCreate(BaseModel):
    user_id: UUID
    organization_name: str = Field(min_length=1, max_length=150)
    short_description: str = Field(min_length=1)
    organization_type: str = Field(min_length=1, max_length=150)

    @field_validator("organization_name", "short_description", "organization_type")
    @classmethod
    def trim(cls, value): return value.strip()


class OrganizationUpdate(BaseModel):
    organization_name: str | None = None
    short_description: str | None = None
    organization_type: str | None = None
    landing_page_enabled: bool | None = None


class CompleteOnboardingRequest(BaseModel):
    user_id: UUID
