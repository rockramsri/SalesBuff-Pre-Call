# SalesBuff Backend — How It Works

A plain-English tour of the backend: **Pre-call** (due diligence before a meeting)
and **On-fly** (live coaching during a call), and which folder owns which job.

> Package layout (v0.2.0): **Core** (`core.py`) → shared LLM + search clients.
> **Pre-call** (`precall/`) and **On-fly** (`onfly/`) are separate features that
> both build on Core. See [`../CONTEXT.md`](../CONTEXT.md) for the glossary.

---

## 1. The 10-second story

### Pre-call

> A sales rep types *"I'm selling our scheduling tool to Mercy Hospital, they
> currently use Epic, my contact is Jane Doe, VP of Ops."*
>
> The backend figures out **who** those real entities are, **researches** them
> on the open web + court records, then asks an LLM to turn the verified facts
> into **(A) a coaching brief** ("say this, ask that") and **(B) a facts
> dossier** ("here is what's verifiably true"). Both come back grounded to real
> source URLs.

One pre-call run = **resolve → research → write**.

### On-fly

> During a live call, the rep starts a session with optional pre-call context,
> speaks into the mic, and receives **verb-first coaching tips** as transcript
> chunks arrive (~every 25s or on "Get tip now"). Older speech is **compacted**
> into a structured summary; recent speech stays verbatim. The coach can trigger
> async Tavily lookups (quick or deep multi-query) when it detects gaps.

One live session = **prepare → chunk → tip** (with optional compaction + research).

---

## 2. Pre-call flow (arrows)

```
   ┌─────────────┐
   │  FRONTEND   │  rep types prompt (+ optionally their own API keys)
   └──────┬──────┘
          │  POST /research  { prompt, keys? }
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  api.py  (FastAPI — the front door)                           │
   │  • check usage limit OR accept user's own keys                │
   │  • make a Job, return request_id immediately (run is ~1-2min) │
   │  • frontend then polls GET /research/{id} for progress        │
   └──────┬────────────────────────────────────────────────────────┘
          │  hands the prompt to…
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  pipeline.py  (the conductor)                                 │
   │                                                               │
   │  STAGE 1  resolving   ──►  precall/resolve.py                │
   │  STAGE 2  researching ──►  precall/web.py + precall/legal.py│
   │  STAGE 3  briefing    ──►  precall/brief.py + precall/facts.py
   └──────┬────────────────────────────────────────────────────────┘
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Result = { brief (Actions), facts (Dossier) }                │
   │  stored on the Job → frontend reads it on the next poll       │
   └─────────────────────────────────────────────────────────────┘
```

---

## 3. On-fly flow (arrows)

```
   ┌─────────────┐
   │  FRONTEND   │  pasted context + optional pre-call brief/facts
   └──────┬──────┘
          │  POST /onfly/sessions
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  onfly/api.py  +  onfly/coach.py                              │
   │  prepare_session:                                             │
   │    • extract DealBrief from seed context (LLM, once)            │
   │    • bootstrap Tavily search if context is thin (optional)    │
   └──────┬────────────────────────────────────────────────────────┘
          │  loop while call is live
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  POST /onfly/sessions/{id}/chunks  { text, manual? }          │
   │                                                               │
   │  handle_chunk:                                                │
   │    1. maybe compact older chunks → structured summary         │
   │    2. prompt_live_tip (summary + raw tail + current chunk)    │
   │    3. validate candidate (dedup, generic filter, cooldown)    │
   │    4. if needs_research → async quick/deep Tavily lookup      │
   │    5. push accepted tip → SSE GET …/events                    │
   └──────┬────────────────────────────────────────────────────────┘
          │  DELETE /onfly/sessions/{id}
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  finalize_session → JSON log (onfly_log/) if ONFLY_SESSION_LOG│
   └─────────────────────────────────────────────────────────────┘
```

On-fly uses **`CoreContainer`** only (`core.py`) — it never imports `precall/` or
`pipeline.py`. Session state and tips live **in memory** (same single-instance
constraint as pre-call jobs).

---

## 4. Pre-call stages, in detail

### STAGE 1 — Resolve (who are these people, really?)
**File:** `precall/resolve.py` · **Stage name:** `resolving`

This is exactly the "3-shot" flow you described:

```
rep prompt
   │
   │ shot 1: LLM  ──► prompt_resolve_query()   "turn this into a web search query + rough names"
   ▼
search query
   │ shot 2: Tavily search + extract  (NOT deep research — fast)   ──► raw web evidence
   ▼
evidence (titles, urls, snippets)
   │ shot 3: LLM  ──► prompt_resolve_verify()  "confirm official names, aliases, relationship"
   ▼
SalesContext   ← the clean, typed answer (models/entities.py)
```

