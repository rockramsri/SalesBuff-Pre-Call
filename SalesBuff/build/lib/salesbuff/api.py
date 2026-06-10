"""HTTP API for the due-diligence pipeline.

Job-based submit/poll because a full run takes ~1-2 min:
    POST /research          -> {request_id, status}
    GET  /research/{id}     -> {status, stage, progress, brief, warnings, error}
    GET  /health            -> {status}

Run with: cd SalesBuff && uvicorn salesbuff.api:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from salesbuff.container import Container
from salesbuff.metrics import UsageMetrics, current_metrics
from salesbuff.onfly.api import router as onfly_router
from salesbuff.onfly.coach import OnFlyCoach
from salesbuff.onfly.session import LiveSessionStore
from salesbuff.utils import make_id

logger = logging.getLogger(__name__)

# Stage -> coarse progress percentage for a user-facing bar.
_STAGE_PROGRESS = {
    "queued": 3,
    "resolving": 12,
    "researching": 55,
    "briefing": 88,
    "done": 100,
}


class UserKeys(BaseModel):
    openai: str | None = None
    tavily: str | None = None
    courtlistener: str | None = None

    def is_complete(self) -> bool:
        # OpenAI + Tavily are the required paid pair; CourtListener is optional.
        return bool(self.openai and self.openai.strip() and self.tavily and self.tavily.strip())


class ResearchRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    keys: UserKeys | None = None


class Job:
    def __init__(self) -> None:
        self.status: str = "pending"  # pending | completed | failed
        self.stage: str = "queued"
        self.progress: int = _STAGE_PROGRESS["queued"]
        self.brief: dict[str, Any] | None = None
        self.facts: dict[str, Any] | None = None
        self.warnings: list[str] = []
        self.error: str | None = None

    def set_stage(self, stage: str) -> None:
        self.stage = stage
        self.progress = _STAGE_PROGRESS.get(stage, self.progress)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "brief": self.brief,
            "facts": self.facts,
            "warnings": self.warnings,
            "error": self.error,
        }


def _configure_salesbuff_logging() -> None:
    """Make `salesbuff.*` INFO logs visible in the uvicorn console.

    Uvicorn only attaches handlers to its own loggers, so our package logs fall
    back to logging's "last resort" handler (WARNING+ only). Without an explicit
    handler the INFO-level metrics summary is silently dropped. We attach a
    StreamHandler that reuses uvicorn's formatter when available.
    """
    pkg_logger = logging.getLogger("salesbuff")
    pkg_logger.setLevel(logging.INFO)
    if any(getattr(h, "_salesbuff_handler", False) for h in pkg_logger.handlers):
        return

    handler = logging.StreamHandler()
    handler._salesbuff_handler = True  # type: ignore[attr-defined]

    uvicorn_logger = logging.getLogger("uvicorn")
    formatter = None
    for h in uvicorn_logger.handlers:
        if h.formatter is not None:
            formatter = h.formatter
            break
    handler.setFormatter(formatter or logging.Formatter("%(levelname)s:     %(message)s"))

    pkg_logger.addHandler(handler)
    pkg_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_salesbuff_logging()
    app.state.container = Container.from_config()
    app.state.jobs = {}
    app.state.onfly_store = LiveSessionStore()
    app.state.onfly_coach = OnFlyCoach(app.state.container)
    # Usage limiter: start from configured current count, capped at usage_max.
    cfg = app.state.container.config
    app.state.usage_used = cfg.usage_current
    app.state.usage_max = cfg.usage_max
    app.state.usage_lock = asyncio.Lock()
    logger.info(
        "Usage limiter initialized: used=%d max=%d", cfg.usage_current, cfg.usage_max
    )
    try:
        yield
    finally:
        await app.state.container.aclose()


def _usage_snapshot(app: FastAPI) -> dict[str, int]:
    used = app.state.usage_used
    limit = app.state.usage_max
    return {"used": used, "limit": limit, "remaining": max(limit - used, 0)}


app = FastAPI(title="SalesBuff Due-Diligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onfly_router, prefix="/onfly", tags=["onfly"])


async def _run_job(
    app: FastAPI,
    request_id: str,
    prompt: str,
    container: Container,
    owned: bool,
) -> None:
    job: Job = app.state.jobs[request_id]
    loop = asyncio.get_running_loop()
    metrics = UsageMetrics()
    metrics_token = current_metrics.set(metrics)

    def on_stage(stage: str) -> None:
        # Pipeline runs in this loop; update synchronously.
        job.set_stage(stage)

    try:
        result = await container.pipeline.run(prompt, on_stage=on_stage)
        if result.brief is not None:
            job.brief = result.brief.model_dump(mode="json")
        else:
            job.warnings.append("Brief could not be generated from the available findings.")
        if result.facts is not None:
            job.facts = result.facts.model_dump(mode="json")
        if result.dropped_cards:
            job.warnings.append(f"{len(result.dropped_cards)} card(s) dropped for lacking citations.")
        if metrics.errors:
            job.warnings.extend(metrics.errors)
        job.status = "completed"
        job.set_stage("done")
        metrics.snapshot("done")
        metrics.log_summary(request_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Research job %s failed", request_id)
        job.status = "failed"
        job.error = str(exc)
        metrics.snapshot("failed")
        metrics.log_summary(request_id)
    finally:
        current_metrics.reset(metrics_token)
        if owned:
            # Per-request (user-key) container — release its HTTP clients.
            await container.aclose()
        _ = loop  # keep reference; task lifetime tied to job


async def _validate_container(container: Container) -> str | None:
    """Return a user-facing message if the container's keys are rejected."""
    try:
        await container.llm.validate()
    except Exception as exc:  # noqa: BLE001
        return f"OpenAI key rejected: {_short(exc)}"
    try:
        await container.web_source.validate()
    except Exception as exc:  # noqa: BLE001
        return f"Tavily key rejected: {_short(exc)}"
    return None


def _short(exc: Exception, limit: int = 160) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:limit]


@app.post("/research")
async def submit_research(req: ResearchRequest) -> dict[str, Any]:
    prompt = req.prompt.strip()
    user_keys = req.keys if (req.keys and req.keys.is_complete()) else None

    if user_keys is None:
        # Shared server keys: enforce the usage limit.
        async with app.state.usage_lock:
            if app.state.usage_used >= app.state.usage_max:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "Usage limit reached. Add your own API keys to continue.",
                        "usage": _usage_snapshot(app),
                    },
                )
            app.state.usage_used += 1
        container = app.state.container
        owned = False
    else:
        # User-provided keys: bypass the limit, validate before running so a bad
        # key surfaces immediately instead of producing an empty brief.
        container = Container.from_keys(
            app.state.container.config,
            openai=user_keys.openai,
            tavily=user_keys.tavily,
            courtlistener=user_keys.courtlistener,
        )
        error = await _validate_container(container)
        if error:
            await container.aclose()
            raise HTTPException(status_code=400, detail={"message": error})
        owned = True

    request_id = make_id("req")
    app.state.jobs[request_id] = Job()
    asyncio.create_task(_run_job(app, request_id, prompt, container, owned))
    return {"request_id": request_id, "status": "pending", "usage": _usage_snapshot(app)}


@app.get("/usage")
async def get_usage() -> dict[str, int]:
    return _usage_snapshot(app)


@app.get("/research/{request_id}")
async def get_research(request_id: str) -> dict[str, Any]:
    job: Job | None = app.state.jobs.get(request_id)
    if job is None:
        return {"status": "not_found"}
    return job.to_dict()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
