<!-- 🟡 SalesBuff -->

[![CI](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/ci.yml/badge.svg)](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/ci.yml)
[![CodeQL](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/codeql.yml/badge.svg)](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/codeql.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-brightgreen?logo=dependabot)](https://github.com/rockramsri/SalesBuff-Pre-Call/security/dependabot)
[![PyPI](https://img.shields.io/pypi/v/salesbuff?color=yellow&label=pip%20install%20salesbuff)](https://pypi.org/project/salesbuff/)

# 🟡 SalesBuff — Pre-call intelligence + live coaching

> Speak your account scenario and SalesBuff helps before **and during** the call:
> **Pre-call** turns a one-liner into citation-grounded **Action tips** and a
> **Fact dossier**; **On-fly** streams real-time coaching moves as the conversation
> unfolds.

SalesBuff resolves the real companies and people involved, researches them across
the web (and court records for pre-call), and produces **citation-grounded**
output — no chat, no fluff.

---

## What it does

### Pre-call (before the meeting)

You give it something like:

> *"Meeting Dr. Lee Schwamm at Yale New Haven Health tomorrow. We're expanding
> our AI clinical-documentation rollout to more physicians."*

…and it returns:

| Tab | What you get |
|-----|--------------|
| **Actions** | Conversation **moves** grouped by call flow — opening move, pain hypothesis, differentiation, proof point, next step. Each is something to *say / ask / show / avoid / verify*, with a talk-track and sources. |
| **Facts** | An **evidence dossier** grouped into domain categories (priorities, pain signals, stakeholders, legal/regulatory, open questions), every finding backed by a source URL. |

Both come from **one** shared research pass, so the two tabs always agree on the
evidence.

### On-fly (during the call)

Start a live session with optional pre-call context, speak into the mic, and get
**verb-first coaching tips** as the call progresses:

- **Conversation memory** — compacts older transcript into a structured summary
  while keeping a raw tail of recent speech.
- **Bootstrap + reactive research** — enriches thin context at session start; mid-call
  Tavily lookups (quick or deep multi-query) when the coach detects gaps (competitor,
  objection, ROI proof, news).
- **Stage-aware tips** — icebreaker → discovery → differentiation → close, with
  dedup and quality filters so cards stay actionable, not generic.
- **Session logs** — full JSON event trace dumped when the session ends (for tuning
  and debugging).

---

## Repository layout

```
SalesBuff-Pre-Call/                ← this repo (git root)
├── README.md                      ← you are here
├── CONTRIBUTING.md                ← how to contribute / push / deploy
├── CONTEXT.md                     ← domain glossary (pre-call + on-fly)
├── render.yaml                    ← Render blueprint for the backend
└── SalesBuff/
    ├── README.md                  ← backend guide (Python / FastAPI)
    ├── salesbuff/                 ← the Python package (API + pipeline + on-fly)
    └── SalesBiff-Frontend/
        ├── README.md              ← frontend guide (TanStack Start)
        └── ...
```

- **Backend** — Python + FastAPI. **Core** (LLM + search clients) shared by
  **Pre-call** (resolve → research → brief) and **On-fly** (live coaching).
  See [`SalesBuff/README.md`](SalesBuff/README.md).
- **Frontend** — TanStack Start + Vite + React + Tailwind. Pre-call brief + On-fly
  live coach in one app. See [`SalesBuff/SalesBiff-Frontend/README.md`](SalesBuff/SalesBiff-Frontend/README.md).
- **Architecture deep-dive** — [`SalesBuff/ARCHITECTURE.md`](SalesBuff/ARCHITECTURE.md).

---

## 🟡 Python package — `salesbuff` on PyPI

The engine is published as a standalone Python package so you can use it directly
in your own code — no server needed.

```bash
pip install salesbuff                        # shared core
pip install "salesbuff[precall]"             # + pre-call due-diligence feature
pip install "salesbuff[onfly]"               # + live coaching (Core only — no precall deps)
pip install "salesbuff[precall,api]"         # + FastAPI host (run salesbuff-serve)
pip install "salesbuff[all]"                 # everything
```

**Pre-call SDK:**

```python
from salesbuff import SalesBuff

async with SalesBuff(openai_api_key="sk-...", tavily_api_key="tvly-...") as sb:
    result = await sb.research(
        "Meeting the VP of Ops at Acme Health next week..."
    )
    print(result.brief)   # Actions coaching brief
    print(result.facts)   # Evidence dossier
```

One-shot sync helper for scripts/notebooks:

```python
from salesbuff import research_once

result = research_once("...", openai_api_key="sk-...", tavily_api_key="tvly-...")
```

**Host it yourself from the terminal** (no code needed):

```bash
pip install "salesbuff[precall,api]"
# set OPENAI_API_KEY + TAVILY_API_KEY in your env, then:
salesbuff-serve --port 8000
```

On-fly live coaching is exposed at `/onfly/*` when the API is running (see
backend README for routes).

📦 [pypi.org/project/salesbuff](https://pypi.org/project/salesbuff/) · **Current version: 0.2.0**

---

## Quickstart (local)

Run the two services in separate terminals.

**1) Backend** (needs OpenAI + Tavily keys)

```bash
cd SalesBuff
pip install -r salesbuff/requirements.txt
cp salesbuff/.env.example salesbuff/.env   # then fill in your keys
uvicorn salesbuff.api:app --port 8000 --reload
```

**2) Frontend**

```bash
cd SalesBuff/SalesBiff-Frontend
npm install
npm run dev            # talks to http://127.0.0.1:8000 by default
```

Open the printed local URL. Use **Pre-call** to run due diligence, or switch to
**On-fly** for live coaching (mic + optional pre-call context).

> 🟡 **No keys?** The UI also lets a user paste their **own** OpenAI + Tavily keys
> (kept in the browser tab only) to run without touching the shared quota.

---

## How the pieces talk

```
Browser ──► Frontend server fns ──► Backend API ──► OpenAI + Tavily + CourtListener
                (SALESBUFF_API_URL)
                     ├── /research/*   pre-call jobs
                     └── /onfly/*       live coaching sessions
```

The browser never calls the backend directly — TanStack server functions proxy
to it, so the backend URL and any keys stay off the client.

---

## Deployment

| Part | Host | Notes |
|------|------|-------|
| Backend | **Render** | Web service, **Root Directory = `SalesBuff`**. Blueprint in [`render.yaml`](render.yaml). Long jobs + in-memory state → keep **1 instance**. |
| Frontend | **Vercel** | **Root Directory = `SalesBuff/SalesBiff-Frontend`**, Nitro `vercel` preset (set in `vite.config.ts`). Set `SALESBUFF_API_URL` to the Render URL. |

Full steps and env vars are in [`CONTRIBUTING.md`](CONTRIBUTING.md) and each
sub-README.

---

## Security

- **Never commit secrets.** `.env` files are git-ignored — use `.env.example` as
  the template and set real values in Render / Vercel.
- If a key is ever exposed, **rotate it** immediately.
