"""Web research lane: one Tavily Deep Research call per entity.

Each entity (prospect, contact, optional incumbent) gets a single structured
deep-research call that returns a validated profile of sales-relevant findings,
which is mapped into the shared WebFindings model used by the brief builder.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from salesbuff.domain.framing import describe_entity, sales_context_blurb
from salesbuff.domain.prompts import prompt_web_deep_research
from salesbuff.models.entities import EntityRole
from salesbuff.models.findings import AllWebFindings, EntityWebProfile, WebFindings, WebResult
from salesbuff.research.deep import DeepResearcher

if TYPE_CHECKING:
    from salesbuff.models.entities import SalesContext


class WebResearcher:
    def __init__(self, deep: DeepResearcher) -> None:
        self.deep = deep

    async def research_all(self, ctx: SalesContext) -> AllWebFindings:
        blurb = sales_context_blurb(ctx)
        tasks = [
            self._research_entity(
                describe_entity(ctx, EntityRole.PROSPECT_COMPANY),
                ctx.prospect.name,
                "company",
                "prospect_company",
                blurb,
            ),
            self._research_entity(
                describe_entity(ctx, EntityRole.CONTACT_PERSON),
                ctx.contact.full_name,
                "person",
                "contact_person",
                blurb,
            ),
        ]
        if ctx.incumbent:
            tasks.append(
                self._research_entity(
                    describe_entity(ctx, EntityRole.INCUMBENT_VENDOR),
                    ctx.incumbent.name,
                    "company",
                    "incumbent_vendor",
                    blurb,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        prospect = results[0] if not isinstance(results[0], Exception) else None
        contact = results[1] if not isinstance(results[1], Exception) else None
        incumbent = (
            results[2]
            if len(results) > 2 and not isinstance(results[2], Exception)
            else None
        )
        return AllWebFindings(prospect=prospect, contact=contact, incumbent=incumbent)

    async def _research_entity(
        self,
        description: str,
        subject: str,
        subject_type: str,
        role: str,
        blurb: str,
    ) -> WebFindings:
        empty = WebFindings(subject=subject, subject_type=subject_type, entity_role=role)
        if not description:
            return empty

        input_text = prompt_web_deep_research(description, subject_type, role, blurb)
        profile = await self.deep.run(input_text, EntityWebProfile)
        if profile is None:
            return empty

        return _profile_to_findings(profile, subject, subject_type, role)


def _profile_to_findings(
    profile: EntityWebProfile, subject: str, subject_type: str, role: str
) -> WebFindings:
    categories: dict[str, list[WebResult]] = {}
    for finding in profile.findings:
        category = (finding.category or "general").strip() or "general"
        categories.setdefault(category, []).append(
            WebResult(
                title=finding.headline,
                url=finding.url,
                content=finding.detail,
                source_domain=urlparse(finding.url).netloc if finding.url else "",
            )
        )
    return WebFindings(
        subject=subject,
        subject_type=subject_type,
        entity_role=role,
        categories=categories,
    )
