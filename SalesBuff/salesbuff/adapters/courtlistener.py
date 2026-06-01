"""CourtListener adapter — implements LegalSource."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from salesbuff.ports.sources import LegalSource

logger = logging.getLogger(__name__)

_ROOT = "https://www.courtlistener.com/api/rest/v4"


class CourtListenerAdapter(LegalSource):
    """Raw CourtListener calls. Defensive: returns {} on failure, never raises."""

    SEARCH_URL = f"{_ROOT}/search/"
    DOCKETS_URL = f"{_ROOT}/dockets/"
    PARTIES_URL = f"{_ROOT}/parties/"

    def __init__(self, token: str | None = None, *, timeout: float = 30.0) -> None:
        headers = {"Authorization": f"Token {token}"} if token else {}
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)

    async def search(
        self,
        query: str,
        *,
        search_type: str = "d",
        semantic: bool = False,
        order_by: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            return {}
        params: dict[str, Any] = {"q": query, "type": search_type}
        if semantic:
            params["type"] = "o"
            params["semantic"] = "true"
        if order_by:
            params["order_by"] = order_by
        if extra:
            params.update(extra)
        return await self._get(self.SEARCH_URL, params)

    async def follow(self, url: str) -> dict[str, Any]:
        if not url or not url.strip():
            return {}
        return await self._get(url)

    async def get_docket(self, docket_id: int | str) -> dict[str, Any]:
        return await self._get(f"{self.DOCKETS_URL}{docket_id}/")

    async def get_parties(self, docket_id: int | str) -> dict[str, Any]:
        return await self._get(self.PARTIES_URL, {"docket": docket_id})

    async def get_docket_entries(self, docket_id: int | str) -> dict[str, Any]:
        return await self._get(
            f"{_ROOT}/docket-entries/", {"docket": docket_id, "order_by": "-date_filed"}
        )

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("CourtListener GET failed (%s): %s", url, exc)
            return {}

    async def aclose(self) -> None:
        await self._client.aclose()
