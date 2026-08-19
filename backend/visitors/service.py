import re
from datetime import datetime

from sqlalchemy import func

from database.models import Conversation, Service, Visitor

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
INTEREST_TERMS = (
    "price", "cost", "requirements", "requirement", "details", "proceed",
    "book", "appointment", "buy", "purchase", "use this service", "interested",
)
STATUS_PRIORITY = {"Visitor": 0, "Needs Follow-Up": 1, "Meeting Scheduled": 2}


def serialize(v):
    return {
        "visitor_id": str(v.visitor_id), "organization_id": str(v.organization_id),
        "visitor_name": v.visitor_name, "visitor_email": v.visitor_email,
        "interested_service_id": str(v.interested_service_id) if v.interested_service_id else None,
        "interested_service": v.interested_service.service_name if v.interested_service else None,
        "sub_service_name": v.sub_service_name, "service_required_info": v.service_required_info,
        "meeting_datetime": v.meeting_datetime, "status": v.status, "created_at": v.created_at, "updated_at": v.updated_at,
    }


def _merge_duplicate_email_visitor(db, visitor: Visitor):
    """Merge a temporary visitor into an existing visitor when the same email is provided.

    This keeps cross-session/cross-device chats together under one visitor inbox card.
    """
    if not visitor.visitor_email:
        return visitor

    normalized_email = visitor.visitor_email.strip().lower()
    existing = (
        db.query(Visitor)
        .filter(
            Visitor.organization_id == visitor.organization_id,
            Visitor.visitor_id != visitor.visitor_id,
            func.lower(Visitor.visitor_email) == normalized_email,
        )
        .order_by(Visitor.created_at.asc())
        .first()
    )
    if not existing:
        visitor.visitor_email = normalized_email
        return visitor

    # Prefer newly captured identity/details while preserving older useful data.
    existing.visitor_name = visitor.visitor_name or existing.visitor_name
    existing.visitor_email = normalized_email
    existing.interested_service_id = visitor.interested_service_id or existing.interested_service_id
    existing.sub_service_name = visitor.sub_service_name or existing.sub_service_name
    existing.service_required_info = visitor.service_required_info or existing.service_required_info
    existing.meeting_datetime = visitor.meeting_datetime or existing.meeting_datetime
    if STATUS_PRIORITY.get(visitor.status, 0) > STATUS_PRIORITY.get(existing.status, 0):
        existing.status = visitor.status

    # Re-parent every current session to the established visitor record.
    (
        db.query(Conversation)
        .filter(Conversation.visitor_id == visitor.visitor_id)
        .update({Conversation.visitor_id: existing.visitor_id}, synchronize_session=False)
    )
    db.flush()
    db.delete(visitor)
    db.commit()
    db.refresh(existing)
    return existing


def update_from_message(db, visitor: Visitor, message: str, last_agent_message: str | None = None):
    email = EMAIL_RE.search(message)
    if email:
        visitor.visitor_email = email.group(0).lower()

    name_match = re.search(r"\b(?:my name is|name is|i am|i'm)\s+([A-Za-z][A-Za-z .'-]{1,80})", message, re.I)
    if name_match:
        candidate = name_match.group(1).strip().rstrip('.,')
        # Avoid treating common conversational phrases as names.
        blocked = {"interested", "looking", "trying", "here", "fine", "good"}
        if '@' not in candidate and candidate.lower().split()[0] not in blocked and len(candidate.split()) <= 5:
            visitor.visitor_name = candidate
    elif not visitor.visitor_name and last_agent_message and "name" in last_agent_message.lower():
        candidate = message.strip().rstrip('.,')
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,80}", candidate) and len(candidate.split()) <= 5:
            visitor.visitor_name = candidate

    services = db.query(Service).filter(Service.organization_id == visitor.organization_id).all()
    low = message.lower()
    for service in services:
        if service.service_name.lower() in low or (service.sub_service_name and service.sub_service_name.lower() in low):
            visitor.interested_service_id = service.service_id
            if service.sub_service_name and service.sub_service_name.lower() in low:
                visitor.sub_service_name = service.sub_service_name
            break

    if visitor.status == "Visitor" and (visitor.interested_service_id or any(term in low for term in INTEREST_TERMS)):
        visitor.status = "Needs Follow-Up"

    db.commit()
    db.refresh(visitor)
    return _merge_duplicate_email_visitor(db, visitor)


def set_meeting_scheduled(db, visitor: Visitor, slot_start: str):
    try:
        visitor.meeting_datetime = datetime.fromisoformat(slot_start.replace('Z', '+00:00'))
    except Exception:
        visitor.meeting_datetime = None
    visitor.status = "Meeting Scheduled"
    db.commit()
    db.refresh(visitor)
