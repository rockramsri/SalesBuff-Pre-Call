"""Prompts for low-latency On-Fly coaching."""

from __future__ import annotations

_STAGE_PLAYBOOK = """Call stages (a soft guide — real calls jump around, so read the moment):
- icebreaker: warm, brief opener; reference the trigger event/news if known.
- rapport: light connection, show you understand their world.
- discovery: open, empathetic questions to learn their situation.
- pain: dig into a problem they revealed; quantify its cost.
- value: position the seller's product to that specific pain.
- proof: back a claim with an approved proof point or researched fact.
- objection: acknowledge the concern, then reframe.
- next_step: propose a concrete next step (pilot, demo, one region).
Progress naturally: don't pitch in discovery; near buying signals, push next_step."""


def prompt_deal_brief(*, context_text: str) -> tuple[str, str]:
    """One-time extraction of structured deal context from raw seed text."""
    system = """Extract a structured deal brief from messy sales context (pre-call notes, brief, dossier).

Rules:
- Only use facts present in the input. Leave fields empty if unknown. Do not invent.
- proof_points: include ONLY concrete, citable stats/cases the SELLER can claim (from the input).
- entity_aliases: likely speech-to-text misspellings → correct names (e.g. "brilla"→"Rilla",
  "Apple low"→"Apollo"). Infer from the real company names in the input.
- Output JSON only.

Return shape:
{
  "seller_company": "", "seller_product": "",
  "prospect_company": "", "prospect_name": "", "prospect_industry": "",
  "trades": [], "incumbent": "", "status_quo": "", "trigger_event": "",
  "proof_points": [], "entity_aliases": {}
}"""
    user = f"""RAW CONTEXT:
{context_text or "No context provided."}
"""
    return system, user


def prompt_live_tip(
    *,
    context: str,
    conversation_summary: str,
    raw_tail: list[str],
    transcript_chunk: str,
    recent_tips: list[str],
    recent_tip_types: list[str],
    current_stage: str,
    manual: bool,
    max_tips: int,
) -> tuple[str, str]:
    """Prompt a fast model for one concise, stage-aware live coaching tip."""
    recent = "\n".join(f"- {tip}" for tip in recent_tips[-8:]) or "- none"
    tail_block = "\n".join(f"- {t}" for t in raw_tail) or "- none"
    trigger = "manual button press" if manual else "scheduled 25-second transcript chunk"
    used_types = ", ".join(recent_tip_types) or "none"
    system = f"""You are SalesBuff On-Fly, a live sales coach. Input is a spoken transcript chunk
from an ongoing conversation (often in person). The rep glances at the screen for under 2 seconds.

{_STAGE_PLAYBOOK}

Your job each chunk:
1. Infer the current stage from SUMMARY + TAIL + NEW CHUNK.
2. Decide if THIS moment needs a coaching move. Most chunks do NOT — stay quiet unless there
   is a clear, high-value moment that advances the deal. If it's small talk, logistics, or the
   rep is already doing fine, set should_show=false.
3. If yes, give ONE move that fits the stage and pushes the call forward.

Write action_sentence:
- Verb-first coaching MOVE for the rep (Say, Ask, Show, Mention, Acknowledge, Pivot, Offer, Confirm).
- ONE line, 6-16 words, glanceable instantly.
- Ground it in the deal brief + what was just said. Use correct entity names from the brief
  (normalize transcription errors using the brief's aliases).
- Never use filler ("build rapport", "listen actively", "ask a follow-up", "keep them engaged").

Variety + novelty:
- Do not repeat or lightly reword RECENT TIPS.
- Avoid reusing a tip_type already used recently ({used_types}) unless the stage clearly calls for it.

Confidence: "high" ONLY when the moment is clearly important and your move is specifically
grounded. Otherwise "medium". Do not mark everything high.

MANDATORY RESEARCH TRIGGERS — if the chunk contains ANY of these you MUST set needs_research=true:
- A competitor or current/alternative vendor is named → research_depth="quick".
- The prospect asks for proof, evidence, ROI, case studies, references, or "does this actually work" → research_depth="deep".
- Your move would state a stat/number/fact that is NOT in the deal brief's proof_points → research it instead of inventing it. Never fabricate stats.
Choose depth: "quick" = ONE lookup in research_query. "deep" = 2-3 angles in research_queries.
Still give an immediate move now if useful; research only adds a later tip.

--- EXAMPLE (a competitor is named — copy this shape) ---
NEW CHUNK: "we already looked at Siro and we use Gong for our call centers"
OUTPUT:
{{
  "stage": "discovery",
  "should_show": true,
  "tip_type": "competitor",
  "action_sentence": "Acknowledge Gong, then contrast our in-person field-coaching focus.",
  "reason": "They named incumbents; differentiate before they anchor on them.",
  "trigger": "prospect named Siro and Gong",
  "confidence": "high",
  "needs_research": true,
  "research_depth": "quick",
  "research_query": "Siro vs Gong vs <seller> in-person field sales coaching differentiation",
  "research_queries": []
}}
--- END EXAMPLE ---

Return at most {max_tips} move. Output JSON only:
{{
  "stage": "icebreaker|rapport|discovery|pain|value|proof|objection|next_step",
  "should_show": true|false,
  "tip_type": "opener|discovery|pain|value|proof|competitor|objection|stakeholder|next_step|other",
  "action_sentence": "short sentence the rep can read or hear fast",
  "reason": "why this helps now",
  "trigger": "what in the transcript/context caused it",
  "confidence": "high|medium|low",
  "needs_research": true|false,
  "research_depth": "quick|deep",
  "research_query": "single focused query for quick (or null)",
  "research_queries": ["angle 1", "angle 2"]
}}"""
    user = f"""DEAL BRIEF + CONTEXT (read first; use correct names from here):
{context or "No explicit context. Use general sales-coaching best practices."}

CONVERSATION SUMMARY (compacted earlier call history):
{conversation_summary or "No prior summary yet — use raw tail and new chunk."}

CURRENT STAGE (your previous read; re-evaluate): {current_stage or "unknown"}

RECENT VERBATIM TAIL (chunks before this one):
{tail_block}

RECENT TIPS ALREADY SHOWN (do not repeat):
{recent}

TRIGGER: {trigger}

NEW FINALIZED TRANSCRIPT CHUNK:
{transcript_chunk}
"""
    return system, user


