<!-- 🟡 SalesBuff backend -->

# 🟡 SalesBuff — Backend (FastAPI)

The Python service for **Pre-call due diligence** (citation-grounded Actions +
Facts) and **On-fly live coaching** (real-time tips during a call). Built with
FastAPI + asyncio.

> Architecture deep-dive (folders, data flow, prompts): see
> [`ARCHITECTURE.md`](ARCHITECTURE.md). Domain glossary: [`../CONTEXT.md`](../CONTEXT.md).

---

## Features

### Pre-call

One request runs a 3-stage pipeline:

1. **Resolve** — figure out the real buyer, contact, seller, **meeting motion**
   (expansion vs displacement), and any competitor to beat. *(LLM → Tavily search → LLM)*
2. **Research** — deep-research each entity on the web; optionally search court
   records. *(Tavily Deep Research + CourtListener)*
3. **Brief** — from one shared fact pack, generate **Actions** (coaching moves)
   and **Facts** (evidence dossier) concurrently, then **ground** every card to a
   real source URL. *(OpenAI)*

Because a full run takes ~1–2 minutes, the API is **job-based**: submit, then poll.

### On-fly

Live coaching during a call:

1. **Session start** — extract a structured deal brief from seed context; optional
   bootstrap Tavily search when pre-call data is thin.
2. **Transcript chunks** — browser sends speech every ~25s or on manual "Get tip now".
3. **Tip generation** — fast LLM pass with conversation memory (compacted summary +
   raw tail + current chunk), stage/tip-type metadata, dedup filters.
4. **Reactive research** — async Tavily **quick** (one search) or **deep** (multi-query
   synthesis) when the coach flags a gap; never blocks immediate tips.
5. **Session end** — optional JSON log of every chunk, candidate, rejection, and tip.

On-fly uses **Core** only (`CoreContainer`) — it never imports the pre-call pipeline.

---

## Two ways to use it

It's **one package** with feature extras you mix and match:

| Install | You get |
|---------|---------|
| `pip install salesbuff` | Shared **core** — LLM + search clients, config, models. |
| `pip install "salesbuff[precall]"` | The **pre-call due-diligence** feature (`SalesBuff`, `research_once`). |
| `pip install "salesbuff[onfly]"` | **Live coaching** — Core only; no pre-call dependencies pulled in. |
| `pip install "salesbuff[api]"` | The **FastAPI** host layer + the `salesbuff-serve` command. |
| `pip install "salesbuff[precall,api]"` | Pre-call **and** host it as an API (includes On-fly routes). |
| `pip install "salesbuff[all]"` | Everything. |

> Extras are **additive** — they layer optional dependencies onto the core.
> Pre-call SDK symbols load **lazily** so `salesbuff[onfly]` never forces
> pre-call-only deps like `rapidfuzz`.

### Host it from the terminal (no code)

```bash
pip install "salesbuff[precall,api]"
# set OPENAI_API_KEY + TAVILY_API_KEY in your env (or a .env), then:
salesbuff-serve --port 8000        # defaults to $PORT or 8000
```

### As a library (SDK)

```python
from salesbuff import SalesBuff

async with SalesBuff(openai_api_key="sk-...", tavily_api_key="tvly-...") as sb:
    result = await sb.research("Meeting the VP of Ops at Acme Health next week...")
    print(result.brief)   # Actions brief (or None)
    print(result.facts)   # Facts dossier (or None)
```

One-shot synchronous helper (for scripts/notebooks):

```python
from salesbuff import research_once

result = research_once(
    "Expanding our rollout at Acme Health...",
    openai_api_key="sk-...",
    tavily_api_key="tvly-...",
)
```

`courtlistener_token=...` is optional (enables court-record lookups). Advanced
tuning (`research_concurrency`, `openai_model`, …) can be passed as keyword args.

> The FastAPI service is just a thin host over this same SDK — both share one
> engine, so they never drift.

---

## Setup (local)

Run everything from the `SalesBuff/` directory (the parent of the `salesbuff`
package).

```bash
cd SalesBuff
pip install -r salesbuff/requirements.txt
cp salesbuff/.env.example salesbuff/.env     # fill in your keys
uvicorn salesbuff.api:app --port 8000 --reload
```

Health check: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.

There's also a CLI for quick local pre-call runs:

```bash
python -m salesbuff "Meeting the VP of Ops at Acme Health next week..."
```

---

## Environment variables

Set in `salesbuff/.env` locally, or in the Render dashboard in production.
See `salesbuff/.env.example` for the full template.

### Required

| Var | Purpose |
|-----|---------|
| `OPENAI_API_KEY` | Brief + facts + entity resolution + On-fly tips |
| `TAVILY_API_KEY` | Web search + deep research + On-fly reactive lookup |

