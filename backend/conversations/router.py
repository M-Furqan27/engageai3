from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Conversation, Visitor

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def serialize_visitor(visitor):
    if not visitor:
        return None
    return {
        "visitor_id": str(visitor.visitor_id),
        "visitor_name": visitor.visitor_name,
        "visitor_email": visitor.visitor_email,
        "status": visitor.status,
        "interested_service": visitor.interested_service.service_name if visitor.interested_service else None,
        "sub_service_name": visitor.sub_service_name,
        "meeting_datetime": visitor.meeting_datetime,
        "created_at": visitor.created_at,
        "updated_at": visitor.updated_at,
    }


def serialize_conversation(conversation, include_messages=False):
    visitor = conversation.visitor
    last_message = conversation.messages[-1] if conversation.messages else None
    data = {
        "conversation_id": str(conversation.conversation_id),
        "visitor_id": str(conversation.visitor_id),
        "organization_id": str(conversation.organization_id),
        "started_at": conversation.started_at,
        "last_message_at": conversation.last_message_at,
        "visitor_name": visitor.visitor_name if visitor else None,
        "visitor_email": visitor.visitor_email if visitor else None,
        "visitor_status": visitor.status if visitor else None,
        "interested_service": visitor.interested_service.service_name if visitor and visitor.interested_service else None,
        "message_count": len(conversation.messages),
        "last_message_preview": last_message.message[:160] if last_message else None,
    }
    if include_messages:
        data["visitor"] = serialize_visitor(visitor)
        data["messages"] = [
            {
                "message_id": str(message.message_id),
                "sender": message.sender,
                "message": message.message,
                "created_at": message.created_at,
            }
            for message in conversation.messages
        ]
    return data


def serialize_visitor_history(visitor, include_messages=False):
    conversations = sorted(
        visitor.conversations,
        key=lambda row: row.started_at,
    )
    total_messages = sum(len(row.messages) for row in conversations)
    last_conversation = max(
        conversations,
        key=lambda row: row.last_message_at,
        default=None,
    )
    last_message = None
    if last_conversation and last_conversation.messages:
        last_message = last_conversation.messages[-1]

    data = {
        **serialize_visitor(visitor),
        "display_name": visitor.visitor_name or visitor.visitor_email or "Anonymous visitor",
        "anonymous_label": f"Visitor #{str(visitor.visitor_id).split('-')[0].upper()}",
        "conversation_count": len(conversations),
        "message_count": total_messages,
        "first_conversation_at": conversations[0].started_at if conversations else None,
        "last_message_at": last_conversation.last_message_at if last_conversation else None,
        "last_message_preview": last_message.message[:160] if last_message else None,
    }

    if include_messages:
        data["conversations"] = [
            serialize_conversation(conversation, include_messages=True)
            for conversation in conversations
        ]
    return data


@router.get("/organization/{organization_id}/visitors")
def list_visitor_histories(organization_id: UUID, db: Session = Depends(get_db)):
    """Return one inbox row per visitor, regardless of how many chat sessions they have."""
    visitors = (
        db.query(Visitor)
        .filter(Visitor.organization_id == organization_id)
        .all()
    )
    rows = [serialize_visitor_history(visitor) for visitor in visitors if visitor.conversations]
    rows.sort(
        key=lambda row: row["last_message_at"] or row["created_at"],
        reverse=True,
    )
    return rows


@router.get("/visitor/{visitor_id}")
def visitor_history(visitor_id: UUID, db: Session = Depends(get_db)):
    visitor = db.get(Visitor, visitor_id)
    if not visitor:
        raise HTTPException(404, "Visitor not found")
    return serialize_visitor_history(visitor, include_messages=True)


@router.get("/visitor/{visitor_id}/download")
def download_visitor_history(
    visitor_id: UUID,
    format: str = Query("txt", pattern="^(txt|json)$"),
    db: Session = Depends(get_db),
):
    visitor = db.get(Visitor, visitor_id)
    if not visitor:
        raise HTTPException(404, "Visitor not found")

    data = serialize_visitor_history(visitor, include_messages=True)
    if format == "json":
        return data

    display_name = visitor.visitor_name or visitor.visitor_email or "Anonymous visitor"
    lines = [
        f"Visitor: {display_name}",
        f"Visitor ID: {visitor.visitor_id}",
        f"Email: {visitor.visitor_email or 'Not provided'}",
        f"Status: {visitor.status}",
        f"Conversations: {data['conversation_count']}",
        "",
    ]

    for index, conversation in enumerate(data["conversations"], start=1):
        lines.extend(
            [
                "=" * 68,
                f"Conversation {index}",
                f"Started: {conversation['started_at'].isoformat() if conversation['started_at'] else 'Unknown'}",
                f"Last message: {conversation['last_message_at'].isoformat() if conversation['last_message_at'] else 'Unknown'}",
                "=" * 68,
            ]
        )
        for message in conversation["messages"]:
            lines.append(
                f"[{message['created_at'].isoformat()}] {message['sender'].upper()}: {message['message']}"
            )
        lines.extend(["", "--- Conversation paused here ---", ""])

    filename_name = (visitor.visitor_name or "anonymous-visitor").strip().lower().replace(" ", "-")
    return PlainTextResponse(
        "\n".join(lines),
        headers={
            "Content-Disposition": f'attachment; filename="{filename_name}-conversation-history.txt"'
        },
    )


@router.get("/detail/{conversation_id}")
def detail(conversation_id: UUID, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return serialize_conversation(conversation, True)


@router.get("/{conversation_id}/download")
def download(
    conversation_id: UUID,
    format: str = Query("txt", pattern="^(txt|json)$"),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    data = serialize_conversation(conversation, True)
    if format == "json":
        return data

    visitor_name = conversation.visitor.visitor_name if conversation.visitor else None
    visitor_email = conversation.visitor.visitor_email if conversation.visitor else None
    lines = [
        f"Conversation: {conversation.conversation_id}",
        f"Visitor: {visitor_name or conversation.visitor_id}",
        f"Email: {visitor_email or 'Not provided'}",
        "",
    ]
    for message in conversation.messages:
        lines.append(
            f"[{message.created_at.isoformat()}] {message.sender.upper()}: {message.message}"
        )

    return PlainTextResponse(
        "\n".join(lines),
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{conversation.conversation_id}.txt"'
        },
    )


@router.get("/{organization_id}")
def list_conversations(organization_id: UUID, db: Session = Depends(get_db)):
    """Legacy endpoint kept for compatibility with older portal builds."""
    rows = (
        db.query(Conversation)
        .filter(Conversation.organization_id == organization_id)
        .order_by(Conversation.last_message_at.desc())
        .all()
    )
    return [serialize_conversation(row) for row in rows]
