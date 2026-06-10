"""FastAPI routes for SalesBuff On-Fly live coaching."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from salesbuff.models.onfly import LiveSessionContext
from salesbuff.onfly.coach import OnFlyCoach
from salesbuff.onfly.session import LiveSession, LiveSessionStore

router = APIRouter()


class CreateSessionRequest(BaseModel):
    precall_request_id: str | None = None
    pasted_context: str = Field(default="", max_length=12000)
    spoken_setup: str = Field(default="", max_length=4000)
    precall_brief: str = Field(default="", max_length=30000)
    precall_facts: str = Field(default="", max_length=30000)
    max_tips: int = Field(default=1, ge=1, le=3)
    tts_enabled: bool = False


class ChunkRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    manual: bool = False


def _store(request: Request) -> LiveSessionStore:
    store = getattr(request.app.state, "onfly_store", None)
    if store is None:
        store = LiveSessionStore()
        request.app.state.onfly_store = store
    return store


def _coach(request: Request) -> OnFlyCoach:
    coach = getattr(request.app.state, "onfly_coach", None)
    if coach is None:
        coach = OnFlyCoach(request.app.state.container)
        request.app.state.onfly_coach = coach
    return coach


async def _require_session(request: Request, session_id: str) -> LiveSession:
    session = await _store(request).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"message": "Live session not found."})
    return session


@router.post("/sessions")
async def create_session(req: CreateSessionRequest, request: Request) -> dict[str, Any]:
    context = LiveSessionContext(
        precall_request_id=req.precall_request_id,
        pasted_context=req.pasted_context,
        spoken_setup=req.spoken_setup,
        precall_brief=req.precall_brief,
        precall_facts=req.precall_facts,
        max_tips=req.max_tips,
        tts_enabled=req.tts_enabled,
    )
    context_text = _build_context_text(req, request)
    session = await _store(request).create(context, context_text)
    await _coach(request).prepare_session(session)
    return {"session_id": session.session_id, "expires_at": session.expires_at.isoformat()}


@router.post("/sessions/{session_id}/chunks")
async def ingest_chunk(session_id: str, req: ChunkRequest, request: Request) -> dict[str, Any]:
    session = await _require_session(request, session_id)
    await _coach(request).handle_chunk(session, req.text, manual=req.manual)
    return {"status": "accepted", "tip_count": len(session.tips)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict[str, Any]:
    session = await _require_session(request, session_id)
    return session.to_state().model_dump(mode="json")


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str, request: Request) -> dict[str, Any]:
    store = _store(request)
    session = await store.get(session_id)
    log_path = _coach(request).finalize_session(session) if session is not None else None
    ended = await store.end(session_id)
    return {"ended": ended, "log": log_path}


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, request: Request) -> StreamingResponse:
    session = await _require_session(request, session_id)

    async def stream():
        while True:
            latest = await _store(request).get(session_id)
            if latest is None:
                yield "event: end\ndata: {}\n\n"
                return
            try:
                tip = await asyncio.wait_for(session.queue.get(), timeout=15)
                yield f"event: tip\ndata: {tip.model_dump_json()}\n\n"
            except TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _build_context_text(req: CreateSessionRequest, request: Request) -> str:
    parts: list[str] = []
    if req.pasted_context.strip():
        parts.append(f"User-provided context:\n{req.pasted_context.strip()}")
    if req.spoken_setup.strip():
        parts.append(f"Spoken setup:\n{req.spoken_setup.strip()}")

    # Prefer brief/facts sent directly by the client (robust to server reloads
    # that wipe the in-memory jobs map); fall back to the job lookup.
    brief: object = req.precall_brief.strip()
    facts: object = req.precall_facts.strip()
    if (not brief or not facts) and req.precall_request_id:
        job = getattr(request.app.state, "jobs", {}).get(req.precall_request_id)
        if job is not None:
            snap = job.to_dict()
            brief = brief or snap.get("brief")
            facts = facts or snap.get("facts")

    if brief:
        parts.append(f"Pre-call Actions brief:\n{brief}")
    if facts:
        parts.append(f"Pre-call Facts dossier:\n{facts}")

    return "\n\n".join(parts).strip()

