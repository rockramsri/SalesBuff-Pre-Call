"""Fast live-tip generation, transcript compaction, and research."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from salesbuff.adapters.openai_llm import OpenAiLlmClient
from salesbuff.core import CoreContainer
from salesbuff.models.onfly import DealBrief, LiveTip, LiveTipCandidate
from salesbuff.onfly.memory import (
    chunks_to_compact_text,
    raw_tail_before_current,
    should_compact,
    unsummarized_chunks,
)
from salesbuff.onfly.prompts import (
    prompt_background_tip,
    prompt_compact_transcript,
    prompt_deal_brief,
    prompt_live_tip,
)
from salesbuff.onfly.session import LiveSession

logger = logging.getLogger(__name__)

_FILLER = {
    "um",
    "uh",
    "like",
    "you know",
    "yeah",
    "okay",
    "ok",
    "right",
    "so",
}
_GENERIC_PHRASES = (
    "ask a follow up",
    "ask a follow-up",
    "listen actively",
    "build rapport",
    "summarize what they said",
    "keep them engaged",
    "build trust",
    "stay engaged",
    "maintain rapport",
    "active listening",
)
# Types where repetition is the main "generic" failure mode; gate these by cooldown.
_COOLDOWN_TYPES = {"value", "proof", "competitor"}


class OnFlyCoach:
    def __init__(self, container: CoreContainer) -> None:
        self.container = container
        cfg = container.config
        self._tip_llm = OpenAiLlmClient(cfg.openai_api_key, model=cfg.onfly_tip_model)
        self._compact_llm = OpenAiLlmClient(cfg.openai_api_key, model=cfg.onfly_compaction_model)

    # ---- logging -------------------------------------------------------

    def _log(self, session: LiveSession, event: str, **data: object) -> None:
        if not self.container.config.onfly_session_log:
            return
        session.events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "chunk_index": len(session.transcript_chunks),
                "event": event,
                **data,
            }
        )

    def finalize_session(self, session: LiveSession) -> str | None:
        cfg = self.container.config
        if not cfg.onfly_session_log:
            return None
        log_dir = (
            Path(cfg.onfly_log_dir)
            if cfg.onfly_log_dir
            else Path(__file__).resolve().parent.parent / "onfly_log"
        )
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "context": session.context.model_dump(),
                "deal_brief": session.deal_brief_text,
                "bootstrap_context": session.bootstrap_context,
                "final_stage": session.current_stage,
                "final_summary": session.transcript_summary,
                "counters": {
                    "chunks": len(session.transcript_chunks),
                    "tips": len(session.tips),
                    "quick_research": session.background_started,
                    "deep_research": session.deep_research_started,
                    "compacted_up_to": session.compacted_up_to,
                },
                "transcript_chunks": session.transcript_chunks,
                "tips": [t.model_dump() for t in session.tips],
                "events": session.events,
            }
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = log_dir / f"{ts}_{session.session_id}.json"
            path.write_text(json.dumps(payload, indent=2, default=str))
            logger.info("On-fly session log written: %s", path)
            return str(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("On-fly session log failed: %s", exc)
            return None

    # ---- session start -------------------------------------------------

    async def prepare_session(self, session: LiveSession) -> None:
        """Extract a structured deal brief (always) and bootstrap-search (if no pre-call)."""
        await self._extract_deal_brief(session)
        has_precall = bool(session.context.precall_request_id or session.context.precall_brief)
        if not has_precall:
            query = _bootstrap_query(session)
            if query:
                asyncio.create_task(self._run_bootstrap(session, query))

    async def _extract_deal_brief(self, session: LiveSession) -> None:
        if not session.context_text.strip():
            return
        try:
            system, user = prompt_deal_brief(context_text=session.context_text)
            raw = await self._tip_llm.json(system, user)
            brief = DealBrief.model_validate(raw)
            session.deal_brief_text = brief.to_prompt_text()
            self._log(session, "deal_brief_extracted", chars=len(session.deal_brief_text))
        except (ValidationError, ValueError) as exc:
            logger.warning("On-fly deal-brief extraction failed: %s", exc)

    async def _run_bootstrap(self, session: LiveSession, query: str) -> None:
        try:
            result = await self.container.web_source.search(
                query, max_results=3, search_depth="basic"
            )
            session.bootstrap_context = f"Bootstrap web research:\n{json.dumps(result, default=str)}"
            self._log(session, "bootstrap_research", query=query, ok=bool(result))
        except Exception as exc:  # noqa: BLE001
            logger.warning("On-fly bootstrap research failed: %s", exc)

    # ---- chunk hot path ------------------------------------------------

    async def handle_chunk(self, session: LiveSession, chunk: str, *, manual: bool = False) -> None:
        clean = _clean_text(chunk)
        if not manual and _is_noise(clean):
            self._log(session, "chunk_rejected_noise", text=clean, words=_word_count(clean))
            return

        session.transcript_chunks.append(clean)
        self._log(session, "chunk_received", text=clean, manual=manual, words=_word_count(clean))
        self._maybe_compact(session)

        cfg = self.container.config
        system, user = prompt_live_tip(
            context=session.full_context_text(),
            conversation_summary=session.transcript_summary,
            raw_tail=raw_tail_before_current(session, raw_tail=cfg.onfly_raw_tail_chunks),
            transcript_chunk=clean,
            recent_tips=[tip.action_sentence for tip in session.tips],
            recent_tip_types=session.recent_tip_types(cfg.onfly_tip_type_window),
            current_stage=session.current_stage,
            manual=manual,
            max_tips=session.context.max_tips,
        )
        try:
            raw = await self._tip_llm.json(system, user)
            candidate = LiveTipCandidate.model_validate(raw)
        except (ValidationError, ValueError) as exc:
            logger.warning("On-fly tip generation failed: %s", exc)
            self._log(session, "tip_llm_error", error=str(exc))
            return

        if candidate.stage:
            session.current_stage = candidate.stage
        self._log(
            session,
            "tip_candidate",
            source="immediate",
            stage=candidate.stage,
            tip_type=candidate.tip_type,
            should_show=candidate.should_show,
            action_sentence=candidate.action_sentence,
            confidence=candidate.confidence,
            needs_research=candidate.needs_research,
            research_depth=candidate.research_depth,
        )

        tip, reason = self._evaluate_candidate(candidate, session=session, source="immediate")
        if tip:
            session.remember_tip(tip)
            self._log(session, "tip_accepted", source="immediate", tip_id=tip.tip_id,
                      stage=tip.stage, tip_type=tip.tip_type, action_sentence=tip.action_sentence)
        else:
            self._log(session, "tip_rejected", source="immediate", reason=reason,
                      tip_type=candidate.tip_type, action_sentence=candidate.action_sentence)

        if candidate.needs_research:
            queries = candidate.research_queries or (
                [candidate.research_query] if candidate.research_query else []
            )
            queries = [q.strip() for q in queries if q and q.strip()]
            if queries:
                self._maybe_start_research(
                    session, queries, deep=candidate.research_depth == "deep"
                )
        elif _should_force_research(clean):
            # Safety net: the chunk clearly asked for proof/competitor info but the
            # model didn't flag it. Fire a quick search anyway.
            self._log(session, "research_forced", query=clean[:160])
            self._maybe_start_research(session, [clean[:160]], deep=False)

    # ---- compaction ----------------------------------------------------

    def _maybe_compact(self, session: LiveSession) -> None:
        if session.compaction_running:
            return
        cfg = self.container.config
        if not should_compact(
            session,
            raw_tail=cfg.onfly_raw_tail_chunks,
            chunk_threshold=cfg.onfly_compact_chunk_threshold,
            token_threshold=cfg.onfly_compact_token_threshold,
        ):
            return
        session.compaction_running = True
        self._log(session, "compaction_triggered", up_to=session.compacted_up_to)
        asyncio.create_task(self._run_compaction(session))

    async def _run_compaction(self, session: LiveSession) -> None:
        cfg = self.container.config
        try:
            pending = unsummarized_chunks(session, raw_tail=cfg.onfly_raw_tail_chunks)
            if not pending:
                return
            system, user = prompt_compact_transcript(
                previous_summary=session.transcript_summary,
                new_chunks_text=chunks_to_compact_text(pending),
                max_tokens=cfg.onfly_summary_max_tokens,
            )
            summary = (await self._compact_llm.text(system, user)).strip()
            if summary:
                session.transcript_summary = summary[: cfg.onfly_summary_max_tokens * 4]
            session.compacted_up_to = max(
                0, len(session.transcript_chunks) - cfg.onfly_raw_tail_chunks
            )
            self._log(session, "compaction_done", up_to=session.compacted_up_to,
                      summary_chars=len(session.transcript_summary))
        except Exception as exc:  # noqa: BLE001
            logger.warning("On-fly compaction failed: %s", exc)
        finally:
            session.compaction_running = False

    # ---- reactive research (quick = 1 search, deep = several) ----------

    def _maybe_start_research(self, session: LiveSession, queries: list[str], *, deep: bool) -> None:
        cfg = self.container.config
        if deep and session.deep_research_started >= cfg.onfly_deep_research_max:
            deep = False
            queries = queries[:1]
        if deep:
            if session.deep_research_running:
                self._log(session, "research_skipped", reason="deep_busy", queries=queries)
                return
            session.deep_research_started += 1
            session.deep_research_running = True
            self._log(session, "research_triggered", depth="deep", queries=queries)
            asyncio.create_task(self._run_research(session, queries, deep=True))
            return
        if session.background_running:
            self._log(session, "research_skipped", reason="quick_busy", queries=queries)
            return
        if session.background_started >= cfg.onfly_reactive_search_max:
            self._log(session, "research_skipped", reason="quick_quota", queries=queries)
            return
        session.background_started += 1
        session.background_running = True
        self._log(session, "research_triggered", depth="quick", queries=queries[:1])
        asyncio.create_task(self._run_research(session, queries[:1], deep=False))

    async def _run_research(self, session: LiveSession, queries: list[str], *, deep: bool) -> None:
        depth = "deep" if deep else "quick"
        try:
            research_json = await self._collect_research(session, queries, deep=deep)
            self._log(session, "research_result", depth=depth, queries=queries,
                      ok=bool(research_json), chars=len(research_json or ""))
            if not research_json:
                return
            cfg = self.container.config
            transcript_summary = " ".join(session.transcript_chunks[-cfg.onfly_raw_tail_chunks :])
            system, user = prompt_background_tip(
                context=session.full_context_text(),
                conversation_summary=session.transcript_summary,
                transcript_summary=transcript_summary,
                research_json=research_json,
                recent_tips=[tip.action_sentence for tip in session.tips],
            )
            raw = await self._tip_llm.json(system, user)
            candidate = LiveTipCandidate.model_validate(raw)
            self._log(session, "tip_candidate", source="background", depth=depth,
                      tip_type=candidate.tip_type, should_show=candidate.should_show,
                      action_sentence=candidate.action_sentence, confidence=candidate.confidence)
            tip, reason = self._evaluate_candidate(candidate, session=session, source="background")
            if tip:
                session.remember_tip(tip)
                self._log(session, "tip_accepted", source="background", depth=depth,
                          tip_id=tip.tip_id, tip_type=tip.tip_type,
                          action_sentence=tip.action_sentence)
            else:
                self._log(session, "tip_rejected", source="background", depth=depth,
                          reason=reason, action_sentence=candidate.action_sentence)
        except Exception as exc:  # noqa: BLE001
            logger.warning("On-fly %s research failed: %s", depth, exc)
            self._log(session, "research_error", depth=depth, error=str(exc))
        finally:
            if deep:
                session.deep_research_running = False
            else:
                session.background_running = False

    async def _collect_research(
        self, session: LiveSession, queries: list[str], *, deep: bool
    ) -> str:
        cfg = self.container.config
        if not deep:
            q = queries[0]
            cache_key = f"quick:{q}"
            if cache_key in session.research_cache:
                return session.research_cache[cache_key]
            result = await self.container.web_source.search(q, max_results=3, search_depth="basic")
            blob = json.dumps({q: result}, default=str)
            session.research_cache[cache_key] = blob
            return blob

        picked = queries[: cfg.onfly_deep_max_queries]
        cache_key = "deep:" + "|".join(picked)
        if cache_key in session.research_cache:
            return session.research_cache[cache_key]
        results = await asyncio.gather(
            *(
                self.container.web_source.search(q, max_results=3, search_depth="basic")
                for q in picked
            ),
            return_exceptions=True,
        )
        combined = {
            q: (r if not isinstance(r, BaseException) else {"error": str(r)})
            for q, r in zip(picked, results, strict=False)
        }
        blob = json.dumps(combined, default=str)
        session.research_cache[cache_key] = blob
        return blob

    # ---- validation / dedup -------------------------------------------

    def _evaluate_candidate(
        self,
        candidate: LiveTipCandidate,
        *,
        session: LiveSession,
        source: str,
    ) -> tuple[LiveTip | None, str]:
        sentence = _clean_text(candidate.action_sentence)
        if not candidate.should_show:
            return None, "should_show_false"
        if len(sentence) < 12:
            return None, "too_short"
        if candidate.confidence == "low":
            return None, "low_confidence"
        lowered = sentence.lower()
        if any(phrase in lowered for phrase in _GENERIC_PHRASES):
            return None, "generic_phrase"
        if _is_duplicate(sentence, [tip.action_sentence for tip in session.tips]):
            return None, "duplicate"
        window = self.container.config.onfly_tip_type_window
        if (
            candidate.tip_type in _COOLDOWN_TYPES
            and candidate.tip_type in session.recent_tip_types(window)
        ):
            return None, "type_cooldown"
        tip = LiveTip(
            action_sentence=sentence,
            reason=candidate.reason,
            trigger=candidate.trigger,
            confidence=candidate.confidence,
            stage=candidate.stage,
            tip_type=candidate.tip_type,
            source="background" if source == "background" else "immediate",
        )
        return tip, "accepted"


def _bootstrap_query(session: LiveSession) -> str | None:
    parts: list[str] = []
    if session.context.pasted_context.strip():
        parts.append(session.context.pasted_context.strip()[:400])
    if session.context.spoken_setup.strip():
        parts.append(session.context.spoken_setup.strip()[:200])
    text = " ".join(parts).strip()
    if len(text) < 20:
        return None
    return f"{text[:280]} company news priorities"


_FORCE_RESEARCH_TRIGGERS = (
    "proof",
    "evidence",
    "roi",
    "case study",
    "case studies",
    "actually work",
    "does it work",
    "does this work",
    "references",
    "prove it",
)


def _should_force_research(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _FORCE_RESEARCH_TRIGGERS)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"[a-zA-Z']+", text or ""))


def _is_noise(text: str) -> bool:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 5:
        return True
    filler_count = sum(1 for w in words if w in _FILLER)
    return filler_count / max(len(words), 1) > 0.55


def _is_duplicate(candidate: str, previous: list[str]) -> bool:
    cand = set(re.findall(r"[a-zA-Z']+", candidate.lower()))
    if not cand:
        return True
    for old in previous:
        old_words = set(re.findall(r"[a-zA-Z']+", old.lower()))
        if not old_words:
            continue
        overlap = len(cand & old_words) / max(len(cand | old_words), 1)
        if overlap >= 0.62:
            return True
    return False
