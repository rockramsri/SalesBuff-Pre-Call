"""Tavily and CourtListener query builders."""

from __future__ import annotations

from typing import Any

from salesbuff.models.entities import SalesContext


def build_prospect_company_queries(ctx: SalesContext) -> dict[str, str]:
    name = ctx.prospect.name
    year_range = "2025 2026"
    queries = {
        "news": f'"{name}" news announcement leadership {year_range}',
        "leadership_change": f'"{name}" new CEO CFO CMO VP director hired appointed {year_range}',
        "hiring": f'"{name}" jobs hiring {ctx.prospect.industry or ""} {year_range}'.strip(),
        "financial": f'"{name}" funding revenue financial results {year_range}',
        "culture": f'"{name}" glassdoor employee reviews culture turnover {year_range}',
        "pain": f'"{name}" problems challenges complaints issues {year_range}',
    }
    if ctx.prospect.industry and "health" in ctx.prospect.industry.lower():
        queries["regulatory"] = f'"{name}" FDA CMS regulatory compliance warning {year_range}'
        queries["merger"] = f'"{name}" merger acquisition health system {year_range}'
    return queries


def build_contact_person_queries(ctx: SalesContext) -> dict[str, str]:
    name = ctx.contact.full_name
    company = ctx.contact.company_name
    title = ctx.contact.title or ""
    return {
        "career": f'"{name}" "{company}" {title} background career linkedin'.strip(),
        "public_voice": f'"{name}" "{company}" interview article author talk written'.strip(),
        "social": f'"{name}" "{company}" linkedin post opinion'.strip(),
        "conference": f'"{name}" conference speaker keynote panel 2024 2025 2026'.strip(),
        "pain_signals": f'"{name}" "{company}" challenges problems feedback review'.strip(),
        "media": f'"{name}" podcast interview youtube 2024 2025 2026'.strip(),
    }


def build_incumbent_vendor_queries(ctx: SalesContext) -> dict[str, str]:
    if not ctx.incumbent:
        return {}
    name = ctx.incumbent.name
    category = ctx.incumbent.product_category or ""
    year_range = "2024 2025 2026"
    return {
        "customer_complaints": (
            f'"{name}" customer complaints problems issues unreliable {year_range}'
        ),
        "reviews": f'"{name}" reviews G2 trustpilot reddit negative {year_range}',
        "employees": f'"{name}" glassdoor layoffs engineer turnover morale {year_range}',
        "financial": f'"{name}" funding down round financial news {year_range}',
        "delivery_issues": f'"{name}" {category} outage failure recall delay problem'.strip(),
        "contract_practices": f'"{name}" contract auto-renewal cancellation locked in complaints',
        "news": f'"{name}" news {year_range}',
    }


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
