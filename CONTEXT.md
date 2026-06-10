# SalesBuff — Domain glossary

> Implementation-free language shared across Pre-call and On-fly.

## Packaging

**Core** — The shared foundation every feature reuses: configuration, the language-model client, and the web-search client. Has no knowledge of any specific feature and can run on its own.

**Pre-call** — The feature that turns a one-line meeting description into a researched brief and fact dossier before a call. Builds on Core.

**On-fly** — The feature that coaches a rep live during a call. Builds on Core and never requires Pre-call.

> Installing the On-fly feature alone is enough to run live coaching; it does not pull in Pre-call.

## On-fly

**Live session** — A single in-call coaching run from Start live coach until End. Holds seed context, transcript memory, tips, and optional research cache. Expires after 2 hours or on end.

**Seed context** — Background the coach knows before listening: pasted notes, call goal, optional pre-call brief, and optional bootstrap research. Frozen or refreshed at session boundaries, not replaced by live transcript.

**Transcript chunk** — One slice of live speech text sent from the browser (scheduled ~every 25s, or manual “Get tip now”).

**Conversation memory** — What the tip model sees from the live call: **compacted summary** of older chunks + **raw tail** (recent chunks verbatim) + **current chunk**. Not the full raw transcript on every tip call.

**Compacted summary** — Structured, iteratively updated digest of older transcript chunks. Produced by a separate compaction step; must preserve sales-critical facts (stakeholders, objections, budget/timeline, commitments, open questions).

**Raw tail** — The last 3 transcript chunks kept verbatim so coaching stays tied to the immediate moment (~75s at 25s intervals).

**Compaction trigger** — Run when unsummarized chunks exceed 10 **or** raw unsummarized text exceeds ~3k tokens (whichever comes first).

**Bootstrap research** — One-time (or gap-fill) web lookup at session start to enrich seed context when pre-call brief or notes are thin. Cached for the session; not repeated every chunk.

**Reactive research** — Mid-call Tavily lookup triggered when the tip LLM flags a specific gap (competitor, ROI proof, news). Async; never blocks immediate tips. **Quick** = one Tavily search; **deep** = several searches whose results the LLM synthesizes into one battlecard-style tip.

## Models (On-fly)

**Tip model** — Fast OpenAI model for hot-path JSON tips (default `gpt-4o-mini`, env `ONFLY_TIP_MODEL`).

**Compaction model** — OpenAI model for async transcript summarization (default `gpt-4o-mini`, env `ONFLY_COMPACTION_MODEL`). Plain text, not JSON.

**Deep Research** — Tavily's slow multi-step research pipeline with its own models. Used in **pre-call** only, not On-fly.

**Immediate tip** — Fast coaching move from the hot path (~1–3s), source `Live`.

**Research-backed tip** — Coaching move informed by Tavily (or similar) web research, source `Research-backed`. Never blocks immediate tips.

**Coaching move** — One short, verb-first action sentence the rep can use now (not a vague question to the AI).
