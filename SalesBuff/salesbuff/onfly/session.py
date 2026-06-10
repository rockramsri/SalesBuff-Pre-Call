"""In-memory live-session store for On-Fly coaching."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from salesbuff.models.onfly import LiveSessionContext, LiveSessionState, LiveTip
from salesbuff.utils import make_id


@dataclass
class LiveSession:
    session_id: str
    context: LiveSessionContext
    context_text: str
    created_at: datetime
    expires_at: datetime
    queue: asyncio.Queue[LiveTip] = field(default_factory=asyncio.Queue)
    tips: list[LiveTip] = field(default_factory=list)
    transcript_chunks: list[str] = field(default_factory=list)
    transcript_summary: str = ""
    compacted_up_to: int = 0
    bootstrap_context: str = ""
    deal_brief_text: str = ""
    current_stage: str = ""
    last_tip_at: float = 0.0
    research_cache: dict[str, str] = field(default_factory=dict)
    ended: bool = False
    background_started: int = 0
    background_running: bool = False
    deep_research_started: int = 0
    deep_research_running: bool = False
    compaction_running: bool = False
    events: list[dict] = field(default_factory=list)

    def full_context_text(self) -> str:
        parts = [self.deal_brief_text.strip(), self.context_text.strip(), self.bootstrap_context.strip()]
        return "\n\n".join(p for p in parts if p)

    def recent_tip_types(self, n: int = 3) -> list[str]:
        return [t.tip_type for t in self.tips[-n:]]

    def remember_tip(self, tip: LiveTip) -> None:
        self.tips.append(tip)
        self.queue.put_nowait(tip)

    def to_state(self) -> LiveSessionState:
        return LiveSessionState(
            session_id=self.session_id,
            context=self.context,
            created_at=self.created_at.isoformat(),
            expires_at=self.expires_at.isoformat(),
            ended=self.ended,
            tips=self.tips,
        )


class LiveSessionStore:
    """Small in-memory store. Render must stay single-instance for this MVP."""

    def __init__(self, *, ttl_hours: int = 2) -> None:
        self.ttl = timedelta(hours=ttl_hours)
        self._sessions: dict[str, LiveSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, context: LiveSessionContext, context_text: str) -> LiveSession:
        now = datetime.now(timezone.utc)
        session = LiveSession(
            session_id=make_id("live"),
            context=context,
            context_text=context_text.strip(),
            created_at=now,
            expires_at=now + self.ttl,
        )
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str) -> LiveSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.ended or datetime.now(timezone.utc) > session.expires_at:
                self._sessions.pop(session_id, None)
                return None
            return session

    async def end(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return False
            session.ended = True
            return True

