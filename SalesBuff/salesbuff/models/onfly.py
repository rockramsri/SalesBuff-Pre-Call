"""Models for SalesBuff On-Fly live coaching."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from salesbuff.utils import make_id

TipConfidence = Literal["high", "medium", "low"]
TipSource = Literal["immediate", "background"]
ResearchDepth = Literal["quick", "deep"]

# Call stages (a soft playbook, not a rigid script).
SalesStage = Literal[
    "icebreaker",
    "rapport",
    "discovery",
    "pain",
    "value",
    "proof",
    "objection",
    "next_step",
]
# What kind of coaching move a tip is (used for semantic dedup + cooldown).
TipType = Literal[
    "opener",
    "discovery",
    "pain",
    "value",
    "proof",
    "competitor",
    "objection",
    "stakeholder",
    "next_step",
    "other",
]


class DealBrief(BaseModel):
    """Structured deal context extracted once at session start (dynamic, never hardcoded)."""

    seller_company: str = ""
    seller_product: str = ""
    prospect_company: str = ""
    prospect_name: str = ""
    prospect_industry: str = ""
    trades: list[str] = Field(default_factory=list)
    incumbent: str = ""
    status_quo: str = ""
    trigger_event: str = ""
    proof_points: list[str] = Field(default_factory=list)
    entity_aliases: dict[str, str] = Field(default_factory=dict)

    def to_prompt_text(self) -> str:
        if not any(
            [
                self.seller_company,
                self.seller_product,
                self.prospect_company,
                self.prospect_name,
                self.trades,
                self.incumbent,
                self.trigger_event,
                self.proof_points,
            ]
        ):
            return ""
        lines: list[str] = []
        if self.seller_company or self.seller_product:
            lines.append(f"Seller: {self.seller_company} — {self.seller_product}".strip(" —"))
        if self.prospect_company or self.prospect_name:
            who = ", ".join(p for p in [self.prospect_name, self.prospect_company] if p)
            lines.append(f"Prospect: {who}")
        if self.prospect_industry:
            lines.append(f"Industry: {self.prospect_industry}")
        if self.trades:
            lines.append(f"Trades/lines: {', '.join(self.trades)}")
        if self.incumbent:
            lines.append(f"Incumbent / current solution: {self.incumbent}")
        if self.status_quo:
            lines.append(f"Status quo: {self.status_quo}")
        if self.trigger_event:
            lines.append(f"Trigger event / news: {self.trigger_event}")
        if self.proof_points:
            lines.append("Approved proof points (cite ONLY these as facts):")
            lines.extend(f"  - {p}" for p in self.proof_points)
        if self.entity_aliases:
            pairs = ", ".join(f'"{k}"→"{v}"' for k, v in self.entity_aliases.items())
            lines.append(f"Transcription aliases (normalize these): {pairs}")
        return "\n".join(lines)


class LiveTip(BaseModel):
    """One short, live coaching nudge."""

    tip_id: str = Field(default_factory=lambda: make_id("tip"))
    action_sentence: str
    reason: str = ""
    trigger: str = ""
    confidence: TipConfidence = "medium"
    source: TipSource = "immediate"
    stage: str = ""
    tip_type: str = "other"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LiveTipCandidate(BaseModel):
    """Raw LLM candidate before validation/dedup.

    LLMs often emit ``null`` for optional fields instead of omitting them, so
    every non-essential field coerces None/invalid values to a safe default.
    """

    stage: str = ""
    should_show: bool = False
    tip_type: str = "other"
    action_sentence: str = ""
    reason: str = ""
    trigger: str = ""
    confidence: TipConfidence = "medium"
    needs_research: bool = False
    research_depth: ResearchDepth = "quick"
    research_query: str | None = None
    research_queries: list[str] = Field(default_factory=list)

    @field_validator("stage", "tip_type", "action_sentence", "reason", "trigger", mode="before")
    @classmethod
    def _none_to_str(cls, v: object) -> object:
        return "" if v is None else v

    @field_validator("should_show", "needs_research", mode="before")
    @classmethod
    def _none_to_false(cls, v: object) -> object:
        return False if v is None else v

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: object) -> object:
        return v if v in ("high", "medium", "low") else "medium"

    @field_validator("research_depth", mode="before")
    @classmethod
    def _coerce_depth(cls, v: object) -> object:
        return v if v in ("quick", "deep") else "quick"

    @field_validator("research_queries", mode="before")
    @classmethod
    def _none_to_list(cls, v: object) -> object:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v


class LiveSessionContext(BaseModel):
    """Optional seed context for a live session."""

    precall_request_id: str | None = None
    pasted_context: str = ""
    spoken_setup: str = ""
    precall_brief: str = ""
    precall_facts: str = ""
    max_tips: int = Field(default=1, ge=1, le=3)
    tts_enabled: bool = False


class LiveSessionState(BaseModel):
    session_id: str
    context: LiveSessionContext
    created_at: str
    expires_at: str
    ended: bool = False
    tips: list[LiveTip] = Field(default_factory=list)
