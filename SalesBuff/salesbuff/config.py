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
        )
