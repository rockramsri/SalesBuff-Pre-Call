"""Entity resolution: LLM query -> Tavily search/extract -> LLM verify.

Three fast shots (no deep research): an LLM crafts a strong web query from the
rep's prompt, Tavily search + extract gathers evidence, then an LLM verifies the
canonical names, aliases, and relationships into a SalesContext.
"""

from __future__ import annotations

import json
import logging

from salesbuff.domain.framing import sales_context_from_resolution
from salesbuff.domain.prompts import prompt_resolve_query, prompt_resolve_verify
from salesbuff.models.entities import (
    ContactPerson,
    ProspectCompany,
    SalesContext,
)
from salesbuff.models.findings import WebResult
from salesbuff.ports.llm import LlmClient
from salesbuff.ports.sources import WebSource

logger = logging.getLogger(__name__)


class EntityResolver:
    def __init__(
        self,
        llm: LlmClient,
        source: WebSource,
        *,
        max_results: int = 8,
        max_extract: int = 3,
    ) -> None:
        self.llm = llm
        self.source = source
        self.max_results = max_results
        self.max_extract = max_extract

    async def resolve(self, rep_prompt: str) -> SalesContext:
        anchors = await self._anchors(rep_prompt)
        query = anchors.get("search_query") or self._fallback_query(anchors)
        evidence = await self._gather_evidence(query)

        try:
            data = await self.llm.json(
                prompt_resolve_verify(rep_prompt), json.dumps(evidence, default=str)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Entity resolve verify failed: %s", exc)
            data = {}

        if not data.get("prospect_company"):
            return self._fallback_context(anchors)
        return sales_context_from_resolution(data)

    async def _anchors(self, rep_prompt: str) -> dict:
        system, user = prompt_resolve_query(rep_prompt)
        try:
            return await self.llm.json(system, user)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Entity resolve query failed: %s", exc)
            return {}

    async def _gather_evidence(self, query: str) -> list[dict]:
        if not query:
            return []
        raw = await self.source.search(
            query, max_results=self.max_results, search_depth="advanced"
        )
        results = [WebResult.from_tavily(item) for item in raw.get("results", []) or []]

        urls = [r.url for r in results if r.url][: self.max_extract]
        if urls:
            extracted = await self.source.extract(urls, query=query)
            by_url = {
                item.get("url"): item.get("raw_content", "")
                for item in extracted.get("results", []) or []
            }
            for result in results:
                if result.url in by_url and by_url[result.url]:
                    result.raw_content = by_url[result.url]

        return [
            {
                "title": r.title,
                "url": r.url,
                "content": (r.raw_content or r.content or ""),
            }
            for r in results
        ]

    @staticmethod
    def _fallback_query(anchors: dict) -> str:
        parts = [
            anchors.get("prospect_name") or "",
            anchors.get("contact_name") or "",
            anchors.get("incumbent_name") or "",
        ]
        return " ".join(p for p in parts if p).strip() or ""

    @staticmethod
    def _fallback_context(anchors: dict) -> SalesContext:
        prospect_name = anchors.get("prospect_name") or "Unknown Company"
        return SalesContext(
            prospect=ProspectCompany(name=prospect_name),
            contact=ContactPerson(
                full_name=anchors.get("contact_name") or prospect_name,
                company_name=prospect_name,
            ),
            rep_product=anchors.get("rep_product"),
            rep_company=anchors.get("rep_company"),
        )
