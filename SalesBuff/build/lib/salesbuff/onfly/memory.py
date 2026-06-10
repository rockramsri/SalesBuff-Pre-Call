"""Transcript memory helpers for On-Fly (compaction triggers, tail slicing)."""

from __future__ import annotations

from salesbuff.onfly.session import LiveSession

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // _CHARS_PER_TOKEN)


def unsummarized_chunks(session: LiveSession, *, raw_tail: int) -> list[str]:
    """Chunks eligible for compaction (excludes raw tail buffer)."""
    chunks = session.transcript_chunks
    if len(chunks) <= raw_tail:
        return chunks[session.compacted_up_to :]
    return chunks[session.compacted_up_to : len(chunks) - raw_tail]


def raw_tail_before_current(session: LiveSession, *, raw_tail: int) -> list[str]:
    """Verbatim recent chunks before the chunk currently being processed."""
    chunks = session.transcript_chunks
    if len(chunks) <= 1:
        return []
    prior = chunks[:-1]
    if len(prior) <= raw_tail:
        return prior
    return prior[-raw_tail:]


def should_compact(
    session: LiveSession,
    *,
    raw_tail: int,
    chunk_threshold: int,
    token_threshold: int,
) -> bool:
    pending = unsummarized_chunks(session, raw_tail=raw_tail)
    if not pending:
        return False
    if len(pending) > chunk_threshold:
        return True
    joined = " ".join(pending)
    return estimate_tokens(joined) > token_threshold


def chunks_to_compact_text(chunks: list[str]) -> str:
    return "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(chunks))
