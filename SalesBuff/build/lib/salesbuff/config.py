"""Frozen configuration loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


@dataclass(frozen=True)
class Config:
    tavily_api_key: str
    openai_api_key: str
    openai_model: str
    courtlistener_token: str | None
    max_cases_per_entity: int
    tavily_max_results: int = 5
    tavily_search_depth: str = "basic"
    # Tavily Deep Research (research endpoint is 20 RPM; cap in-flight tasks).
    # Concurrency 6 covers the 5 research tasks per run without queueing; max_polls
    # 60 (~240s) gives slow `mini` tasks more room before timing out.
    research_model: str = "mini"
    research_concurrency: int = 6
    research_poll_interval: float = 4.0
    research_max_polls: int = 60
    research_output_length: str = "standard"
    legal_batch_size: int = 10
    # Usage limiter: how many due-diligence runs already consumed and the cap.
    usage_current: int = 0
    usage_max: int = 25
    # On-Fly live coaching (fast paths — not Tavily Deep Research).
    onfly_tip_model: str = "gpt-4o-mini"
    onfly_compaction_model: str = "gpt-4o-mini"
    onfly_compact_chunk_threshold: int = 10
    onfly_compact_token_threshold: int = 3000
    onfly_summary_max_tokens: int = 3000
    onfly_raw_tail_chunks: int = 3
    onfly_reactive_search_max: int = 3
    # On-Fly reactive research. "quick" = one Tavily search; "deep" = several
    # Tavily searches whose results the LLM synthesizes into one tip.
    onfly_deep_research_max: int = 2
    onfly_deep_max_queries: int = 3
    # Semantic dedup: do not repeat the same tip_type within this many recent tips.
    onfly_tip_type_window: int = 3
    # On-Fly session logging (one JSON dump per session on end).
    onfly_session_log: bool = True
    onfly_log_dir: str = ""

    @classmethod
    def create(
        cls,
        *,
        openai_api_key: str,
        tavily_api_key: str,
        courtlistener_token: str | None = None,
        openai_model: str = "gpt-4o-mini",
        max_cases_per_entity: int = 8,
        **overrides: object,
    ) -> Config:
        """Build a Config from explicit values (no environment needed).

        Used by the SDK so callers can pass their own keys directly. Advanced
        tuning fields (research_concurrency, etc.) can be passed via overrides.
        """
        values: dict[str, object] = {
            "openai_api_key": openai_api_key,
            "tavily_api_key": tavily_api_key,
            "courtlistener_token": courtlistener_token,
            "openai_model": openai_model,
            "max_cases_per_entity": max_cases_per_entity,
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = True) -> Config:
        if load_dotenv_file:
            load_dotenv(_PKG_DIR / ".env")
            load_dotenv(_PKG_DIR.parent / ".env")
            load_dotenv()
        return cls(
            tavily_api_key=_require("TAVILY_API_KEY"),
            openai_api_key=_require("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            courtlistener_token=os.getenv("COURTLISTENER_TOKEN") or None,
            max_cases_per_entity=int(os.getenv("MAX_CASES_PER_ENTITY", "8")),
            tavily_max_results=int(os.getenv("TAVILY_MAX_RESULTS", "5")),
            tavily_search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
            research_model=os.getenv("TAVILY_RESEARCH_MODEL", "mini"),
            research_concurrency=int(os.getenv("TAVILY_RESEARCH_CONCURRENCY", "6")),
            research_poll_interval=float(os.getenv("TAVILY_RESEARCH_POLL_INTERVAL", "4.0")),
            research_max_polls=int(os.getenv("TAVILY_RESEARCH_MAX_POLLS", "60")),
            research_output_length=os.getenv("TAVILY_RESEARCH_OUTPUT_LENGTH", "standard"),
            legal_batch_size=int(os.getenv("LEGAL_BATCH_SIZE", "10")),
            usage_current=int(os.getenv("USAGE_CURRENT", "0")),
            usage_max=int(os.getenv("USAGE_MAX", "25")),
            onfly_tip_model=os.getenv("ONFLY_TIP_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
            onfly_compaction_model=os.getenv(
                "ONFLY_COMPACTION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            ),
            onfly_compact_chunk_threshold=int(os.getenv("ONFLY_COMPACT_CHUNK_THRESHOLD", "10")),
            onfly_compact_token_threshold=int(os.getenv("ONFLY_COMPACT_TOKEN_THRESHOLD", "3000")),
            onfly_summary_max_tokens=int(os.getenv("ONFLY_SUMMARY_MAX_TOKENS", "3000")),
            onfly_raw_tail_chunks=int(os.getenv("ONFLY_RAW_TAIL_CHUNKS", "3")),
            onfly_reactive_search_max=int(os.getenv("ONFLY_REACTIVE_SEARCH_MAX", "3")),
            onfly_deep_research_max=int(os.getenv("ONFLY_DEEP_RESEARCH_MAX", "2")),
            onfly_deep_max_queries=int(os.getenv("ONFLY_DEEP_MAX_QUERIES", "3")),
            onfly_tip_type_window=int(os.getenv("ONFLY_TIP_TYPE_WINDOW", "3")),
            onfly_session_log=os.getenv("ONFLY_SESSION_LOG", "1") not in ("0", "false", "False", ""),
            onfly_log_dir=os.getenv("ONFLY_LOG_DIR", ""),
        )
