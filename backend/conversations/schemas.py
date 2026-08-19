from uuid import UUID
from pydantic import BaseModel, Field

class StartConversationRequest(BaseModel):
    organization_id: UUID
    visitor_id: UUID | None = None

class ChatMessageRequest(BaseModel):
    organization_id: UUID
    visitor_id: UUID
    conversation_id: UUID
    message: str = Field(min_length=1)
