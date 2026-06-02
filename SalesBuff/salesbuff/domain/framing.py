"""Sales framing helpers and context builders."""

from __future__ import annotations

from salesbuff.models.entities import (
    ContactPerson,
    CurrentDeployment,
    EntityRole,
    IncumbentVendor,
    MeetingMotion,
    ProspectCompany,
    SalesContext,
)

RISK_TYPE_SALES_FRAME: dict[str, dict[str, str]] = {
    "breach_of_contract": {
        "label": "Contract breach suit",
        "implication": (
            "Their customers have taken them to court over failed commitments. "
            "Ask the prospect if they've had similar issues."
        ),
    },
    "product_liability": {
        "label": "Product failure / liability suit",
        "implication": (
            "A customer alleged their product caused harm or failed in service. "
            "Directly relevant if you're offering a safer or more reliable alternative."
        ),
    },
    "fraud": {
        "label": "Fraud / securities suit",
        "implication": (
            "Financial integrity is in question. Raise vendor financial stability "
            "as a procurement risk — hospitals can't afford a vendor going under mid-contract."
        ),
    },
    "employment": {
        "label": "Employment / labor suit",
        "implication": (
            "Internal dysfunction signal. High turnover in their team means "
            "your prospect's account may not get consistent service."
        ),
    },
    "antitrust": {
        "label": "Antitrust / competition suit",
        "implication": (
            "They may be using anti-competitive practices to lock customers in. "
            "Ask if the prospect feels locked in and what switching would cost them."
        ),
    },
    "other": {
        "label": "Other litigation",
        "implication": "Review the case details for relevance to vendor reliability.",
    },
}


def get_sales_frame(risk_type: str) -> dict[str, str]:
    return RISK_TYPE_SALES_FRAME.get(risk_type, RISK_TYPE_SALES_FRAME["other"])


def sales_context_blurb(ctx: SalesContext) -> str:
    parts: list[str] = []
    if ctx.rep_product:
        seller = f" ({ctx.rep_company})" if ctx.rep_company else ""
        parts.append(f"A sales rep{seller} is selling {ctx.rep_product}.")
    prospect = ctx.prospect.name
    if ctx.prospect.industry:
        prospect += f", a {ctx.prospect.industry} org"
    if ctx.prospect.location:
        prospect += f" in {ctx.prospect.location}"
    parts.append(f"Selling to {prospect}.")

    # Motion-aware positioning line — never frame the seller as the vendor to beat.
    deployed = ctx.current_deployment.vendor if ctx.current_deployment else None
    if deployed and deployed == ctx.rep_company:
        parts.append(
            f"This is an {ctx.meeting_motion.value} motion: {ctx.rep_company} is already "
            "deployed here, so the goal is to broaden adoption — not to win the account."
        )
    elif ctx.incumbent and ctx.incumbent.name and ctx.incumbent.name != ctx.rep_company:
        inc = ctx.incumbent.name
        if ctx.incumbent.product_category:
            inc += f" (provides {ctx.incumbent.product_category})"
        parts.append(f"Trying to displace the incumbent vendor {inc}.")
    elif ctx.named_alternatives:
        parts.append(f"The buyer may weigh: {', '.join(ctx.named_alternatives)}.")
    else:
        sq = ctx.status_quo or "the status quo / no decision"
        parts.append(f"No single competitor to beat — positioning against {sq}.")

    parts.append(f"Contact: {ctx.contact.full_name} ({ctx.contact.title or 'unknown title'}).")
    return " ".join(parts)


def describe_entity(ctx: SalesContext, role: EntityRole) -> str:
    if role == EntityRole.PROSPECT_COMPANY:
        desc = ctx.prospect.name
        if ctx.prospect.industry:
            desc += f" (industry: {ctx.prospect.industry})"
        if ctx.prospect.location:
            desc += f" in {ctx.prospect.location}"
        return desc
    if role == EntityRole.CONTACT_PERSON:
        desc = ctx.contact.full_name
        if ctx.contact.title:
            desc += f", {ctx.contact.title}"
        desc += f", at {ctx.contact.company_name}"
        return desc
    if role == EntityRole.INCUMBENT_VENDOR and ctx.incumbent:
        desc = ctx.incumbent.name
        if ctx.incumbent.product_category:
            desc += f" (provides {ctx.incumbent.product_category})"
        return desc
    return ""


