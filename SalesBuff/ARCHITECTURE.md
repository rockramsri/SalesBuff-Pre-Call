# SalesBuff Backend — How It Works

A plain-English tour of the backend: what happens from the moment a rep hits
"Run" to the moment two result tabs (Actions + Facts) appear, and which folder
owns which job.

---

## 1. The 10-second story

> A sales rep types *"I'm selling our scheduling tool to Mercy Hospital, they
> currently use Epic, my contact is Jane Doe, VP of Ops."*
>
> The backend figures out **who** those real entities are, **researches** them
> on the open web + court records, then asks an LLM to turn the verified facts
> into **(A) a coaching brief** ("say this, ask that") and **(B) a facts
> dossier** ("here is what's verifiably true"). Both come back grounded to real
> source URLs.

One run = **resolve → research → write**. That's the whole spine.

---

## 2. The flow (arrows)

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
   │  STAGE 1  resolving   ──►  research/resolve.py                │
   │  STAGE 2  researching ──►  research/web.py + research/legal.py│
   │  STAGE 3  briefing    ──►  research/brief.py + research/facts.py
   └──────┬────────────────────────────────────────────────────────┘
          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Result = { brief (Actions), facts (Dossier) }                │
   │  stored on the Job → frontend reads it on the next poll       │
   └─────────────────────────────────────────────────────────────┘
```

---

## 3. The three stages, in detail

### STAGE 1 — Resolve (who are these people, really?)
**File:** `research/resolve.py` · **Stage name:** `resolving`

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
**Files:** `research/web.py`, `research/legal.py`, `research/deep.py` · **Stage:** `researching`

Two lanes run **in parallel** (`asyncio.gather`):

```
              ┌── WEB lane (research/web.py) ───────────────────────┐
SalesContext ─┤   one Tavily "Deep Research" call PER entity         │
              │   (prospect, contact, optional incumbent)            │
              │   via research/deep.py (submit → poll → validate)    │
              └─────────────────────────────────────────────────────┘
              ┌── LEGAL lane (research/legal.py) ───────────────────┐
              │   CourtListener search for lawsuits, then            │
              │   one batched deep-research call to enrich/verify    │
              └─────────────────────────────────────────────────────┘
                         ▼
            AllWebFindings + LitigationFindings   (models/findings.py)
```

`research/deep.py` is the careful "submit a long job, poll until done, validate
the JSON against a schema" runner. It has a semaphore so we never exceed
Tavily's rate limit.

### STAGE 3 — Write (turn evidence into output)
**Files:** `research/brief.py`, `research/facts.py` · **Stage:** `briefing`

First both builders share **one** bundle of verified facts:

```
build_fact_pack(web, legal)   ← in research/brief.py, used by BOTH lanes
        │
        ├──► research/brief.py  (BriefBuilder)  ──► ACTIONS tab
        │      prompt_card_brief()  "you are a sales coach, give MOVES"
        │      → SalesBrief = cards (say/ask/show/avoid) + opening line + next step
        │
        └──► research/facts.py  (FactsBuilder)  ──► FACTS tab
               prompt_fact_brief()  "you are an analyst, give a sourced DOSSIER"
               → FactsReport = findings grouped by YAML categories
```

Both run concurrently — each is **one independent LLM call**. After the LLM
replies, each builder **grounds** the output: any card/finding whose citation
URL is not in the real research sources gets **dropped** (see
`domain/brief_rules.py`). This is the "a wrong fact loses the deal" safeguard.

---

## 4. What each folder is for

Think of it in **layers**, outside-in:

```
adapters/   ──implements──►  ports/   ──used by──►  research/  ──reads──►  models/ + domain/
(real APIs)                  (contracts)            (the work)            (shapes + rules)
```

| Folder | Role | Analogy |
|--------|------|---------|
| **`api.py`** | HTTP front door (FastAPI). Submit/poll jobs, usage limit, key handling. | The receptionist |
| **`pipeline.py`** | Orchestrates the 3 stages in order. | The conductor |
| **`container.py`** | Wires everything together at startup (dependency injection). | The wiring panel |
| **`config.py`** | Reads env vars (API keys, limits) into a frozen `Config`. | The settings sheet |
| **`ports/`** | **Abstract interfaces** — "an LLM must have `.json()`", "a web source must have `.search()`". No real code. | The job descriptions |
| **`adapters/`** | **Concrete implementations** of the ports — OpenAI, Tavily, CourtListener HTTP clients. | The actual employees |
| **`research/`** | The actual work: resolve, web, legal, deep, brief, facts. Talks only to *ports*, never directly to OpenAI/Tavily. | The workers |
| **`models/`** | **Pydantic/dataclass shapes** of all data: `entities`, `findings`, `brief`, `facts`. Pure structure, no logic. | The forms/templates |
| **`domain/`** | Sales **knowledge in code**: prompt builders (`prompts.py`), framing (`framing.py`), grounding rules (`brief_rules.py`), YAML loader (`sales_logic.py`). | The playbook |
| **`domain_logic_sales/`** | The **editable YAML playbook**: fact categories, question bank, ranking, compliance overlays. Change behavior without touching Python. | The rulebook (binder you can edit) |
| **`metrics.py` / `utils.py`** | Timing/usage logging and small helpers (id generation). | The stopwatch + toolbox |

### Why `ports/` + `adapters/` are split (the key design idea)
`research/` code says *"give me an `LlmClient`"* — it does **not** know or care
that it's OpenAI. That means:
- You can swap OpenAI for another model by writing one new adapter.
- Tests can pass a fake adapter.
- The user's **own API keys** at runtime just build a different adapter
  (`Container.from_keys`) — nothing else changes.

---

## 5. Where the prompts live (and how "examples" work)

All prompts are plain strings in **`domain/prompts.py`** — no I/O, easy to edit:

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

---

## 6. The "bring your own keys" + usage limit path

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

## 7. One-line summary per file

- `api.py` — receive request, manage job + usage, return progress.
- `pipeline.py` — run resolve → research → write, report stage.
- `container.py` — build all the pieces and connect them.
- `config.py` — load settings from environment.
- `research/resolve.py` — figure out the real entities (LLM + Tavily, 3 shots).
- `research/web.py` — deep-research each entity on the web.
- `research/legal.py` — find + verify lawsuits.
- `research/deep.py` — run/poll/validate a Tavily deep-research task.
- `research/brief.py` — build the **Actions** coaching brief + share the fact pack.
- `research/facts.py` — build the **Facts** dossier from the same facts + YAML.
- `domain/prompts.py` — all the LLM prompts.
- `domain/framing.py` — turn entities into readable context; legal risk framing.
- `domain/brief_rules.py` — drop any card/finding without a real source URL.
- `domain/sales_logic.py` — load the YAML playbook.
- `domain_logic_sales/*.yaml` — editable categories, questions, ranking, compliance.
- `models/*` — typed shapes for entities, findings, brief, facts.
- `ports/*` — abstract contracts for the LLM and data sources.
- `adapters/*` — real OpenAI / Tavily / CourtListener clients.
