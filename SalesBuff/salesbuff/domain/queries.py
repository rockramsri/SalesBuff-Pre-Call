"""CourtListener legal-search query parameters.

(Tavily web research is driven by structured deep-research prompts in
``domain/prompts.py``, not by keyword query dicts.)
"""

from __future__ import annotations

from typing import Any

from salesbuff.models.entities import SalesContext


def build_incumbent_legal_params(ctx: SalesContext) -> dict[str, Any]:
    if not ctx.incumbent:
        return {}
    return {
        "name": ctx.incumbent.name,
        "years_back": 5,
        "match_field": "party",
        "max_results": 25,
    }


def build_prospect_legal_params(ctx: SalesContext) -> dict[str, Any]:
    return {
        "name": ctx.prospect.name,
        "years_back": 3,
        "match_field": "party",
        "max_results": 10,
    }
