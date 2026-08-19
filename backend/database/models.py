import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_type = Column(String(150), nullable=False)
    organization_name = Column(String(150), nullable=False)
    short_description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    landing_page_enabled = Column(Boolean, nullable=False, default=False)

    users = relationship("User", back_populates="organization")
    services = relationship("Service", back_populates="organization", cascade="all, delete-orphan")
    policies = relationship("Policy", back_populates="organization", cascade="all, delete-orphan")
    knowledge_documents = relationship("KnowledgeDocument", back_populates="organization", cascade="all, delete-orphan")
    visitors = relationship("Visitor", back_populates="organization", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="SET NULL"), nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="users")


class Service(Base):
    __tablename__ = "services"

    service_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    service_name = Column(String(150), nullable=False)
    sub_service_name = Column(String(150), nullable=True)
    service_description = Column(Text, nullable=False)
    service_price = Column(Numeric(12, 2), nullable=True)
    service_requirements = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="services")
    policies = relationship("Policy", back_populates="related_service")
    interested_visitors = relationship("Visitor", back_populates="interested_service")


class Policy(Base):
    __tablename__ = "policies"

    policy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    policy_name = Column(String(150), nullable=False)
    policy_description = Column(Text, nullable=False)
    related_service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="policies")
    related_service = relationship("Service", back_populates="policies")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    document_type = Column(String(50), nullable=False, default="general")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="knowledge_documents")


class Visitor(Base):
    __tablename__ = "visitors"

    visitor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_name = Column(String(150), nullable=True)
    visitor_email = Column(String(255), nullable=True)
    interested_service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id", ondelete="SET NULL"), nullable=True)
    sub_service_name = Column(String(150), nullable=True)
    service_required_info = Column(JSONB, nullable=True)
    meeting_datetime = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="Visitor", index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="visitors")
    interested_service = relationship("Service", back_populates="interested_visitors")
    conversations = relationship("Conversation", back_populates="visitor", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visitor_id = Column(UUID(as_uuid=True), ForeignKey("visitors.visitor_id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_message_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    visitor = relationship("Visitor", back_populates="conversations")
    organization = relationship("Organization", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
