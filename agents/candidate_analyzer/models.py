"""Pydantic models for the candidate profile (PKB)."""
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class SkillLevel(StrEnum):
    BEGINNER="beginner"; INTERMEDIATE="intermediate"; ADVANCED="advanced"; EXPERT="expert"


class SkillCategory(StrEnum):
    LANGUAGE="language"; BACKEND="backend"; FRONTEND="frontend"; AI_ML="ai_ml"
    DEVOPS="devops"; DATABASE="database"; PM="pm"; OTHER="other"


class AchievementType(StrEnum):
    HACKATHON="hackathon"; ACADEMIC="academic"; LEADERSHIP="leadership"
    COMPETITIVE="competitive"; CERTIFICATION="certification"; OPEN_SOURCE="open_source"


class Skill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name:     str
    category: SkillCategory
    level:    SkillLevel   = SkillLevel.INTERMEDIATE
    years:    float | None = Field(None, ge=0)
    evidence: list[str]    = Field(default_factory=list)


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name:       str
    description:str
    tech_stack: list[str] = Field(default_factory=list)
    period:     str | None = None
    status:     str | None = None
    metrics:    list[str] = Field(default_factory=list)
    url:        str | None = None
    highlights: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title:    str
    company:  str
    period:   str
    location: str | None = None
    bullets:  list[str] = Field(default_factory=list)
    tech_used:list[str] = Field(default_factory=list)


class Education(BaseModel):
    model_config = ConfigDict(extra="ignore")
    institution: str
    degree:      str
    field:       str | None = None
    period:      str
    gpa:         str | None = None
    highlights:  list[str]  = Field(default_factory=list)


class Achievement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title:      str
    type:       AchievementType
    date:       str | None = None
    description:str | None = None
    impact:     str | None = None


class ContactInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email:    str | None = None
    phone:    str | None = None
    location: str | None = None
    github:   str | None = None
    linkedin: str | None = None
    portfolio:str | None = None


class Profile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name:    str
    headline:     str | None = None
    summary:      str | None = None
    contact:      ContactInfo  = Field(default_factory=ContactInfo)
    skills:       list[Skill]       = Field(default_factory=list)
    projects:     list[Project]     = Field(default_factory=list)
    experience:   list[Experience]  = Field(default_factory=list)
    education:    list[Education]   = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    sources:      list[str]         = Field(default_factory=list)
    version:      str               = "1.0.0"

    def skills_by_category(self, category: SkillCategory) -> list[Skill]:
        return [s for s in self.skills if s.category == category]

    def top_projects(self, n: int = 3) -> list[Project]:
        return sorted(self.projects, key=lambda p: len(p.metrics), reverse=True)[:n]
