"""Domain models for recipient discovery."""
from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContactSource(StrEnum):
    """Where an address was quoted from. There is no "guessed" source."""
    POSTING = "posting"            # inside the stored job posting text
    COMPANY_PAGE = "company_page"  # on a public company page fetched live


class ContactStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ContactCandidate(BaseModel):
    """A discovered possible recipient for one exact stored job.

    Every email is quoted from source text (a job posting or a public page).
    A candidate is a lead for human review, not a verified recipient: an
    address appearing on a page does not prove it belongs to the hiring team
    or that mail to it will be delivered.
    """
    model_config = ConfigDict(extra="forbid")
    job_dedup_key: str
    email: EmailStr
    name: str | None = None
    role: str | None = None
    source: ContactSource
    provenance: str           # "job posting" or the exact page URL
    context: str = ""         # short quoted snippet around the find
    status: ContactStatus = ContactStatus.PROPOSED
    discovered_at: datetime = Field(default_factory=datetime.utcnow)


class NameLead(BaseModel):
    """A hiring-related role mention without an email, for manual lookup."""
    model_config = ConfigDict(extra="forbid")
    job_dedup_key: str
    description: str          # keyword plus a short quoted snippet
    provenance: str


class JobDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_dedup_key: str
    company: str = ""
    title: str = ""
    candidates: list[ContactCandidate] = Field(default_factory=list)
    leads: list[NameLead] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DiscoveryScanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[JobDiscoveryResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    new_candidates: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None

    @property
    def candidate_count(self) -> int:
        return sum(len(r.candidates) for r in self.results)
