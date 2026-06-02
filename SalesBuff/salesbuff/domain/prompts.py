"""LLM prompt builders — pure strings, no I/O."""

from __future__ import annotations

from salesbuff.domain.framing import sales_context_blurb
from salesbuff.models.brief import BriefCategory
from salesbuff.models.entities import SalesContext


def prompt_resolve_query(rep_prompt: str) -> tuple[str, str]:
    """Step 1: turn the rep's prompt into rough anchors + a good web query."""
    system = (
        "You help resolve the real entities in a salesperson's request. Read their "
        "description and return ONLY JSON — no markdown, no preamble.\n\n"
        "Schema:\n"
        "{\n"
        '  "prospect_name": str,            // company being sold TO\n'
        '  "contact_name": str|null,        // specific person, else null\n'
        '  "incumbent_name": str|null,      // current vendor to displace, else null\n'
        '  "rep_product": str|null,         // what the rep sells, plain words\n'
        '  "rep_company": str|null,\n'
        '  "search_query": str              // one strong web search query to confirm the\n'
        "                                   // correct legal names, aliases, and how these\n"
        "                                   // entities relate to each other\n"
        "}\n\n"
        "Rules: extract only what is stated; do not invent names. The search_query should "
        "combine the prospect, contact, and incumbent so a web search returns their official "
        "names, domains, and relationship."
    )
    return system, rep_prompt


def prompt_resolve_verify(rep_prompt: str, anchors: dict | None = None) -> str:
    """Step 3: confirm names, the meeting motion, and who (if anyone) to displace.

    The key distinction: a vendor already in use at the buyer ("current_deployment")
    is NOT automatically the "incumbent_vendor" to beat — and is never the seller.
    """
    anchors = anchors or {}
    anchor_line = (
        "FIRST-PASS EXTRACTION (treat as strong hints, correct only with clear evidence):\n"
        f"- prospect: {anchors.get('prospect_name') or 'unknown'}\n"
        f"- contact: {anchors.get('contact_name') or 'unknown'}\n"
        f"- competitor to displace: {anchors.get('incumbent_name') or 'none found'}\n"
        f"- seller company: {anchors.get('rep_company') or 'unknown'}\n"
        f"- seller product: {anchors.get('rep_product') or 'unknown'}\n\n"
    )
    return (
        "You are validating a SALES MEETING context using web evidence — not doing generic "
        "entity matching. Identify the buyer, the contact, the seller + product, the meeting "
        "motion, what is already deployed, and who (if anyone) must be displaced.\n\n"
        f"REP REQUEST: {rep_prompt}\n\n"
        f"{anchor_line}"
        "You will receive a JSON list of web results (title, url, content).\n\n"
        "HARD BUSINESS RULES (follow exactly):\n"
        "- If the request mentions expansion, rollout, scale, broader adoption, pilot expansion, "
        "or that the seller is ALREADY in use, then meeting_motion = \"expansion\".\n"
        "- If the seller's own company is already used at the buyer, record it under "
        "current_deployment.vendor — NOT as incumbent_vendor.\n"
        "- incumbent_vendor means a DIFFERENT vendor being displaced in this meeting. It is "
        "NEVER the seller. If there is no different competitor to beat, set incumbent_vendor = null.\n"
        "- In an expansion/renewal/rescue motion, incumbent_vendor is usually null.\n"
        "- If there is no single vendor to beat, leave incumbent_vendor null and capture "
        "named_alternatives and/or the status_quo (e.g. manual notes, no tooling).\n"
        "- aliases = legal-suffix/former-name variants of the SAME entity only — never a "
        "same-named but different company.\n"
        "- Prefer official buyer/seller pages and reputable press over personal sites or social.\n\n"
        "Reply ONLY as JSON:\n"
        "{\n"
        '  "prospect_company": {"name": str, "aliases": [str], "industry": str|null, "location": str|null, "domain": str|null},\n'
        '  "contact_person": {"full_name": str, "title": str|null, "company": str},\n'
        '  "rep_company": str|null,\n'
        '  "rep_product": str|null,\n'
        '  "meeting_motion": "expansion|displacement|renewal|rescue|discovery",\n'
        '  "current_deployment": {"vendor": str|null, "scope": str|null, "evidence_note": str|null}|null,\n'
        '  "incumbent_vendor": {"name": str, "aliases": [str], "product_category": str|null}|null,\n'
        '  "named_alternatives": [str],\n'
        '  "status_quo": str|null,\n'
        '  "note": str\n'
        "}\n"
        "contact_person.full_name falls back to the prospect name if no person was given."
    )


