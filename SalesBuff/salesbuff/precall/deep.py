"""Tavily Deep Research runner: submit, poll, validate into Pydantic.

The Tavily research endpoint is rate-limited (20 RPM) and runs asynchronously
(submit -> poll). A semaphore caps how many research tasks are in flight at once
so concurrent web + legal lanes stay well under the limit.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from salesbuff.metrics import get_metrics
from salesbuff.ports.sources import WebSource
from salesbuff.precall.schema import pydantic_to_tavily_schema, validate_research_detail

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _tavily_response_error(payload: dict[str, Any]) -> str:
    """Best-effort error string from a Tavily API response body."""
    if not payload:
        return "empty response"
    for key in ("error", "detail", "message", "status_message"):
        val = payload.get(key)
        if val:
            return str(val)
    if payload.get("status") == "failed":
        return "status=failed (no error field in response)"
    return f"unexpected response keys: {sorted(payload.keys())}"


def _content_preview(content: Any, limit: int = 200) -> str:
    if content is None:
        return "None"
    try:
        text = content if isinstance(content, str) else json.dumps(content, default=str)
    except (TypeError, ValueError):
        text = repr(content)
    if len(text) > limit:
        return text[:limit] + "..."
    return text


class DeepResearcher:
    def __init__(
        self,
        source: WebSource,
        *,
        model: str = "mini",
        concurrency: int = 4,
        poll_interval: float = 4.0,
        max_polls: int = 45,
        output_length: str = "standard",
    ) -> None:
        self.source = source
        self.model = model
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self.output_length = output_length
        self._sem = asyncio.Semaphore(concurrency)

    def _record_failure(self, message: str) -> None:
        logger.warning(message)
        metrics = get_metrics()
        if metrics is not None:
            metrics.record_error(message)

    async def run(self, input_text: str, schema_model: type[T]) -> T | None:
        """Run one deep-research task and validate it into ``schema_model``."""
        if not input_text or not input_text.strip():
            return None
        schema = pydantic_to_tavily_schema(schema_model)
        label = schema_model.__name__

        async with self._sem:
            task = await self.source.research(
                input_text,
                model=self.model,
                output_schema=schema,
                output_length=self.output_length,
            )
            request_id = task.get("request_id")
            if not request_id:
                reason = _tavily_response_error(task)
                resp_preview = _content_preview(task, limit=800)
                self._record_failure(
                    f"Deep research submit failed ({label}): {reason} | "
                    f"input_preview={input_text[:120]!r} | response_preview={resp_preview}"
                )
                return None

            for _poll in range(self.max_polls):
                await asyncio.sleep(self.poll_interval)
                result = await self.source.get_research(request_id)
                status = result.get("status")

                if status == "completed":
                    validated, err = validate_research_detail(
                        result.get("content"), schema_model
                    )
                    if validated is not None:
                        return cast(T, validated)
                    self._record_failure(
                        f"Deep research validation failed ({label}, {request_id}): {err} | "
                        f"content_preview={_content_preview(result.get('content'))}"
                    )
                    return None

                if status == "failed":
                    reason = _tavily_response_error(result)
                    body_preview = _content_preview(result, limit=1200)
                    self._record_failure(
                        f"Deep research failed ({label}, {request_id}): {reason} | "
                        f"response_preview={body_preview}"
                    )
                    return None

            self._record_failure(
                f"Deep research timed out ({label}, {request_id}): "
                f"no terminal status after {self.max_polls} polls "
                f"({self.max_polls * self.poll_interval:.0f}s)"
            )
            return None
