from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from ..database.db import SessionLocal
from ..database.models import ChatMessage, ChatSession
from .case_profile_v2 import CaseProfileV2, create_case_profile_v2


class MemoryManager:
    """
    Production-grade hybrid memory manager:
    Fast in-memory cache + persistent database backing for conversation history,
    workflow state machine, and Case Profile V2.
    Survives server restarts, worker restarts, and process crashes.
    """

    def __init__(self, max_message: int = 15):
        self.max_message = max_message
        self.messages: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_message))
        self.state: Dict[str, dict] = defaultdict(dict)
        self.profiles: Dict[str, CaseProfileV2] = {}

    def _get_db(self):
        return SessionLocal()

    def add_user_message(self, session_id: str, message: str):
        self.messages[session_id].append({
            "role": "user",
            "content": message,
        })

    def add_ai_message(self, session_id: str, message: str):
        self.messages[session_id].append({
            "role": "assistant",
            "content": message,
        })

    def get_history(self, session_id: str) -> List[dict]:
        # If in cache, return
        if session_id in self.messages and len(self.messages[session_id]) > 0:
            return list(self.messages[session_id])

        # Otherwise recover from persistent DB
        db = self._get_db()
        try:
            db_msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.desc())
                .limit(self.max_message)
                .all()
            )
            recovered = []
            for m in reversed(db_msgs):
                recovered.append({"role": m.sender, "content": m.message})
                self.messages[session_id].append({"role": m.sender, "content": m.message})
            return recovered
        except Exception:
            return []
        finally:
            db.close()

    def set_state(self, session_id: str, key: str, value: Any):
        self.state[session_id][key] = value

        # Persist to database
        db = self._get_db()
        try:
            sess = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if sess:
                sess_state = json.loads(sess.state_json or "{}") if sess.state_json else {}
                # Filter out non-serializable objects
                try:
                    sess_state[key] = value
                    sess.state_json = json.dumps(sess_state)
                    db.commit()
                except (TypeError, ValueError):
                    pass
        except Exception:
            db.rollback()
        finally:
            db.close()

    def get_state(self, session_id: str, key: str, default: Any = None) -> Any:
        if session_id in self.state and key in self.state[session_id]:
            return self.state[session_id][key]

        # Try recovering from DB
        db = self._get_db()
        try:
            sess = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if sess and sess.state_json:
                db_state = json.loads(sess.state_json)
                self.state[session_id] = db_state
                return db_state.get(key, default)
        except Exception:
            pass
        finally:
            db.close()

        return default

    def get_all_state(self, session_id: str) -> dict:
        if session_id not in self.state or not self.state[session_id]:
            db = self._get_db()
            try:
                sess = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
                if sess and sess.state_json:
                    self.state[session_id] = json.loads(sess.state_json)
            except Exception:
                pass
            finally:
                db.close()
        return self.state[session_id]

    def clear(self, session_id: str):
        self.messages.pop(session_id, None)
        self.state.pop(session_id, None)
        self.profiles.pop(session_id, None)

    def set_case_profile(self, session_id: str, profile: Any):
        if isinstance(profile, CaseProfileV2):
            self.profiles[session_id] = profile
            profile_dict = profile.model_dump()
        elif isinstance(profile, dict):
            profile_dict = profile
        else:
            profile_dict = {}

        self.state[session_id]["case_profile"] = profile_dict

        # Persist to database
        db = self._get_db()
        try:
            sess = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if sess:
                sess.case_profile_json = json.dumps(profile_dict)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def get_case_profile(self, session_id: str) -> dict:
        if session_id in self.profiles:
            return self.profiles[session_id].to_legacy_dict()

        # Try recovering from state
        db_profile = None
        if session_id in self.state and "case_profile" in self.state[session_id]:
            prof = self.state[session_id]["case_profile"]
            if isinstance(prof, dict):
                db_profile = prof

        # Try recovering from DB
        if not db_profile:
            db = self._get_db()
            try:
                sess = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
                if sess and sess.case_profile_json:
                    db_profile = json.loads(sess.case_profile_json)
            except Exception:
                pass
            finally:
                db.close()

        if db_profile:
            try:
                v2 = CaseProfileV2.model_validate(db_profile)
                self.profiles[session_id] = v2
                return v2.to_legacy_dict()
            except Exception:
                return db_profile

        return {}

    def get_case_profile_v2(self, session_id: str) -> CaseProfileV2:
        if session_id in self.profiles:
            return self.profiles[session_id]

        profile_dict = self.get_case_profile(session_id)
        if profile_dict:
            try:
                prof = CaseProfileV2.model_validate(profile_dict)
                self.profiles[session_id] = prof
                return prof
            except Exception:
                pass

        new_prof = create_case_profile_v2()
        self.profiles[session_id] = new_prof
        return new_prof