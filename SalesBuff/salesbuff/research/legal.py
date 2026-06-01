"""CourtListener legal research + batched deep-research enrichment.

Search keeps the docket dedup, party fuzzy-match, and pagination from the
original flow but drops the per-case LLM relevance verifier. Relevance and
enrichment now happen in batches via Tavily Deep Research (see LegalEnricher).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta

from salesbuff.domain.prompts import prompt_legal_deep_research
from salesbuff.models.findings import LegalEnrichmentBatch, LegalCase, LitigationFindings
from salesbuff.ports.sources import LegalSource
from salesbuff.research.deep import DeepResearcher

try:
    from rapidfuzz import fuzz, process

    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _HAS_RAPIDFUZZ = False


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    text = re.sub(r"&", "and", name.lower())
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\b(co|company|inc|incorporated|ltd|llc|corp|corporation|lp)\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


class LegalResearcher:
    def __init__(
        self,
        source: LegalSource,
        *,
        fuzzy_threshold: int = 80,
        max_pages: int = 3,
    ) -> None:
        self.source = source
        self.fuzzy_threshold = fuzzy_threshold
        self.max_pages = max_pages

    async def research_company(
        self,
        name: str,
        *,
        years_back: int = 5,
        match_field: str = "party",
        max_results: int = 25,
        variants: list[str] | None = None,
    ) -> LitigationFindings:
        names = list(dict.fromkeys([name, *(variants or [])]))
        end = datetime.now()
        start = end - timedelta(days=years_back * 365)
        start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

        seen: set[str] = set()
        cases: list[LegalCase] = []
        total_count = 0

        for nm in names:
            if len(cases) >= max_results:
                break
            field = "party" if match_field == "party" else "caseName"
            query = f'{field}:"{nm}" AND dateFiled:[{start_s} TO {end_s}]'
            data = await self.source.search(query, search_type="d")
            total_count = max(total_count, int(data.get("count") or 0))

            page = 0
            while data and page < self.max_pages:
                for item in data.get("results", []) or []:
                    key = (
                        item.get("docketNumber")
                        or item.get("docket_id")
                        or item.get("absolute_url")
                    )
                    if not key or key in seen:
                        continue
                    if not self._party_matches(nm, item.get("party", [])):
                        continue
                    seen.add(key)
                    cases.append(LegalCase.from_result(item))
                    if len(cases) >= max_results:
                        break
                if len(cases) >= max_results:
                    break
                next_url = data.get("next")
                if not next_url or not str(next_url).strip():
                    break
                data = await self.source.follow(next_url)
                page += 1

        return LitigationFindings(
            subject=name,
            subject_type="company",
            total_count=total_count or len(cases),
            searched_variants=names,
            cases=cases,
        )

    def _party_matches(self, name: str, parties: list[str]) -> bool:
        if not parties:
            return True
        norm = _normalize_name(name)
        norm_parties = [_normalize_name(p) for p in parties if p]
        if not _HAS_RAPIDFUZZ:
            return any(norm and norm in p for p in norm_parties)
        if norm in norm_parties:
            return True
        match = process.extractOne(norm, norm_parties, scorer=fuzz.token_set_ratio)
        return bool(match and match[1] >= self.fuzzy_threshold)


class LegalEnricher:
    """Validate + enrich cases in batches via Tavily Deep Research."""

    def __init__(self, deep: DeepResearcher, *, batch_size: int = 10) -> None:
        self.deep = deep
        self.batch_size = batch_size

    async def enrich(
        self, findings: LitigationFindings | None, blurb: str
    ) -> LitigationFindings | None:
        if not findings or findings.no_cases:
            return findings

        batches = [
            findings.cases[i : i + self.batch_size]
            for i in range(0, len(findings.cases), self.batch_size)
        ]
        results = await asyncio.gather(
            *(self._enrich_batch(batch, findings.subject, blurb) for batch in batches),
            return_exceptions=True,
        )

        kept: list[LegalCase] = []
        for batch, result in zip(batches, results):
            if isinstance(result, Exception) or result is None:
                kept.extend(batch)  # keep raw on failure rather than lose data
            else:
                kept.extend(result)

        findings.cases = kept
        findings.total_count = max(findings.total_count, len(kept))
        return findings

    async def _enrich_batch(
        self, batch: list[LegalCase], subject: str, blurb: str
    ) -> list[LegalCase]:
        payload = [
            {
                "id": i,
                "case_name": case.case_name,
                "docket_number": case.docket_number,
                "court": case.court,
                "date_filed": case.date_filed,
                "nature_of_suit": case.nature_of_suit or case.cause,
                "snippet": case.snippet,
                "url": case.url,
            }
            for i, case in enumerate(batch)
        ]
        input_text = prompt_legal_deep_research(blurb, subject, json.dumps(payload, default=str))
        result = await self.deep.run(input_text, LegalEnrichmentBatch)
        if result is None:
            return batch

        by_id = {c.id: c for c in result.cases}
        kept: list[LegalCase] = []
        for i, case in enumerate(batch):
            enr = by_id.get(i)
            if enr is None:
                kept.append(case)  # model omitted it; keep raw
                continue
            if not enr.involved:
                continue  # deep research says not genuinely involved -> drop
            case.details = enr.summary or case.details
            case.status = enr.status or case.status
            if enr.risk_type:
                case.risk_type = enr.risk_type
            if enr.sources:
                case.web_sources = [s for s in enr.sources if s]
            kept.append(case)
        return kept