`SalesContext` = prospect company + contact person + (optional) incumbent vendor
+ what the rep sells. Everything downstream reads from this one object. If the
LLM fails, there's a `_fallback_context` so the run never crashes.

### STAGE 2 — Research (go find real evidence)
**Files:** `precall/web.py`, `precall/legal.py`, `precall/deep.py` · **Stage:** `researching`

Two lanes run **in parallel** (`asyncio.gather`):

```
              ┌── WEB lane (precall/web.py) ───────────────────────┐
SalesContext ─┤   one Tavily "Deep Research" call PER entity         │
              │   (prospect, contact, optional incumbent)            │
              │   via precall/deep.py (submit → poll → validate)    │
              └─────────────────────────────────────────────────────┘
              ┌── LEGAL lane (precall/legal.py) ───────────────────┐
              │   CourtListener search for lawsuits, then            │
              │   one batched deep-research call to enrich/verify    │
              └─────────────────────────────────────────────────────┘
                         ▼
            AllWebFindings + LitigationFindings   (models/findings.py)
```

`precall/deep.py` is the careful "submit a long job, poll until done, validate
the JSON against a schema" runner. It has a semaphore so we never exceed
Tavily's rate limit.

### STAGE 3 — Write (turn evidence into output)
**Files:** `precall/brief.py`, `precall/facts.py` · **Stage:** `briefing`

First both builders share **one** bundle of verified facts:

```
build_fact_pack(web, legal)   ← in precall/brief.py, used by BOTH lanes
        │
        ├──► precall/brief.py  (BriefBuilder)  ──► ACTIONS tab
        │      prompt_card_brief()  "you are a sales coach, give MOVES"
        │      → SalesBrief = cards (say/ask/show/avoid) + opening line + next step
        │
        └──► precall/facts.py  (FactsBuilder)  ──► FACTS tab
               prompt_fact_brief()  "you are an analyst, give a sourced DOSSIER"
               → FactsReport = findings grouped by YAML categories
```

Both run concurrently — each is **one independent LLM call**. After the LLM
replies, each builder **grounds** the output: any card/finding whose citation
URL is not in the real research sources gets **dropped** (see
`domain/brief_rules.py`). This is the "a wrong fact loses the deal" safeguard.

---

## 5. What each folder is for

Think of it in **layers**, outside-in:

```
adapters/   ──implements──►  ports/   ──used by──►  precall/ + onfly/  ──reads──►  models/ + domain/
(real APIs)                  (contracts)            (the work)                    (shapes + rules)
                              ▲
                         core.py  (shared LLM + search — no feature deps)
```

| Folder | Role | Analogy |
|--------|------|---------|
| **`api.py`** | HTTP front door (FastAPI). Pre-call jobs, usage limit, mounts `/onfly`. | The receptionist |
| **`core.py`** | `CoreContainer` — shared config, LLM, Tavily. No feature imports. | The shared toolkit |
| **`pipeline.py`** | Orchestrates pre-call resolve → research → write. | The pre-call conductor |
| **`container.py`** | Extends Core; wires pre-call pipeline (DI). | The pre-call wiring panel |
| **`config.py`** | Reads env vars (API keys, limits, On-fly tuning) into a frozen `Config`. | The settings sheet |
| **`ports/`** | **Abstract interfaces** — "an LLM must have `.json()`", "a web source must have `.search()`". No real code. | The job descriptions |
| **`adapters/`** | **Concrete implementations** of the ports — OpenAI, Tavily, CourtListener HTTP clients. | The actual employees |
| **`precall/`** | Pre-call work: resolve, web, legal, deep, brief, facts. Talks only to *ports*. | Pre-call workers |
| **`onfly/`** | Live coaching: session store, coach, prompts, API routes. Uses Core only. | Live coach workers |
| **`models/`** | **Pydantic/dataclass shapes** — entities, findings, brief, facts, onfly tips/sessions. | The forms/templates |
| **`domain/`** | Pre-call **knowledge in code**: prompts, framing, grounding rules, YAML loader. | The pre-call playbook |
| **`onfly/prompts.py`** | On-fly prompts: deal brief extraction, live tip, compaction, background tip. | The live coach playbook |
| **`domain_logic_sales/`** | The **editable YAML playbook**: fact categories, question bank, ranking, compliance. | The rulebook (binder you can edit) |
| **`metrics.py` / `utils.py`** | Timing/usage logging and small helpers (id generation). | The stopwatch + toolbox |

