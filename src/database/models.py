from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    phone = Column(String(20), index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    emergency_contact = Column(String(50), nullable=True)
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    firs = relationship("FIRRecord", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("DocumentAnalysisRecord", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(255), default="Emergency Cyber Consultation")
    workflow = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)
    state_json = Column(Text, default="{}")
    case_profile_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id")



class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.session_id"), index=True, nullable=False)
    sender = Column(String(20), nullable=False)  # "user" | "assistant"
    message = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    workflow = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)
    confidence = Column(Float, default=1.0)
    sources_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=utcnow)

    session = relationship("ChatSession", back_populates="messages")

    @property
    def sources(self):
        try:
            return json.loads(self.sources_json or "[]")
        except Exception:
            return []

    @sources.setter
    def sources(self, value):
        self.sources_json = json.dumps(value or [])


class FIRRecord(Base):
    __tablename__ = "fir_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    incident_type = Column(String(50), default="unknown")
    complainant_name = Column(String(120), default="")
    form_data_json = Column(Text, default="{}")
    status = Column(String(30), default="draft")  # "draft" | "incomplete" | "ready" | "filed"
    fir_draft_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="firs")

    @property
    def form_data(self):
        try:
            return json.loads(self.form_data_json or "{}")
        except Exception:
            return {}

    @form_data.setter
    def form_data(self, value):
        self.form_data_json = json.dumps(value or {})


class DocumentAnalysisRecord(Base):
    __tablename__ = "document_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(100), default="Unknown")
    confidence = Column(Float, default=0.0)
    language = Column(String(50), default="English")
    risk_level = Column(String(30), default="Low")
    summary = Column(Text, default="")
    important_points_json = Column(Text, default="[]")
    recommended_actions_json = Column(Text, default="[]")
    legal_guidance_json = Column(Text, default="null")
    ocr_text = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="documents")

    @property
    def important_points(self):
        try:
            return json.loads(self.important_points_json or "[]")
        except Exception:
            return []

    @property
    def recommended_actions(self):
        try:
            return json.loads(self.recommended_actions_json or "[]")
        except Exception:
            return []

    @property
    def legal_guidance(self):
        try:
            return json.loads(self.legal_guidance_json or "null")
        except Exception:
            return None


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    file_id = Column(String(64), unique=True, index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_hash = Column(String(64), index=True, nullable=False)  # SHA-256
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    ocr_text = Column(Text, default="")
    extracted_entities_json = Column(Text, default="{}")
    timeline_events_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", backref="evidence_records")

