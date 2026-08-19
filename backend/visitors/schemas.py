from uuid import UUID
from pydantic import BaseModel

class VisitorStatusUpdate(BaseModel):
    status: str

class VisitorContextUpdate(BaseModel):
    visitor_name: str | None = None
    visitor_email: str | None = None
    interested_service_id: UUID | None = None
    sub_service_name: str | None = None
    service_required_info: dict | None = None
