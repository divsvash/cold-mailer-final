"""Pydantic schemas for recruiter simulator inputs and outputs."""
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class SkillLevel(StrEnum):
    BEGINNER="beginner"; INTERMEDIATE="intermediate"; ADVANCED="advanced"; EXPERT="expert"


class CandidateSkill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name:     str
    category: str
    level:    SkillLevel = SkillLevel.INTERMEDIATE
    years:    float | None = None
    evidence: list[str]    = Field(default_factory=list)


class CandidateProject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name:       str
    description:str
    tech_stack: list[str] = Field(default_factory=list)
    metrics:    list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class CandidateExperience(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title:    str;  company: str;  period: str
    bullets:  list[str] = Field(default_factory=list)
    tech_used:list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name:  str
    headline:   str | None = None
    summary:    str | None = None
    skills:     list[CandidateSkill]      = Field(default_factory=list)
    projects:   list[CandidateProject]    = Field(default_factory=list)
    experience: list[CandidateExperience] = Field(default_factory=list)

    def all_skill_names_lower(self) -> set[str]:
        return {s.name.lower() for s in self.skills}

    def total_experience_years(self) -> float:
        years = [s.years for s in self.skills if s.years is not None]
        return max(years) if years else 0.0


class JobSkill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str;  category: str


class BusinessProblem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str;  priority: str = "secondary"


class JobRequirements(BaseModel):
    model_config = ConfigDict(extra="ignore")
    must_have_skills:  list[JobSkill]       = Field(default_factory=list)
    preferred_skills:  list[JobSkill]       = Field(default_factory=list)
    domain:    str = "unknown";  seniority: str = "unknown"
    business_problems: list[BusinessProblem]= Field(default_factory=list)
    culture:   list[str] = Field(default_factory=list)

    def must_have_names_lower(self) -> set[str]:
        return {s.name.lower() for s in self.must_have_skills}

    def preferred_names_lower(self) -> set[str]:
        return {s.name.lower() for s in self.preferred_skills}


class Strength(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:  str = Field(..., min_length=1, max_length=120)
    detail: str = Field(..., min_length=1, max_length=400)


class Concern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:    str = Field(..., min_length=1, max_length=120)
    detail:   str = Field(..., min_length=1, max_length=400)
    severity: str = Field(..., pattern="^(low|medium|high)$")


class SkillCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    must_have_total:    int = Field(..., ge=0);  must_have_matched:  int = Field(..., ge=0)
    preferred_total:    int = Field(..., ge=0);  preferred_matched:  int = Field(..., ge=0)
    missing_must_haves: list[str] = Field(default_factory=list)
    missing_preferred:  list[str] = Field(default_factory=list)
    matched_must_haves: list[str] = Field(default_factory=list)
    matched_preferred:  list[str] = Field(default_factory=list)

    @property
    def must_have_ratio(self) -> float:
        return 1.0 if self.must_have_total == 0 else self.must_have_matched / self.must_have_total

    @property
    def preferred_ratio(self) -> float:
        return 1.0 if self.preferred_total == 0 else self.preferred_matched / self.preferred_total


class RecruiterAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fit_score:             float = Field(..., ge=0.0, le=1.0)
    callback_probability:  float = Field(..., ge=0.0, le=1.0)
    interview_probability: float = Field(..., ge=0.0, le=1.0)
    strengths:      list[Strength] = Field(default_factory=list, max_length=10)
    concerns:       list[Concern]  = Field(default_factory=list, max_length=10)
    skill_coverage: SkillCoverage
    candidate_name: str;  job_seniority: str;  job_domain: str
