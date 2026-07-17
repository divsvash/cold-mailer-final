"""Domain models for the job fetcher agent."""
from __future__ import annotations
import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class JobSource(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER      = "lever"
    YC         = "yc"


class RawJob(BaseModel):
    source:          JobSource
    source_id:       str
    raw_html:        str
    fetched_at:      datetime   = Field(default_factory=datetime.utcnow)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedJob(BaseModel):
    title:       str
    company:     str
    location:    str | None = None
    url:         str
    description: str
    posted_at:   datetime | None = None
    source:      JobSource
    source_id:   str
    dedup_key:   str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.dedup_key:
            raw = f"{self.title.lower()}|{self.company.lower()}|{self.url.lower().rstrip('/')}"
            self.dedup_key = hashlib.sha256(raw.encode()).hexdigest()

    @property
    def _normalised_url(self) -> str:
        return self.url.strip().rstrip("/")


class ScrapeResult(BaseModel):
    source:     JobSource
    raw_jobs:   list[RawJob]        = Field(default_factory=list)
    jobs:       list[NormalizedJob] = Field(default_factory=list)
    errors:     list[str]           = Field(default_factory=list)
    scraped_at: datetime            = Field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        return len(self.jobs) > 0

    @property
    def error_count(self) -> int:
        return len(self.errors)
