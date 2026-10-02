from __future__ import annotations

from typing import Optional
from fastapi import HTTPException, status
from ..database.models import ChatSession, FIRRecord, User


def verify_session_ownership(
    db_session: Optional[ChatSession],
    current_user: Optional[User],
) -> None:
    """
    Guards against Insecure Direct Object References (IDOR) and session hijacking.
    Verifies that the session belongs to the requesting user.
    """
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )

    # If the session belongs to a registered user
    if db_session.user_id is not None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this private consultation session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if db_session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to access another victim's session.",
            )


def verify_fir_ownership(
    record: Optional[FIRRecord],
    current_user: Optional[User],
) -> None:
    """
    Guards FIR records and downloadable legal PDFs against IDOR attacks.
    """
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIR complaint record not found.",
        )

    if record.user_id is not None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access or download this FIR draft.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot access or download another victim's FIR complaint.",
            )
