from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from workflows.n8n_client import n8n_client

router=APIRouter(prefix="/tools",tags=["Agent Meeting Tools"])
class ToolPayload(BaseModel):
    organization_id: str
    visitor_id: str
    name: str
    email: str
    service_name: str
    sub_service_name: str | None = None
    service_required_info: dict = Field(default_factory=dict)
    slot_start: str | None = None
    slot_end: str | None = None
    meeting_datetime: str | None = None

@router.post("/check-slots")
def check_slots(payload: ToolPayload):
    try: return n8n_client.check_slots(payload.model_dump(exclude_none=True))
    except Exception as exc: raise HTTPException(502,str(exc)) from exc

@router.post("/create-meeting")
def create_meeting(payload: ToolPayload):
    if not payload.slot_start or not payload.slot_end: raise HTTPException(400,"slot_start and slot_end are required")
    try: return n8n_client.create_meeting(payload.model_dump(exclude_none=True))
    except Exception as exc: raise HTTPException(502,str(exc)) from exc