### Core / pre-call

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENAI_MODEL` | `gpt-4o-mini` | Default chat model |
| `COURTLISTENER_TOKEN` | — | Legal/court records (optional) |
| `USAGE_MAX` | `25` | Shared-quota runs before users must bring their own keys |
| `USAGE_CURRENT` | `0` | Runs already consumed (in-memory counter) |
| `MAX_CASES_PER_ENTITY` | `8` | Court cases kept per company |
| `TAVILY_MAX_RESULTS` | `5` | Web search results |
| `TAVILY_SEARCH_DEPTH` | `basic` | Tavily search depth |
| `LEGAL_BATCH_SIZE` | `10` | Court cases processed per batch |
| `TAVILY_RESEARCH_MODEL` | `mini` | Tavily Deep Research model (pre-call) |
| `TAVILY_RESEARCH_CONCURRENCY` | `6` | Max in-flight deep-research tasks |
| `TAVILY_RESEARCH_POLL_INTERVAL` | `4.0` | Seconds between poll attempts |
| `TAVILY_RESEARCH_MAX_POLLS` | `60` | Max polls before timeout |
| `TAVILY_RESEARCH_OUTPUT_LENGTH` | `standard` | Deep research output size |

### On-fly live coaching

| Var | Default | Purpose |
|-----|---------|---------|
| `ONFLY_TIP_MODEL` | `OPENAI_MODEL` | Fast model for hot-path JSON tips |
| `ONFLY_COMPACTION_MODEL` | `OPENAI_MODEL` | Model for async transcript compaction |
| `ONFLY_COMPACT_CHUNK_THRESHOLD` | `10` | Compact when unsummarized chunks exceed this |
| `ONFLY_COMPACT_TOKEN_THRESHOLD` | `3000` | …or when raw unsummarized text exceeds this |
| `ONFLY_SUMMARY_MAX_TOKENS` | `3000` | Target size for compacted summary |
| `ONFLY_RAW_TAIL_CHUNKS` | `3` | Recent chunks kept verbatim |
| `ONFLY_REACTIVE_SEARCH_MAX` | `3` | Max quick reactive searches per session |
| `ONFLY_DEEP_RESEARCH_MAX` | `2` | Max deep (multi-query) research runs per session |
| `ONFLY_DEEP_MAX_QUERIES` | `3` | Tavily queries per deep research run |
| `ONFLY_TIP_TYPE_WINDOW` | `3` | Dedup window for repeated tip types |
| `ONFLY_SESSION_LOG` | `1` | Dump JSON session log on end (`0`/`false` to disable) |
| `ONFLY_LOG_DIR` | `salesbuff/onfly_log/` | Directory for session log files |

---

## API

### Pre-call

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/research` | Submit `{ "prompt": "...", "keys"?: {openai, tavily, courtlistener} }` → `{ request_id, status, usage }` |
| `GET` | `/research/{id}` | Poll → `{ status, stage, progress, brief, facts, warnings, error }` |
| `GET` | `/usage` | `{ used, limit, remaining }` |
| `GET` | `/health` | Liveness probe |

- Without user `keys`, runs count against the shared `USAGE_MAX` (HTTP **429** when exhausted).
- With valid user `keys`, the run **bypasses** the quota and uses a throwaway
  client; bad keys return **400** with a clear message.

### On-fly

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/onfly/sessions` | Create session `{ pasted_context, spoken_setup, precall_brief?, precall_facts?, max_tips, tts_enabled }` → `{ session_id, expires_at }` |
| `POST` | `/onfly/sessions/{id}/chunks` | Ingest transcript chunk `{ text, manual? }` |
| `GET` | `/onfly/sessions/{id}` | Current session state (tips, stage, etc.) |
| `GET` | `/onfly/sessions/{id}/events` | SSE stream of new tips |
| `DELETE` | `/onfly/sessions/{id}` | End session; returns `{ ended, log }` path if logging enabled |

Sessions are in-memory (2-hour TTL). Keep **one backend instance** in production.

---

## Project structure

```
salesbuff/
├── api.py              # FastAPI app: pre-call jobs + mounts /onfly
├── core.py             # CoreContainer — shared LLM + search (no feature deps)
├── container.py        # Container extends Core — wires pre-call pipeline (DI)
├── pipeline.py         # orchestrates resolve → research → brief
├── config.py           # env → frozen Config
├── client.py           # SDK entry (SalesBuff, research_once)
├── ports/              # abstract interfaces (LLM, web, legal)
├── adapters/           # OpenAI, Tavily, CourtListener implementations
├── precall/            # pre-call feature: resolve, web, legal, deep, brief, facts
├── onfly/              # live coaching: coach, session, prompts, api routes
├── domain/             # prompts, framing, grounding rules, source tiers, YAML loader
├── domain_logic_sales/ # editable YAML: categories, questions, ranking, compliance
└── models/             # typed shapes: entities, findings, brief, facts, onfly
```

The **ports/adapters** split is what lets a user bring their own keys at runtime
(a different adapter, same pipeline) and makes the LLM/search providers swappable.
**Core** is shared; **precall** and **onfly** are separate features that both
build on Core.

---

## Deploy (Render)

Use the blueprint at the repo root ([`../render.yaml`](../render.yaml)) or set
manually:

- **Root Directory:** `SalesBuff`
- **Build:** `pip install -r salesbuff/requirements.txt` *(or `pip install ".[api]"` — same result via `pyproject.toml`)*
- **Start:** `uvicorn salesbuff.api:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Instances: 1** — the job store, usage counter, and live sessions live in
  memory, so multiple instances would split state.

Set `OPENAI_API_KEY` and `TAVILY_API_KEY` (and optionally `COURTLISTENER_TOKEN`)
as dashboard secrets. On-fly vars are optional — defaults work out of the box.
