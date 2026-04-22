from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ChatTurn:
    role: str
    text: str
    created_at: str


@dataclass(slots=True)
class ChatSession:
    session_id: str
    created_at: str
    updated_at: str
    memory_id: str = ""
    latest_response_id: str | None = None
    turns: list[ChatTurn] = field(default_factory=list)

    def add_turn(self, role: str, text: str) -> None:
        now = utc_now_iso()
        self.turns.append(ChatTurn(role=role, text=text, created_at=now))
        self.updated_at = now

    def to_dict(self) -> dict:
        data = asdict(self)
        data["turns"] = [asdict(turn) for turn in self.turns]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        turns = [ChatTurn(**turn) for turn in data.get("turns", [])]
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            memory_id=data.get("memory_id", ""),
            latest_response_id=data.get("latest_response_id"),
            turns=turns,
        )


class SessionStore:
    def __init__(self, session_dir: Path) -> None:
        self._session_dir = session_dir
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def create(self, *, memory_id: str | None = None) -> ChatSession:
        now = utc_now_iso()
        session_id = uuid.uuid4().hex
        session = ChatSession(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            memory_id=memory_id or f"session:{session_id}",
        )
        self.save(session)
        return session

    def get(self, session_id: str) -> ChatSession | None:
        path = self._path_for(session_id)
        if not path.exists():
            return None
        return ChatSession.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def get_or_create(self, session_id: str | None, *, memory_id: str | None = None) -> ChatSession:
        if session_id:
            existing = self.get(session_id)
            if existing:
                if memory_id and existing.memory_id != memory_id:
                    existing.memory_id = memory_id
                    self.save(existing)
                elif not existing.memory_id:
                    existing.memory_id = memory_id or f"session:{existing.session_id}"
                    self.save(existing)
                return existing
        return self.create(memory_id=memory_id)

    def save(self, session: ChatSession) -> None:
        path = self._path_for(session.session_id)
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_summaries(self, query: str = "", limit: int = 50) -> list[dict]:
        normalized_query = query.strip().lower()
        sessions: list[ChatSession] = []

        for path in self._session_dir.glob("*.json"):
            session = ChatSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if normalized_query and not self._matches_query(session, normalized_query):
                continue
            sessions.append(session)

        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return [self._summarize(session) for session in sessions[:limit]]

    def _path_for(self, session_id: str) -> Path:
        safe_session_id = session_id.replace("/", "_").replace("\\", "_")
        return self._session_dir / f"{safe_session_id}.json"

    def _matches_query(self, session: ChatSession, query: str) -> bool:
        if query in session.session_id.lower() or query in session.memory_id.lower():
            return True
        return any(query in turn.text.lower() for turn in session.turns)

    def _summarize(self, session: ChatSession) -> dict:
        last_turn = session.turns[-1] if session.turns else None
        last_user_turn = next((turn for turn in reversed(session.turns) if turn.role == "user"), None)
        return {
            "session_id": session.session_id,
            "memory_id": session.memory_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "turn_count": len(session.turns),
            "preview": (last_turn.text[:80] if last_turn else ""),
            "last_role": (last_turn.role if last_turn else ""),
            "last_user_text": (last_user_turn.text[:80] if last_user_turn else ""),
        }
