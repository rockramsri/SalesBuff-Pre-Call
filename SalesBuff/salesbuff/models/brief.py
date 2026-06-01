"""Card-based sales brief output models (conversation-move coach)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from salesbuff.utils import make_id


class BriefCategory(str, Enum):
    OPENING_MOVE = "opening_move"
    RAPPORT_HOOK = "rapport_hook"
    PRIORITY_SIGNAL = "priority_signal"
    PAIN_HYPOTHESIS = "pain_hypothesis"
    DIFFERENTIATION_ANGLE = "differentiation_angle"
    PROOF_POINT = "proof_point"
    STAKEHOLDER_HINT = "stakeholder_hint"
    OBJECTION_PREP = "objection_prep"
    NEXT_STEP = "next_step"
    WATCH_OUT = "watch_out"
    OPEN_QUESTION = "open_question"


class CardActionType(str, Enum):
    SAY = "say"
    ASK = "ask"
    SHOW = "show"
    AVOID = "avoid"
    VERIFY = "verify"


class UseWhen(str, Enum):
    OPENING = "opening"
    DISCOVERY = "discovery"
    DIFFERENTIATION = "differentiation"
    OBJECTION = "objection"
    CLOSE = "close"
    FOLLOW_UP = "follow_up"


# Categories that may omit citations (used by brief_rules.ground_brief).
CITATION_OPTIONAL = {BriefCategory.OPEN_QUESTION, BriefCategory.RAPPORT_HOOK}

# Old (pre-move-coach) category names + common near-misses, mapped to the new
# move taxonomy so a stray/legacy value never discards the whole brief.
_CATEGORY_ALIASES = {
    "competitor_weakness": "differentiation_angle",
    "competitive_weakness": "differentiation_angle",
    "weakness": "differentiation_angle",
    "company_signal": "priority_signal",
    "signal": "priority_signal",
    "trigger": "priority_signal",
    "person_insight": "rapport_hook",
    "insight": "rapport_hook",
    "person": "rapport_hook",
    "icebreaker": "rapport_hook",
    "pain": "pain_hypothesis",
    "differentiation": "differentiation_angle",
    "proof": "proof_point",
    "stakeholder": "stakeholder_hint",
    "objection": "objection_prep",
    "next": "next_step",
    "question": "open_question",
    "risk": "watch_out",
    "caution": "watch_out",
    "warning": "watch_out",
}


def _coerce_category(value: object) -> object:
    if isinstance(value, BriefCategory) or not isinstance(value, str):
        return value
    key = value.strip().lower()
    valid = {c.value for c in BriefCategory}
    if key in valid:
        return key
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    for category in BriefCategory:
        if category.value in key or key in category.value:
            return category.value
    return BriefCategory.PRIORITY_SIGNAL.value


def _coerce_enum(value: object, enum: type[Enum], default: Enum) -> object:
    """Map a stray string onto an enum value, falling back to ``default``."""
    if isinstance(value, enum) or not isinstance(value, str):
        return value
    key = value.strip().lower()
    valid = {e.value for e in enum}
    if key in valid:
        return key
    return default.value


class Citation(BaseModel):
    # Shape only — grounding (brief_rules.ground_brief) is the single source of
    # truth for citation validity, so a stray empty URL can't fail the whole brief.
    source: Literal["web", "court_listener"] = "web"
    url: str = ""
    title: str = ""
    quote: str = ""


class BriefCard(BaseModel):
    card_id: str = Field(default_factory=lambda: make_id("card"))
    category: BriefCategory
    action_type: CardActionType = CardActionType.SAY
    use_when: UseWhen = UseWhen.DISCOVERY
    title: str
    preview: str
    talk_track: str = ""
    detail: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    confidence: Literal["high", "medium", "low"] = "medium"
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: object) -> object:
        return _coerce_category(value)

    @field_validator("action_type", mode="before")
    @classmethod
    def _normalize_action_type(cls, value: object) -> object:
        return _coerce_enum(value, CardActionType, CardActionType.SAY)

    @field_validator("use_when", mode="before")
    @classmethod
    def _normalize_use_when(cls, value: object) -> object:
        return _coerce_enum(value, UseWhen, UseWhen.DISCOVERY)


class BriefSubject(BaseModel):
    prospect: str
    contact: str
    incumbent: str | None = None


class SalesBrief(BaseModel):
    subject: BriefSubject
    opening_line: str
    next_step_line: str = ""
    cards: list[BriefCard] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def grouped(self) -> dict[BriefCategory, list[BriefCard]]:
        out: dict[BriefCategory, list[BriefCard]] = {}
        for card in self.cards:
            out.setdefault(card.category, []).append(card)
        return out

    @property
    def card_count(self) -> int:
        return len(self.cards)
