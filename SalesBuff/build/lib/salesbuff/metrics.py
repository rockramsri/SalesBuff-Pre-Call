"""Per-job API usage counters (Tavily + OpenAI) via contextvar."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

current_metrics: ContextVar[UsageMetrics | None] = ContextVar("salesbuff_metrics", default=None)


@dataclass
class UsageMetrics:
    tavily_search: int = 0
    tavily_extract: int = 0
    tavily_research_submit: int = 0
    tavily_research_poll: int = 0
    openai_json: int = 0
    openai_text: int = 0
    stage_snapshots: dict[str, dict[str, int]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    _COUNT_KEYS = (
        "tavily_search",
        "tavily_extract",
        "tavily_research_submit",
        "tavily_research_poll",
        "openai_json",
        "openai_text",
    )

    def counts(self) -> dict[str, int]:
        return {k: getattr(self, k) for k in self._COUNT_KEYS}

    def snapshot(self, stage: str) -> None:
        self.stage_snapshots[stage] = self.counts()

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def _delta(self, prev: dict[str, int], curr: dict[str, int]) -> dict[str, int]:
        return {k: curr.get(k, 0) - prev.get(k, 0) for k in self._COUNT_KEYS}

    def _format_counts(self, delta: dict[str, int]) -> str:
        tavily = (
            f"search={delta['tavily_search']} extract={delta['tavily_extract']} "
            f"research={delta['tavily_research_submit']} polls={delta['tavily_research_poll']}"
        )
        openai = f"json={delta['openai_json']} text={delta['openai_text']}"
        return f"tavily [{tavily}] | openai [{openai}]"

    def log_summary(self, request_id: str) -> None:
        """Log per-stage deltas and totals for a completed job."""
        stages = list(self.stage_snapshots.keys())
        if not stages:
            logger.info("Job %s — no API usage recorded", request_id)
            return

        lines = [f"Job {request_id} — API usage:"]
        prev: dict[str, int] = {k: 0 for k in self._COUNT_KEYS}
        for stage in stages:
            curr = self.stage_snapshots[stage]
            delta = self._delta(prev, curr)
            if any(delta.values()):
                lines.append(f"  {stage}: {self._format_counts(delta)}")
            prev = curr

        totals = self.counts()
        lines.append(f"  total: {self._format_counts(totals)}")

        if self.errors:
            lines.append("  failures:")
            for err in self.errors:
                lines.append(f"    - {err}")

        logger.info("\n".join(lines))


def get_metrics() -> UsageMetrics | None:
    return current_metrics.get()


def bump(metric: str, amount: int = 1) -> None:
    m = current_metrics.get()
    if m is not None and hasattr(m, metric):
        setattr(m, metric, getattr(m, metric) + amount)
