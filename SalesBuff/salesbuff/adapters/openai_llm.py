"""OpenAI adapter — implements LlmClient."""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:  # pragma: no cover
    _HAS_TIKTOKEN = False

from salesbuff.metrics import bump
from salesbuff.ports.llm import LlmClient

logger = logging.getLogger(__name__)


class OpenAiLlmClient(LlmClient):
    def __init__(self, api_key: str, *, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._encoding = self._load_encoding(model)

    @staticmethod
    def _load_encoding(model: str):
        if not _HAS_TIKTOKEN:
            return None
        try:
            return tiktoken.encoding_for_model(model)
        except Exception:  # noqa: BLE001
            return tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, *parts: str) -> int | None:
        if self._encoding is None:
            return None
        return sum(len(self._encoding.encode(p or "")) for p in parts)

    def _log_request(self, call: str, system: str, user: str) -> None:
        chars = len(system or "") + len(user or "")
        tokens = self._count_tokens(system, user)
        token_str = f"{tokens} tokens" if tokens is not None else "tokens=n/a (tiktoken missing)"
        logger.info(
            "OpenAI %s call (%s): input ~%s, %d chars (system=%d, user=%d)",
            call,
            self.model,
            token_str,
            chars,
            len(system or ""),
            len(user or ""),
        )

    async def json(self, system: str, user: str) -> dict:
        bump("openai_json")
        self._log_request("json", system, user)
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        self._log_usage("json", resp)
        return json.loads(resp.choices[0].message.content or "{}")

    async def text(self, system: str, user: str) -> str:
        bump("openai_text")
        self._log_request("text", system, user)
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        self._log_usage("text", resp)
        return (resp.choices[0].message.content or "").strip()

    @staticmethod
    def _log_usage(call: str, resp) -> None:
        usage = getattr(resp, "usage", None)
        if usage is None:
            return
        logger.info(
            "OpenAI %s usage (actual): prompt=%s completion=%s total=%s",
            call,
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
            getattr(usage, "total_tokens", "?"),
        )

    async def validate(self) -> None:
        """Raise if the API key is invalid/unauthorized (cheap, no tokens)."""
        await self._client.models.list()

    async def aclose(self) -> None:
        await self._client.close()
