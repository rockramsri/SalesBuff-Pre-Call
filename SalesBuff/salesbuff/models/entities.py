"""Core entity definitions for a sales research session."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EntityRole(str, Enum):
    PROSPECT_COMPANY = "prospect_company"
    CONTACT_PERSON = "contact_person"
    INCUMBENT_VENDOR = "incumbent_vendor"


class MeetingMotion(str, Enum):
    """The kind of deal motion — drives whether we attack a competitor or not."""

    EXPANSION = "expansion"        # seller already in the account; grow usage
    DISPLACEMENT = "displacement"  # replace a named competitor
    RENEWAL = "renewal"            # keep/renew existing seller contract
    RESCUE = "rescue"              # fix a struggling existing deployment
    DISCOVERY = "discovery"        # new logo, no clear competitor


@dataclass(frozen=True)
class CurrentDeployment:
    """A solution already live at the prospect (may be the seller's own)."""

    vendor: str | None = None
    scope: str | None = None
    evidence_note: str | None = None


@dataclass(frozen=True)
class ProspectCompany:
    name: str
    domain: str | None = None
    industry: str | None = None
    location: str | None = None
    size_hint: str | None = None
    # Name variants for court-record search (from entity resolution).
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContactPerson:
    full_name: str
    company_name: str
    title: str | None = None
    linkedin_url: str | None = None


@dataclass(frozen=True)
class IncumbentVendor:
    name: str
    domain: str | None = None
    product_category: str | None = None
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SalesContext:
    prospect: ProspectCompany
    contact: ContactPerson
    # `incumbent` = a competitor to DISPLACE. It is never the seller itself.
    incumbent: IncumbentVendor | None = None
    rep_product: str | None = None
    rep_company: str | None = None
    # What kind of meeting this is (expansion vs displacement, etc.).
    meeting_motion: MeetingMotion = MeetingMotion.DISCOVERY
    # A solution already live at the prospect (often the seller's own product).
    current_deployment: CurrentDeployment | None = None
    # Other options the buyer might weigh / the do-nothing path.
    named_alternatives: list[str] = field(default_factory=list)
    status_quo: str | None = None
    # Free-text credibility / disambiguation note from entity resolution.
    resolution_note: str | None = None
