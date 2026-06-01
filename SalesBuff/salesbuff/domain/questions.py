"""Per-entity research question sets."""

PROSPECT_COMPANY_QUESTIONS: dict[str, list[str]] = {
    "financial_health": [
        "What is their current funding stage and when did they last raise money?",
        "Are they expanding (headcount, new sites) or contracting (layoffs, cost cuts)?",
        "Is there a new budget cycle starting that creates a buying window?",
        "For healthcare: are they for-profit or non-profit, standalone or part of a system?",
    ],
    "leadership_triggers": [
        "Have they hired a new C-suite or department head in the last 90 days?",
        "Is there a newly promoted VP or director in the department we're selling into?",
        "Did they recently merge, get acquired, or spin off a division?",
        "New leaders = biggest sales trigger. Flag any leadership change immediately.",
    ],
    "buying_signals": [
        "Are they actively hiring in the department the rep is selling into?",
        "What pain points do their job descriptions reveal?",
        "Did they announce a new initiative or strategic priority that our product supports?",
        "Have they issued an RFP or published a vendor evaluation in our category?",
    ],
    "pain_and_instability": [
        "Are there reports of internal dysfunction, high turnover, or poor morale?",
        "Have customers or partners publicly complained about their service quality?",
        "Are there operational issues (delays, outages, recalls) that create urgency?",
    ],
    "legal_exposure": [
        "Are they being sued by a vendor or partner for breach of contract?",
        "Any regulatory action, FDA warning, or compliance investigation?",
        "Any employment discrimination or wrongful termination suits that signal internal issues?",
    ],
}

CONTACT_PERSON_QUESTIONS: dict[str, list[str]] = {
    "career_and_role": [
        "How long have they been in this role? (<12 months = prove-yourself mode, open to wins)",
        "Where did they work before? Do they have history with our product category?",
        "Have they recently been promoted? (ambition + fresh mandate = openness to change)",
        "Did they come from a competitor? (knows the landscape, may have strong opinions)",
    ],
    "public_voice_and_priorities": [
        "Do they write, speak, or post about problems our product solves?",
        "Have they given conference talks or podcast interviews we can reference?",
        "What topics do they care about publicly? Use this to open the call.",
        "Did they recently publish an article or LinkedIn post that reveals their priorities?",
    ],
    "rapport_and_icebreakers": [
        "Shared alma mater, previous employer, or city with the rep?",
        "Mutual connections (LinkedIn 2nd-degree) that could be a warm intro?",
        "Public hobbies, causes, or interests that humanize the conversation?",
        "Did they attend a conference or event recently that the rep can reference?",
    ],
    "buying_intent_and_pain": [
        "Have they publicly complained about a problem we solve?",
        "Have they left a review (positive or negative) of our product or a competitor on G2?",
        "Have they asked questions on forums or communities that our product answers?",
        "Did they respond to or engage with content about our product category?",
    ],
}

INCUMBENT_VENDOR_QUESTIONS: dict[str, list[str]] = {
    "legal_exposure": [
        "Are they currently being sued BY their own customers? (strongest displacement signal)",
        "Any product liability or personal injury suits? (product failure signal)",
        "Any fraud or securities suits? (financial instability signal)",
        "Any class action suits? (systemic failure, not isolated incident)",
        "Any regulatory enforcement actions in our product category?",
    ],
    "customer_complaints": [
        "Are there recurring negative patterns on G2, Trustpilot, Capterra, or Reddit?",
        "Do customers complain about support speed, product reliability, or billing practices?",
        "How has their rating trended over the last 12 months? (declining = displacement window)",
        "Are there industry-specific forum complaints (healthcare forums, pharma listservs)?",
    ],
    "employee_churn_and_health": [
        "Is their engineering or product team losing people fast? (product quality at risk)",
        "What do Glassdoor reviews say about leadership and direction?",
        "Have they announced layoffs in the last 12 months? (operational risk)",
        "Are their Glassdoor ratings declining? (morale collapse = delivery risk)",
    ],
    "financial_instability": [
        "Did they do a down round, miss a fundraise, or show burn pressure?",
        "Any press about cost-cutting, pivots, or existential challenges?",
        "Are they public? If so, recent earnings misses or guidance cuts?",
        "Any M&A uncertainty (being acquired, trying to sell) that creates vendor lock-in risk?",
    ],
    "contract_and_switching_intel": [
        "What is the typical contract length in this product category?",
        "Are there reports of aggressive auto-renewal clauses or lock-in?",
        "Any customer complaints about difficulty cancelling or getting refunds?",
        "Are there signals that their contracts are up for renewal soon?",
    ],
    "product_and_delivery_gaps": [
        "Are there known product quality issues, outages, or delivery failures?",
        "Any recall, safety notice, or regulatory hold on their product?",
        "Are there feature gaps that customers consistently request but don't get?",
        "Are their SLAs weaker than what the rep is offering? Get specifics.",
    ],
}
