<!-- 🟡 SalesBuff backend -->

# 🟡 SalesBuff — Backend (FastAPI)

The Python service that turns a sales rep's prompt into a citation-grounded
**Actions** brief and a **Facts** dossier. Built with FastAPI + asyncio.

> Architecture deep-dive (folders, data flow, prompts): see
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## What it does

One request runs a 3-stage pipeline:

1. **Resolve** — figure out the real buyer, contact, seller, **meeting motion**
   (expansion vs displacement), and any competitor to beat. *(LLM → Tavily search → LLM)*
2. **Research** — deep-research each entity on the web; optionally search court
   records. *(Tavily Deep Research + CourtListener)*
3. **Brief** — from one shared fact pack, generate **Actions** (coaching moves)
   and **Facts** (evidence dossier) concurrently, then **ground** every card to a
   real source URL. *(OpenAI)*

Because a full run takes ~1–2 minutes, the API is **job-based**: submit, then poll.

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

There's also a CLI for quick local runs:

```bash
python -m salesbuff "Meeting the VP of Ops at Acme Health next week..."
```

---

## Environment variables

Set in `salesbuff/.env` locally, or in the Render dashboard in production.

| Var | Required | Default | Purpose |
|-----|:--------:|---------|---------|
| `OPENAI_API_KEY` | ✅ | — | Brief + facts + entity resolution |
| `TAVILY_API_KEY` | ✅ | — | Web search + deep research |
| `OPENAI_MODEL` | | `gpt-4o-mini` | Chat model |
| `COURTLISTENER_TOKEN` | | — | Legal/court records (optional) |
| `USAGE_MAX` | | `25` | Shared-quota runs before users must bring their own keys |
| `USAGE_CURRENT` | | `0` | Runs already consumed (in-memory counter) |
| `MAX_CASES_PER_ENTITY` | | `8` | Court cases kept per company |
| `TAVILY_MAX_RESULTS` | | `5` | Web search results |
| `TAVILY_SEARCH_DEPTH` | | `basic` | Tavily depth |

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/research` | Submit `{ "prompt": "...", "keys"?: {openai, tavily, courtlistener} }` → `{ request_id, status, usage }` |
| `GET` | `/research/{id}` | Poll → `{ status, stage, progress, brief, facts, warnings, error }` |
| `GET` | `/usage` | `{ used, limit, remaining }` |
| `GET` | `/health` | Liveness probe |

- Without user `keys`, runs count against the shared `USAGE_MAX` (HTTP **429** when exhausted).
- With valid user `keys`, the run **bypasses** the quota and uses a throwaway
  client; bad keys return **400** with a clear message.

---

## Project structure

```
salesbuff/
├── api.py            # FastAPI app: submit/poll jobs, usage limiter
├── pipeline.py       # orchestrates resolve → research → brief
├── container.py      # wires adapters into the pipeline (DI)
├── config.py         # env → frozen Config
├── ports/            # abstract interfaces (LLM, web, legal)
├── adapters/         # OpenAI, Tavily, CourtListener implementations
├── research/         # resolve, web, legal, deep, brief, facts
├── domain/           # prompts, framing, grounding rules, source tiers, YAML loader
├── domain_logic_sales/   # editable YAML: categories, questions, ranking, compliance
└── models/           # typed shapes: entities, findings, brief, facts
```

The **ports/adapters** split is what lets a user bring their own keys at runtime
(a different adapter, same pipeline) and makes the LLM/search providers swappable.

---

## Deploy (Render)

Use the blueprint at the repo root ([`../render.yaml`](../render.yaml)) or set
manually:

- **Root Directory:** `SalesBuff`
- **Build:** `pip install -r salesbuff/requirements.txt`
- **Start:** `uvicorn salesbuff.api:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Instances: 1** — the job store and usage counter live in memory, so multiple
  instances would split state.

Set `OPENAI_API_KEY` and `TAVILY_API_KEY` (and optionally `COURTLISTENER_TOKEN`)
as dashboard secrets.