def prompt_web_deep_research(
    subject: str, subject_type: str, role: str, context: str
) -> str:
    """Deep-research input for one entity's sales-relevant web profile."""
    if role == "incumbent_vendor":
        focus = (
            "Find evidence the rep can use to DISPLACE this vendor: customer complaints, "
            "outages/recalls/delays, layoffs and engineering churn, financial trouble, "
            "lawsuits, regulatory actions, and aggressive lock-in/auto-renewal practices."
        )
    elif subject_type == "person":
        focus = (
            "Find rapport and intent signals: their role and tenure, career background, "
            "public talks/podcasts/interviews, articles or posts, priorities they voice, "
            "and any pain points relevant to the rep's offering."
        )
    else:
        focus = (
            "Find timing and trigger signals: recent news, leadership changes, hiring, "
            "funding/financial results, expansions or cutbacks, regulatory items, and "
            "publicly reported pain points or initiatives."
        )

    return (
        f"Research the {subject_type} {subject!r} for a B2B sales rep.\n"
        f"SALES CONTEXT: {context}\n\n"
        f"{focus}\n\n"
        "Search news, finance pages, the entity's own site, social posts, podcasts, and "
        "review/forum sites. Be strict about identity: include ONLY material clearly about "
        "this specific entity, not a same-named different one. Every finding MUST carry the "
        "exact source URL. Prefer recent, sales-relevant facts over generic background. "
        "Return a short summary plus a list of distinct findings."
    )


def prompt_legal_deep_research(context: str, subject: str, cases_json: str) -> str:
    """Perplexity-style batch validation + enrichment of CourtListener dockets."""
    return (
        "You are doing legal due diligence for a B2B sales rep. Perform web searches to "
        "confirm details and locate authoritative sources for each case below.\n"
        f"TARGET COMPANY: {subject!r}\n"
        f"SALES CONTEXT: {context}\n\n"
        "For EACH case in the input list, decide involvement and enrich it:\n"
        "- involved = true if the target company (or a clear name variant) is a named party "
        "in the case — INCLUDING suits brought against it by individuals, customers, patients, "
        "employees, or competitors (product liability, negligence, employment, contract, fraud, "
        "antitrust, or regulatory matters all count). Set false ONLY when the named party is a "
        "DIFFERENT company that merely shares the name, or the target is not actually a party. "
        "When the company is clearly named as plaintiff or defendant, set true.\n"
        "- sales_relevant = true if the case is useful in a sales conversation (budget freeze, "
        "compliance urgency, vendor unreliability, leadership instability).\n"
        "- risk_type = one of fraud, product_liability, breach_of_contract, employment, "
        "antitrust, other.\n"
        "- status = current status/outcome if known.\n"
        "- summary = one to two sentence, fact-only, sales-facing description (no legal advice, "
        "no speculation).\n"
        "- sources = URLs you used to verify the case.\n"
        "- id = echo the case id from the input EXACTLY.\n\n"
        f"CASES (JSON):\n{cases_json}\n\n"
        "Return one entry per input case."
    )


def prompt_card_brief(ctx: SalesContext, guardrails: str = "") -> str:
    """System prompt for the move-based, citation-grounded sales coach brief.

    Motion-aware: in an expansion (seller already deployed) it must NOT coach the
    rep to attack their own product.
    """
    product = ctx.rep_product or "the rep's solution"
    categories = ", ".join(c.value for c in BriefCategory)
    motion = ctx.meeting_motion.value
    beat = _beat_line(ctx)
    guard_block = f"\n{guardrails.strip()}\n" if guardrails.strip() else ""
    return f"""You are a senior sales coach. A rep from {(ctx.rep_company or 'the seller')!r} is about
to pitch {product!r} to {ctx.prospect.name!r} (contact: {ctx.contact.full_name!r}, {ctx.contact.title or "unknown title"}).
Meeting motion: {motion}. {beat}

SALES CONTEXT: {sales_context_blurb(ctx)}
{guard_block}
You are given verified FACTS (JSON). Each web fact has a "url" and a "tier"
(1=official, 2=trade press, 3=interview/talk, 4=review/social). Legal facts carry a
"sales_frame". Turn them into CONVERSATION MOVES the rep can use.

UNIT OF OUTPUT — one card per MOVE, not one card per fact:
- A card is something the rep should SAY, ASK, SHOW, AVOID, or VERIFY in the meeting.
- Multiple facts may support one move. Combine them; do not make a card per raw fact.
- Usually produce 6-10 cards, ordered by how the call flows.

MOTION RULES (critical):
- expansion / renewal / rescue: the seller is ALREADY in the account. Focus on broader
  adoption, new workflows/teams, proof for rollout, governance, and the next-step ask.
  NEVER write a card that attacks, doubts, or raises reliability concerns about the seller's
  own product. Do NOT treat the seller as the competitor.
- displacement: focus on buyer pain, the named incumbent's gaps, proof, switching safety, next step.
- discovery (no competitor): differentiate against the status quo / no-decision inertia.

COVERAGE — include at least:
- 1 opening_move, 1 pain_hypothesis OR priority_signal,
  1 differentiation_angle OR proof_point, and 1 next_step.
- Add rapport_hook, stakeholder_hint, objection_prep, watch_out only when supportable.

CLAIM-SUPPORT RULES:
- A source only supports claims about the entity/topic it actually describes. A buyer's
  security incident shows the BUYER cares about security — it does NOT prove the seller is secure.
- Allegations in lawsuits are allegations, not proven facts — frame them that way.
- Tier-4 (review/social) facts are weak: use them only for watch_out / open_question or prep,
  never as a standalone proof_point or differentiation_angle.

CARD WRITING RULES:
- "title": 4-8 words, keyword-first, literal, useful on its own. Never vague.
- "preview": ONE standalone action line the rep can act on without opening details.
- "talk_track": one or two exact sentences the rep can actually say.
- "detail": the supporting evidence + why it matters.
- "action_type": one of say, ask, show, avoid, verify.
- "use_when": one of opening, discovery, differentiation, objection, close, follow_up.

HARD RULES (high-stakes — a wrong fact loses the deal):
- Every card MUST include citations with "url" copied EXACTLY from a fact's "url". Never invent URLs.
- Use source "web" for web facts and "court_listener" for legal case facts.
- If you cannot support a card with a provided URL, DROP the card.
- "opening_line" must restate your opening_move card — introduce NO new facts.
- "next_step_line" must ask for a realistic next commitment.
- open_question and rapport_hook cards may have zero citations; all others MUST have at least one.
- Do NOT output card ids or timestamps — the system assigns those.

Categories (use exactly these values): {categories}

Reply ONLY as JSON:
{{
  "subject": {{
    "prospect": "{ctx.prospect.name}",
    "contact": "{ctx.contact.full_name}",
    "incumbent": {json_nullable(ctx.incumbent.name if ctx.incumbent else None)}
  }},
  "opening_line": "one sentence the rep can open with",
  "next_step_line": "the concrete next step to ask for",
  "cards": [
    {{
      "category": "opening_move",
      "action_type": "say",
      "use_when": "opening",
      "title": "keyword-first headline (4-8 words)",
      "preview": "standalone action line — enough to act on alone",
      "talk_track": "exact words the rep can say",
      "detail": "supporting evidence + why it matters (the 'See more')",
      "priority": "high|medium|low",
      "confidence": "high|medium|low",
      "citations": [{{"source": "web|court_listener", "url": "exact-url", "title": "", "quote": ""}}]
    }}
  ]
}}"""