def _clean_aliases(raw: object, *, exclude: str = "") -> list[str]:
    out: list[str] = []
    seen = {exclude.strip().lower()} if exclude else set()
    for value in raw if isinstance(raw, list) else []:
        if not isinstance(value, str):
            continue
        name = value.strip()
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _coerce_motion(value: object) -> MeetingMotion:
    if isinstance(value, str):
        key = value.strip().lower()
        for m in MeetingMotion:
            if m.value == key:
                return m
    return MeetingMotion.DISCOVERY


def sales_context_from_resolution(data: dict) -> SalesContext:
    """Map the entity-resolution JSON into a SalesContext.

    Applies the core safety guard: the seller can never be its own incumbent.
    If the model marks the seller (or its current deployment) as the incumbent,
    we drop the incumbent and treat the meeting as an expansion.
    """
    pc = data.get("prospect_company") or {}
    cp = data.get("contact_person") or {}
    iv = data.get("incumbent_vendor") or {}
    cd = data.get("current_deployment") or {}

    prospect_name = pc.get("name") or "Unknown Company"
    prospect = ProspectCompany(
        name=prospect_name,
        industry=pc.get("industry"),
        location=pc.get("location"),
        domain=pc.get("domain"),
        aliases=_clean_aliases(pc.get("aliases"), exclude=prospect_name),
    )
    contact = ContactPerson(
        full_name=cp.get("full_name") or prospect_name,
        company_name=cp.get("company") or prospect_name,
        title=cp.get("title"),
    )

    rep_company = data.get("rep_company")
    motion = _coerce_motion(data.get("meeting_motion"))

    current_deployment = None
    if isinstance(cd, dict) and cd.get("vendor"):
        current_deployment = CurrentDeployment(
            vendor=cd.get("vendor"),
            scope=cd.get("scope"),
            evidence_note=cd.get("evidence_note"),
        )

    incumbent_name = iv.get("name") if isinstance(iv, dict) else None
    # GUARD: the seller is never its own incumbent. If the model set the
    # incumbent to the rep's own company (the classic expansion misread), drop it.
    if incumbent_name and rep_company and _same_company(incumbent_name, rep_company):
        if current_deployment is None:
            current_deployment = CurrentDeployment(
                vendor=rep_company,
                evidence_note="Seller already deployed (auto-corrected from incumbent).",
            )
        incumbent_name = None
        if motion == MeetingMotion.DISPLACEMENT or motion == MeetingMotion.DISCOVERY:
            motion = MeetingMotion.EXPANSION

    incumbent = (
        IncumbentVendor(
            name=incumbent_name,
            product_category=iv.get("product_category"),
            aliases=_clean_aliases(iv.get("aliases"), exclude=incumbent_name),
        )
        if incumbent_name
        else None
    )

    return SalesContext(
        prospect=prospect,
        contact=contact,
        incumbent=incumbent,
        rep_product=data.get("rep_product"),
        rep_company=rep_company,
        meeting_motion=motion,
        current_deployment=current_deployment,
        named_alternatives=_clean_aliases(data.get("named_alternatives")),
        status_quo=data.get("status_quo"),
        resolution_note=data.get("note"),
    )


def _same_company(a: str, b: str) -> bool:
    """Loose match: same core name after stripping legal suffixes/punctuation."""
    import re

    def norm(s: str) -> str:
        s = re.sub(r"[^\w\s]", " ", s.lower())
        s = re.sub(r"\b(inc|incorporated|llc|corp|corporation|ltd|lp|co|company|ai)\b", "", s)
        return re.sub(r"\s+", " ", s).strip()

    na, nb = norm(a), norm(b)
    return bool(na) and (na == nb or na in nb or nb in na)
