"""Loads the YAML sales domain logic into simple typed objects.

Parsed once at startup (cached on the Container) so the Facts lane can read
categories, the question bank, ranking, and compliance overlays without
re-reading files on every request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "domain_logic_sales"


@dataclass(frozen=True)
class FactCategory:
    key: str
    display: str
    description: str
    order: int
    citation_required: bool


@dataclass(frozen=True)
class SalesLogic:
    categories: list[FactCategory]
    question_bank: dict[str, dict[str, list[str]]]
    overlays: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, base_dir: Path | None = None) -> SalesLogic:
        base = base_dir or _DEFAULT_DIR
        cats_raw = _read(base / "categories" / "categories.yaml").get("categories", {})
        ranking = _read(base / "ranking" / "ranking.yaml").get("order", {})
        questions = _read(base / "question_bank" / "questions.yaml")
        questions.pop("version", None)
        overlays = _read(base / "compliance" / "compliance.yaml").get("overlays", {})

        categories = [
            FactCategory(
                key=key,
                display=spec.get("display", key),
                description=(spec.get("description") or "").strip(),
                # Ranking file wins; else the category's own order; else last.
                order=ranking.get(key, spec.get("order", 99)),
                citation_required=bool(spec.get("citation_required", True)),
            )
            for key, spec in cats_raw.items()
        ]
        categories.sort(key=lambda c: c.order)
        return cls(categories=categories, question_bank=questions, overlays=overlays)

    def questions_for(self, role: str) -> list[str]:
        """Flat list of all questions for an entity role (across jobs).

        Coerces every entry to a clean string so a mis-shaped YAML item (e.g. an
        unquoted ``key: value`` parsed as a dict) can never leak a Python repr
        into the prompt.
        """
        jobs = self.question_bank.get(role, {})
        return [
            _as_question(q)
            for questions in jobs.values()
            for q in (questions or [])
        ]

    def compliance_overlay(self, vertical: str | None) -> str:
        """Guardrail text for the vertical; falls back to general_b2b."""
        overlays = self.overlays
        if vertical:
            needle = vertical.lower()
            for spec in overlays.values():
                for term in spec.get("match", []) or []:
                    if term.lower() in needle:
                        return (spec.get("guardrails") or "").strip()
        general = overlays.get("general_b2b", {})
        return (general.get("guardrails") or "").strip()


def _as_question(value: object) -> str:
    """Render a question-bank entry as plain text, even if YAML parsed it oddly."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        # e.g. {"What decision criteria matter": "technical, economic, ..."}
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
