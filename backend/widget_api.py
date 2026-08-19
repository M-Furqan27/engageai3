import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from agent.main_agent import main_agent
from conversations.service import start_conversation
from database.database import get_db
from database.models import Conversation, Organization, Visitor
from visitors.service import update_from_message

router = APIRouter(prefix="/widget", tags=["Widget / Agent"])


class WidgetStartRequest(BaseModel):
    organization_id: UUID
    visitor_id: UUID | None = None


class WidgetChatRequest(BaseModel):
    organization_id: UUID
    visitor_id: UUID
    conversation_id: UUID
    message: str = Field(min_length=1)


@router.get("/embed.js")
def embed_widget(
    organization_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return a one-link bootstrap script for an organization chatbot."""
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(404, "Organization not found")

    api_base = str(request.base_url).rstrip("/")
    config = {
        "organizationId": str(organization.organization_id),
        "organizationName": organization.organization_name,
        "apiBaseUrl": api_base,
        "widgetCssUrl": f"{api_base}/widget-assets/widget.css",
    }
    widget_js_url = f"{api_base}/widget-assets/widget.js"

    # JSON encoding keeps organization names and URLs safe inside JavaScript.
    script = f"""
(function () {{
  if (window.__ENGAGEAI_WIDGET_LOADED__) return;
  window.__ENGAGEAI_WIDGET_LOADED__ = true;
  window.ENGAGEAI_WIDGET_CONFIG = Object.assign(
    {{}},
    window.ENGAGEAI_WIDGET_CONFIG || {{}},
    {json.dumps(config)}
  );
  var script = document.createElement('script');
  script.src = {json.dumps(widget_js_url)};
  script.async = true;
  document.head.appendChild(script);
}})();
""".strip()

    return Response(
        content=script,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/start")
def start(payload: WidgetStartRequest, db: Session = Depends(get_db)):
    try:
        visitor, conversation = start_conversation(db, payload.organization_id, payload.visitor_id)
        return {
            "visitor_id": str(visitor.visitor_id),
            "conversation_id": str(conversation.conversation_id),
            "status": visitor.status,
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/chat")
def chat(payload: WidgetChatRequest, db: Session = Depends(get_db)):
    visitor = db.get(Visitor, payload.visitor_id)
    conv = db.get(Conversation, payload.conversation_id)
    if not visitor or visitor.organization_id != payload.organization_id:
        raise HTTPException(404, "Visitor not found")
    if not conv or conv.visitor_id != visitor.visitor_id:
        raise HTTPException(404, "Conversation not found")

    last_agent = next((m.message for m in reversed(conv.messages) if m.sender == "agent"), None)

    # This may return an existing visitor when the submitted email matches a
    # previous visitor. The current conversation is re-parented automatically.
    visitor = update_from_message(db, visitor, payload.message, last_agent)
    db.refresh(conv)

    try:
        response = main_agent.chat(
            payload.organization_id,
            visitor.visitor_id,
            conv.conversation_id,
            payload.message,
        )
        db.refresh(visitor)
        return {
            "conversation_id": str(conv.conversation_id),
            "visitor_id": str(visitor.visitor_id),
            "response": response,
            "status": visitor.status,
        }
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: UUID, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return {
        "conversation_id": str(conv.conversation_id),
        "messages": [
            {"sender": m.sender, "message": m.message, "created_at": m.created_at}
            for m in conv.messages
        ],
    }