### Why `ports/` + `adapters/` are split (the key design idea)
`precall/` code says *"give me an `LlmClient`"* — it does **not** know or care
that it's OpenAI. That means:
- You can swap OpenAI for another model by writing one new adapter.
- Tests can pass a fake adapter.
- The user's **own API keys** at runtime just build a different adapter
  (`Container.from_keys`) — nothing else changes.

---

## 6. Where the prompts live (and how "examples" work)

### Pre-call

All pre-call prompts are plain strings in **`domain/prompts.py`** — no I/O, easy to edit:

| Prompt | Used by | Job |
|--------|---------|-----|
| `prompt_resolve_query` | resolve (shot 1) | rep text → search query + rough names |
| `prompt_resolve_verify` | resolve (shot 3) | evidence → confirmed entities |
| `prompt_web_deep_research` | web lane | what to dig up per entity |
| `prompt_legal_deep_research` | legal lane | verify/enrich court cases |
| `prompt_card_brief` | Actions builder | facts → coaching **moves** |
| `prompt_fact_brief` | Facts builder | facts → sourced **dossier** |

The "examples" aren't few-shot samples — they're **embedded JSON schemas** inside
each prompt. The prompt literally shows the exact JSON shape it wants back, and
the matching Pydantic model in `models/` validates that the LLM obeyed. If the
LLM returns junk, validation fails and the builder retries once, then drops it.

For the Facts lane, part of the prompt is **assembled from the YAML**:
`FactsBuilder._category_block()` and `_question_block()` read
`domain_logic_sales/` and inject the categories + relevant questions + the
industry compliance guardrail straight into `prompt_fact_brief`. So editing a
YAML file changes what the LLM is told — no code change needed.

### On-fly

On-fly prompts live in **`onfly/prompts.py`**:

| Prompt | Used by | Job |
|--------|---------|-----|
| `prompt_deal_brief` | `prepare_session` | seed context → structured `DealBrief` |
| `prompt_live_tip` | `handle_chunk` | memory + chunk → JSON tip candidate |
| `prompt_compact_transcript` | compaction | older chunks → structured summary |
| `prompt_background_tip` | reactive research | Tavily results → battlecard-style tip |

The live-tip prompt includes stage playbook, research-trigger rules, and a one-shot
example so the model flags `needs_research` (quick vs deep) reliably.

---

## 7. The "bring your own keys" + usage limit path

```
POST /research
   │
   ├── keys provided & complete?
   │        │
   │   YES ─┴─► Container.from_keys()  → validate keys → run (NO limit)
   │
   └── NO ──► shared server keys → check usage_used < usage_max
                    │
                    ├─ over limit ─► 429 "add your own keys"
                    └─ ok ─► usage_used += 1 → run
```

The usage counter lives **in memory** on the API process (that's why Render must
run a single instance). User-supplied keys bypass the limit entirely and get a
throwaway container that's closed when the job finishes.

---

## 8. One-line summary per file

- `api.py` — receive pre-call request, manage job + usage; mount `/onfly` router.
- `core.py` — `CoreContainer`: shared LLM + Tavily clients (no feature deps).
- `pipeline.py` — run pre-call resolve → research → write, report stage.
- `container.py` — extend Core; build pre-call pipeline pieces.
- `config.py` — load settings from environment (pre-call + On-fly).
- `precall/resolve.py` — figure out the real entities (LLM + Tavily, 3 shots).
- `precall/web.py` — deep-research each entity on the web.
- `precall/legal.py` — find + verify lawsuits.
- `precall/deep.py` — run/poll/validate a Tavily deep-research task.
- `precall/brief.py` — build the **Actions** coaching brief + share the fact pack.
- `precall/facts.py` — build the **Facts** dossier from the same facts + YAML.
- `onfly/api.py` — live session CRUD, chunk ingest, SSE tip stream.
- `onfly/coach.py` — prepare session, handle chunks, compaction, research, logging.
- `onfly/session.py` — in-memory session store + conversation memory.
- `onfly/prompts.py` — deal brief, live tip, compaction, background tip prompts.
- `domain/prompts.py` — all pre-call LLM prompts.
- `domain/framing.py` — turn entities into readable context; legal risk framing.
- `domain/brief_rules.py` — drop any card/finding without a real source URL.
- `domain/sales_logic.py` — load the YAML playbook.
- `domain_logic_sales/*.yaml` — editable categories, questions, ranking, compliance.
- `models/*` — typed shapes for entities, findings, brief, facts, onfly.
- `ports/*` — abstract contracts for the LLM and data sources.
- `adapters/*` — real OpenAI / Tavily / CourtListener clients.
