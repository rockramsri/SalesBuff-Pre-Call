"""Core entity definitions for a sales research session."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EntityRole(str, Enum):
    PROSPECT_COMPANY = "prospect_company"
    CONTACT_PERSON = "contact_person"
    INCUMBENT_VENDOR = "incumbent_vendor"


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
    incumbent: IncumbentVendor | None = None
    rep_product: str | None = None
    rep_company: str | None = None
    # Free-text credibility / disambiguation note from entity resolution.
    resolution_note: str | None = None
