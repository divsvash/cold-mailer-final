"""Strict Pydantic schemas for job understanding output."""
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SeniorityLevel(StrEnum):
    INTERN    = "intern"; JUNIOR   = "junior"; MID      = "mid"
    SENIOR    = "senior"; STAFF    = "staff";  PRINCIPAL= "principal"
    LEAD      = "lead";   MANAGER  = "manager";DIRECTOR = "director"
    EXECUTIVE = "executive"; UNKNOWN = "unknown"


class Domain(StrEnum):
    FINTECH="fintech"; HEALTHCARE="healthcare"; ECOMMERCE="ecommerce"
    DEVTOOLS="devtools"; AI_ML="ai_ml"; ENTERPRISE_SAAS="enterprise_saas"
    CONSUMER_SOCIAL="consumer_social"; EDTECH="edtech"; GAMING="gaming"
    CYBERSECURITY="cybersecurity"; LOGISTICS="logistics"; REAL_ESTATE="real_estate"
    MEDIA="media"; GOVERNMENT="government"; ENERGY="energy"
    OTHER="other"; UNKNOWN="unknown"


class CultureTrait(StrEnum):
    FAST_PACED="fast_paced"; REMOTE_FIRST="remote_first"; COLLABORATIVE="collaborative"
    AUTONOMOUS="autonomous"; DATA_DRIVEN="data_driven"; CUSTOMER_OBSESSED="customer_obsessed"
    HIERARCHICAL="hierarchical"; FLAT_STRUCTURE="flat_structure"; WORK_LIFE_BALANCE="work_life_balance"
    HIGH_INTENSITY="high_intensity"; MISSION_DRIVEN="mission_driven"; INNOVATION_FOCUSED="innovation_focused"
    PROCESS_HEAVY="process_heavy"; STARTUP_CULTURE="startup_culture"; DIVERSE_INCLUSIVE="diverse_inclusive"


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name:     str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class BusinessProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(..., min_length=10, max_length=300)
    priority:    str = Field(..., pattern="^(primary|secondary)$")


class JobUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    must_have_skills:  list[Skill]          = Field(..., max_length=20)
    preferred_skills:  list[Skill]          = Field(default_factory=list, max_length=20)
    domain:            Domain               = Field(...)
    seniority:         SeniorityLevel       = Field(...)
    business_problems: list[BusinessProblem]= Field(..., min_length=1, max_length=10)
    culture:           list[CultureTrait]   = Field(default_factory=list, max_length=8)

    @property
    def primary_business_problems(self) -> list[BusinessProblem]:
        return [bp for bp in self.business_problems if bp.priority == "primary"]

    @property
    def all_skill_names(self) -> list[str]:
        return [s.name for s in self.must_have_skills + self.preferred_skills]


class JobUnderstandingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_description: str = Field(..., min_length=20)


class JobUnderstandingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: JobUnderstanding
    model:  str