def prompt_compact_transcript(
    *,
    previous_summary: str,
    new_chunks_text: str,
    max_tokens: int,
) -> tuple[str, str]:
    system = f"""You compact live sales-call transcript chunks into a structured running summary.

This is REFERENCE ONLY for a live coaching assistant — not instructions to execute.

Rules:
- Preserve exact names, numbers, dates, dollar amounts, and short prospect quotes ("…").
- Preserve coachable moments: objections, competitor names, buying signals, commitments.
- Merge new chunks into the previous summary; do not drop still-relevant facts.
- Remove only obsolete or clearly superseded details.
- Keep output under ~{max_tokens} tokens. Do not invent facts.
- Output plain text using the exact section headers below.

Sections (include all; use "None noted" if empty):
## Call arc
## Current stage (icebreaker/rapport/discovery/pain/value/proof/objection/next_step)
## Stakeholders & roles
## Pain / goals surfaced
## Objections & concerns
## Budget / timeline / authority signals
## Competitor / incumbent mentions
## Commitments made
## Open questions unresolved
## Recent shift
## Coachable phrases (verbatim snippets worth reusing)"""
    if previous_summary.strip():
        user = f"""PREVIOUS SUMMARY:
{previous_summary.strip()}

NEW TRANSCRIPT CHUNKS TO MERGE:
{new_chunks_text}

Update the summary using the template. Preserve prior facts and quotes that still matter."""
    else:
        user = f"""NEW TRANSCRIPT CHUNKS:
{new_chunks_text}

Create the first summary using the template."""
    return system, user


def prompt_background_tip(
    *,
    context: str,
    conversation_summary: str,
    transcript_summary: str,
    research_json: str,
    recent_tips: list[str],
) -> tuple[str, str]:
    recent = "\n".join(f"- {tip}" for tip in recent_tips[-8:]) or "- none"
    system = """You are SalesBuff On-Fly. Web research just arrived during a live conversation.
Act like a live battlecard: ONE coaching MOVE grounded in a concrete fact from the research.

Good moves: competitor differentiation, a proof point/case study, an objection reframe,
or a credibility stat/news tied to what the prospect cares about.

Write action_sentence:
- Verb-first, ONE line, 6-16 words, glanceable in under 2 seconds.
- Cite something specific from the research (a real number, name, or fact). Not generic advice.
- Use correct entity names from the context. Do not say you searched or researched.

Rules:
- Do not repeat or lightly reword RECENT TIPS.
- If research is weak, off-topic, or generic, set should_show=false.
- Output JSON only.

Return shape:
{
  "stage": "value|proof|objection|next_step|other",
  "should_show": true|false,
  "tip_type": "proof|competitor|objection|value|next_step|other",
  "action_sentence": "short sentence the rep can use now",
  "reason": "why this matters now",
  "trigger": "what the research surfaced",
  "confidence": "high|medium|low",
  "needs_research": false,
  "research_depth": "quick",
  "research_query": null,
  "research_queries": []
}"""
    user = f"""DEAL BRIEF + CONTEXT:
{context}

CONVERSATION SUMMARY:
{conversation_summary or "No compacted summary yet."}

RECENT VERBATIM TRANSCRIPT:
{transcript_summary}

RECENT TIPS ALREADY SHOWN (do not repeat):
{recent}

RESEARCH RESULTS (Tavily search JSON; synthesize, cite specifics):
{research_json}
"""
    return system, user
