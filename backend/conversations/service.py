from datetime import datetime, timezone
from database.models import Conversation, Message, Visitor


def utc_now(): return datetime.now(timezone.utc)

def start_conversation(db, organization_id, visitor_id=None):
    visitor = db.get(Visitor, visitor_id) if visitor_id else None
    if visitor and visitor.organization_id != organization_id: raise ValueError("Visitor does not belong to organization")
    if not visitor:
        visitor=Visitor(organization_id=organization_id, status="Visitor"); db.add(visitor); db.flush()
    conversation=Conversation(visitor_id=visitor.visitor_id, organization_id=organization_id)
    db.add(conversation); db.commit(); db.refresh(visitor); db.refresh(conversation)
    return visitor, conversation

def add_message(db, conversation_id, sender, text):
    if sender not in {"visitor","agent"}: raise ValueError("sender must be visitor or agent")
    conv=db.get(Conversation, conversation_id)
    if not conv: raise ValueError("Conversation not found")
    msg=Message(conversation_id=conversation_id,sender=sender,message=text)
    conv.last_message_at=utc_now(); db.add(msg); db.commit(); db.refresh(msg); return msg

def history(db, conversation_id):
    conv=db.get(Conversation, conversation_id)
    if not conv: raise ValueError("Conversation not found")
    return conv.messages
