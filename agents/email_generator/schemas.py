"""Pydantic schemas for the email generation agent."""
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class CandidateSkill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str; category: str; level: str = "intermediate"
    years: float | None = None; evidence: list[str] = Field(default_factory=list)


class CandidateProject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str; description: str
    tech_stack: list[str] = Field(default_factory=list)
    metrics:    list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class CandidateExperience(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str; company: str; period: str
    bullets:  list[str] = Field(default_factory=list)
    tech_used:list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name:  str; headline: str | None = None; summary: str | None = None
    skills:     list[CandidateSkill]      = Field(default_factory=list)
    projects:   list[CandidateProject]    = Field(default_factory=list)
    experience: list[CandidateExperience] = Field(default_factory=list)
    contact:    dict = Field(default_factory=dict)


class JobSkill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str; category: str


class BusinessProblem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str; priority: str = "secondary"


class JobAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    must_have_skills:  list[JobSkill]        = Field(default_factory=list)
    preferred_skills:  list[JobSkill]        = Field(default_factory=list)
    domain:    str = "unknown"; seniority: str = "unknown"
    business_problems: list[BusinessProblem] = Field(default_factory=list)
    culture:   list[str] = Field(default_factory=list)


class CompanyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name:           str = Field(..., min_length=1)
    one_liner:      str | None = None
    recent_news:    str | None = None
    role_title:     str | None = None
    recipient_name: str | None = None
    recipient_role: str | None = None


class VariantType(StrEnum):
    TECHNICAL = "technical"
    FOUNDER   = "founder"
    CONCISE   = "concise"


class EmailVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant_type: VariantType
    subject:    str = Field(..., min_length=1, max_length=120)
    body:       str = Field(..., min_length=1)
    word_count: int = Field(..., ge=0)

    @property
    def within_word_limit(self) -> bool:
        from agents.email_generator.engine import MAX_WORDS
        return self.word_count <= MAX_WORDS


class EmailRanking(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant_type:        VariantType
    expected_reply_rate: float = Field(..., ge=0.0, le=1.0)
    reasoning:           str   = Field(..., min_length=1, max_length=400)


class RankedEmailResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variants:     list[EmailVariant] = Field(..., max_length=3)
    rankings:     list[EmailRanking] = Field(..., max_length=3)
    best_variant: EmailVariant

    @property
    def best_expected_reply_rate(self) -> float:
        for r in self.rankings:
            if r.variant_type == self.best_variant.variant_type:
                return r.expected_reply_rate
        return 0.0
