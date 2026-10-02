from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agents.shared_agents import coordinator
from ..database.db import get_db
from ..database.models import ChatMessage, ChatSession, User
from ..services.auth_service import get_current_user, get_optional_user

router = APIRouter()
agent = coordinator


from ..security.auth_guard import verify_session_ownership

# ==========================================================
# Schemas
# ==========================================================

class ChatRequest(BaseModel):
    session_id: str = Field(..., example="session-123456")
    message: str = Field(..., example="I lost 15000 Rs in a UPI scam. What should I do?")


class Source(BaseModel):
    title: str
    page: int | str
    url: Optional[str] = None
    authority_level: Optional[int] = 1


class ResponseData(BaseModel):
    intent: str
    workflow: str
    category: str
    confidence: float
    response: str
    sources: list[Source] = Field(default_factory=list)
    # V2 Structured Fields
    response_type: Optional[str] = "advice"
    urgency: Optional[str] = "standard"
    actions: List[str] = Field(default_factory=list)
    evidence_needed: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    verification: Optional[dict] = None


class ChatResponse(BaseModel):
    success: bool
    message: str
    data: ResponseData
    timestamp: datetime



class MessageItem(BaseModel):
    id: int
    sender: str
    message: str
    intent: Optional[str] = None
    workflow: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[float] = None
    sources: List[dict] = Field(default_factory=list)
    created_at: datetime


class SessionItem(BaseModel):
    session_id: str
    title: str
    workflow: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int


from ..security.rate_limiter import rate_limit
from ..security.sanitizer import sanitize_input


from fastapi.responses import StreamingResponse

# ==========================================================
# Chat Processing
# ==========================================================

@router.post(
    "/",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))],
    summary="Send a message to the AI Coordinator (Rate Limit: 20/min)",
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session_id = sanitize_input(request.session_id).strip()
    user_msg = sanitize_input(request.message).strip()

    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    # 1. Get or create session in DB
    db_session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not db_session:
        title_snippet = (user_msg[:45] + "...") if len(user_msg) > 45 else user_msg
        db_session = ChatSession(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            title=title_snippet,
        )
        db.add(db_session)
        db.commit()
    else:
        # Check ownership if owned by a registered user
        if db_session.user_id is not None:
            verify_session_ownership(db_session, current_user)
        elif current_user and db_session.user_id is None:
            db_session.user_id = current_user.id
            db.commit()

    # 2. Save user message in DB
    user_chat_record = ChatMessage(
        session_id=session_id,
        sender="user",
        message=user_msg,
    )
    db.add(user_chat_record)
    db.commit()

    # 3. Process with Multi-Agent Coordinator
    result = agent.handle(
        session_id,
        user_msg,
    )

    # 4. Save AI message in DB
    ai_response_text = result.get("response", "")
    sources = result.get("sources", [])

    ai_chat_record = ChatMessage(
        session_id=session_id,
        sender="assistant",
        message=ai_response_text,
        intent=result.get("intent", "advice"),
        workflow=result.get("workflow", "advisor"),
        category=result.get("category", "general"),
        confidence=result.get("confidence", 1.0),
        sources_json=json.dumps(sources),
    )
    db.add(ai_chat_record)

    # Update session workflow / category
    db_session.workflow = result.get("workflow")
    db_session.category = result.get("category")
    db_session.updated_at = datetime.utcnow()
    db.commit()

    # Format sources
    formatted_sources = []
    for s in sources:
        if isinstance(s, dict):
            formatted_sources.append(
                Source(
                    title=str(s.get("title", "Government Guidelines")),
                    page=s.get("page", "1"),
                    url=s.get("url"),
                    authority_level=s.get("authority_level", 1),
                )
            )
        else:
            formatted_sources.append(Source(title=str(s), page="1"))

    return ChatResponse(
        success=True,
        message="Request processed successfully.",
        data=ResponseData(
            intent=result.get("intent", "advice"),
            workflow=result.get("workflow", "advisor"),
            category=result.get("category", "general"),
            confidence=float(result.get("confidence", 1.0)),
            response=ai_response_text,
            sources=formatted_sources,
            response_type=result.get("response_type", "advice"),
            urgency=result.get("urgency", "standard"),
            actions=result.get("actions", []),
            evidence_needed=result.get("evidence_needed", []),
            next_action=result.get("next_action"),
            verification=result.get("verification"),
        ),
        timestamp=datetime.now(),
    )



@router.post(
    "/stream",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))],
    summary="Send a message to AI Coordinator and stream tokens in real-time via SSE",
)
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session_id = sanitize_input(request.session_id).strip()
    user_msg = sanitize_input(request.message).strip()

    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    # 1. Get or create session in DB
    db_session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not db_session:
        title_snippet = (user_msg[:45] + "...") if len(user_msg) > 45 else user_msg
        db_session = ChatSession(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            title=title_snippet,
        )
        db.add(db_session)
        db.commit()
    else:
        if db_session.user_id is not None:
            verify_session_ownership(db_session, current_user)
        elif current_user and db_session.user_id is None:
            db_session.user_id = current_user.id
            db.commit()

    # 2. Save user message in DB
    user_chat_record = ChatMessage(
        session_id=session_id,
        sender="user",
        message=user_msg,
    )
    db.add(user_chat_record)
    db.commit()

    # 3. Stream generator
    def sse_event_generator():
        for chunk in agent.handle_stream(session_id, user_msg):
            yield chunk

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==========================================================
# User Chat Sessions & History Endpoints
# ==========================================================

@router.get(
    "/sessions",
    response_model=List[SessionItem],
    summary="Get all chat sessions for the authenticated user",
)
def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    result = []
    for s in sessions:
        msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == s.session_id).count()
        result.append(
            SessionItem(
                session_id=s.session_id,
                title=s.title,
                workflow=s.workflow,
                category=s.category,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=msg_count,
            )
        )

    return result


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[MessageItem],
    summary="Get complete message history for a chat session",
)
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    db_session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if db_session:
        verify_session_ownership(db_session, current_user)

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .all()
    )

    return [

        MessageItem(
            id=m.id,
            sender=m.sender,
            message=m.message,
            intent=m.intent,
            workflow=m.workflow,
            category=m.category,
            confidence=m.confidence,
            sources=m.sources,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete(
    "/sessions/{session_id}",
    summary="Delete a chat session and its history",
)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    db_session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    # If owned by a user, verify ownership
    if db_session.user_id and current_user and db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this session.",
        )

    # Delete messages and session
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(db_session)
    db.commit()

    return {
        "success": True,
        "message": f"Session {session_id} and its history deleted.",
    }