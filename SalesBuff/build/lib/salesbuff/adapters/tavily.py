"""Tavily adapter — implements WebSource."""

from __future__ import annotations

import importlib
import logging
from typing import Any, cast

from salesbuff.metrics import bump, get_metrics
from salesbuff.ports.sources import WebSource

try:
    _tavily_module = cast(Any, importlib.import_module("tavily"))
    _TavilyClient = _tavily_module.AsyncTavilyClient
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "tavily-python is required. Install with `pip install tavily-python`."
    ) from exc

logger = logging.getLogger(__name__)


class TavilyAdapter(WebSource):
    """Raw Tavily calls. Defensive: returns {} on failure, never raises."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = _TavilyClient(api_key=api_key) if api_key else _TavilyClient()

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
        time_range: str | None = None,
        days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            return {}

        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
            "include_raw_content": include_raw_content,
        }
        if time_range:
            kwargs["time_range"] = time_range
        if days is not None:
            kwargs["days"] = days
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        try:
            bump("tavily_search")
            return await self._client.search(**kwargs) or {}
        except Exception as exc:  # noqa: BLE001
            msg = f"Tavily search failed for {query!r}: {exc}"
            logger.warning(msg)
            m = get_metrics()
            if m:
                m.record_error(msg)
            return {}

    async def extract(
        self,
        urls: list[str],
        *,
        extract_depth: str = "basic",
        output_format: str = "markdown",
        query: str = "",
    ) -> dict[str, Any]:
        urls = [u for u in (urls or []) if u]
        if not urls:
            return {}

        kwargs: dict[str, Any] = {
            "urls": urls,
            "extract_depth": extract_depth,
            "format": output_format,
        }
        if query:
            kwargs["query"] = query

        try:
            bump("tavily_extract")
            return await self._client.extract(**kwargs) or {}
        except Exception as exc:  # noqa: BLE001
            msg = f"Tavily extract failed for {len(urls)} urls: {exc}"
            logger.warning(msg)
            m = get_metrics()
            if m:
                m.record_error(msg)
            return {}

    async def research(
        self,
        input: str,
        *,
        model: str | None = None,
        output_schema: dict[str, Any] | None = None,
        output_length: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if not input or not input.strip():
            return {}

        kwargs: dict[str, Any] = {"input": input}
        if model:
            kwargs["model"] = model
        if output_schema:
            kwargs["output_schema"] = output_schema
        if output_length:
            kwargs["output_length"] = output_length
        if timeout is not None:
            kwargs["timeout"] = timeout

        try:
            bump("tavily_research_submit")
            result = await self._client.research(**kwargs)
            return cast("dict[str, Any]", result) if result else {}
        except Exception as exc:  # noqa: BLE001
            msg = f"Tavily research submit failed: {exc}"
            logger.warning(msg)
            m = get_metrics()
            if m:
                m.record_error(msg)
            return {}

    async def get_research(self, request_id: str) -> dict[str, Any]:
        if not request_id:
            return {}
        try:
            bump("tavily_research_poll")
            return await self._client.get_research(request_id) or {}
        except Exception as exc:  # noqa: BLE001
            msg = f"Tavily get_research failed ({request_id}): {exc}"
            logger.warning(msg)
            m = get_metrics()
            if m:
                m.record_error(msg)
            return {}

    async def validate(self) -> None:
        """Raise if the API key is invalid/unauthorized (one minimal search)."""
        await self._client.search("ping", max_results=1)

    async def aclose(self) -> None:
        close = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
        if close:
            result = close()
            if hasattr(result, "__await__"):
                await result
