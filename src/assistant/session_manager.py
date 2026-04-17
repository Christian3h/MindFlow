import time
from typing import Optional
from dataclasses import dataclass, field
import json


SESSION_TTL_SECONDS = 300


@dataclass
class Message:
    role: str
    content: str
    intent: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    user_id: str
    messages: list[Message] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)
    intent_history: list[str] = field(default_factory=list)
    pending_expenses: list[dict] = field(default_factory=list)


class SessionManager:
    def __init__(self, ttl: int = SESSION_TTL_SECONDS):
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl

    def get_session(self, user_id: str) -> Session:
        now = time.time()
        if user_id in self._sessions:
            session = self._sessions[user_id]
            if now - session.last_activity > self._ttl:
                del self._sessions[user_id]
                return self._create_session(user_id)
            session.last_activity = now
            return session
        return self._create_session(user_id)

    def _create_session(self, user_id: str) -> Session:
        session = Session(user_id=user_id)
        self._sessions[user_id] = session
        return session

    def add_message(self, user_id: str, role: str, content: str, intent: Optional[str] = None):
        session = self.get_session(user_id)
        message = Message(role=role, content=content, intent=intent)
        session.messages.append(message)
        if intent:
            session.intent_history.append(intent)
        session.last_activity = time.time()

    def get_conversation_history(self, user_id: str, limit: int = 10) -> list[dict]:
        session = self.get_session(user_id)
        recent = session.messages[-limit:]
        return [{"role": m.role, "content": m.content} for m in recent]

    def get_context(self, user_id: str) -> dict:
        session = self.get_session(user_id)
        return session.context.copy()

    def update_context(self, user_id: str, key: str, value):
        session = self.get_session(user_id)
        session.context[key] = value

    def get_last_intent(self, user_id: str) -> Optional[str]:
        session = self.get_session(user_id)
        return session.intent_history[-1] if session.intent_history else None

    def set_pending_expenses(self, user_id: str, expenses: list[dict]):
        session = self.get_session(user_id)
        session.pending_expenses = expenses

    def get_pending_expenses(self, user_id: str) -> list[dict]:
        session = self.get_session(user_id)
        return session.pending_expenses

    def clear_pending_expenses(self, user_id: str):
        session = self.get_session(user_id)
        session.pending_expenses = []

    def clear_session(self, user_id: str):
        if user_id in self._sessions:
            del self._sessions[user_id]


_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