def _beat_line(ctx: SalesContext) -> str:
    """One sentence telling the model what (if anything) to position against."""
    if ctx.incumbent and ctx.incumbent.name and ctx.incumbent.name != ctx.rep_company:
        return f"The competitor to displace is {ctx.incumbent.name!r}."
    if ctx.current_deployment and ctx.current_deployment.vendor == ctx.rep_company:
        return "The seller is already deployed here — this is about expanding, not winning the account."
    if ctx.named_alternatives:
        return f"Alternatives the buyer may weigh: {', '.join(ctx.named_alternatives)}."
    return "There is no single competitor to beat — position against the status quo / no decision."


def prompt_fact_brief(
    ctx: SalesContext,
    category_block: str,
    question_block: str,
    guardrails: str,
) -> str:
    """System prompt for the FACTS tab — an evidence dossier, not advice."""
    return f"""You are a research analyst building an EVIDENCE DOSSIER for a sales rep.
This is NOT advice and NOT tips — it is what is verifiably TRUE about the account,
organized for fast reference.

SALES CONTEXT: {sales_context_blurb(ctx)}

You are given verified FACTS (JSON). Each web fact has a "url" and a "tier"
(1=official, 2=trade press, 3=interview/talk, 4=review/social); legal facts carry a
"sales_frame". Turn them into concise, sourced findings. Treat tier-4 facts as weak —
use them only as open_questions or clearly-hedged notes, never as a strong claim.

QUESTIONS THE DOSSIER SHOULD HELP ANSWER:
{question_block}

CATEGORIES (use the exact key on the left for each finding's "category"):
{category_block}

WRITING RULES:
- "headline": 4-8 words, specific and literal (a fact, not a tip).
- "detail": the evidence, stated factually. No "say this" / "ask this" language.
- "why_it_matters": one line on relevance to the deal.
- Group multiple facts into one finding when they describe the same thing.
- Skip a category if there is no real evidence for it. Do not pad.

{guardrails}

HARD CITATION RULES:
- Every finding MUST include citations with "url" copied EXACTLY from a fact's "url".
- Use source "web" for Tavily facts and "court_listener" for legal case facts.
- If you cannot support a finding with a provided URL, DROP it (except open_questions).
- Never invent URLs. No speculation, no legal advice.

Reply ONLY as JSON:
{{
  "findings": [
    {{
      "category": "one of the category keys above",
      "headline": "specific factual headline (4-8 words)",
      "detail": "the evidence, stated factually",
      "why_it_matters": "one line on why it matters to the deal",
      "citations": [{{"source": "web|court_listener", "url": "exact-url", "title": "", "quote": ""}}]
    }}
  ]
}}"""


def json_nullable(value: str | None) -> str:
    if value is None:
        return "null"
    return f'"{value}"'
