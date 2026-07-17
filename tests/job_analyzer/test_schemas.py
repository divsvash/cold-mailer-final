"""Unit tests for job_analyzer schemas."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from agents.job_analyzer.schemas import (
    BusinessProblem, CultureTrait, Domain, JobUnderstanding, SeniorityLevel, Skill,
)
from tests.job_analyzer.fixtures import INVALID_DOMAIN_INPUT, MISSING_SENIORITY_INPUT, VALID_JU_INPUT


class TestSkill:
    def test_valid(self):
        s = Skill(name="Python", category="language")
        assert s.name == "Python"

    def test_name_stripped(self):
        assert Skill(name="  FastAPI  ", category="backend").name == "FastAPI"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            Skill(name="", category="language")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Skill(name="Python", category="language", years=5)  # type: ignore


class TestBusinessProblem:
    def test_valid_primary(self):
        bp = BusinessProblem(description="Scale the ledger to 10x transaction volume", priority="primary")
        assert bp.priority == "primary"

    def test_invalid_priority(self):
        with pytest.raises(ValidationError):
            BusinessProblem(description="Do something important here really", priority="urgent")

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            BusinessProblem(description="short", priority="primary")


class TestJobUnderstanding:
    def test_constructs_from_valid_input(self):
        ju = JobUnderstanding.model_validate(VALID_JU_INPUT)
        assert ju.domain == Domain.FINTECH
        assert ju.seniority == SeniorityLevel.SENIOR
        assert len(ju.must_have_skills) == 2

    def test_invalid_domain_rejected(self):
        with pytest.raises(ValidationError):
            JobUnderstanding.model_validate(INVALID_DOMAIN_INPUT)

    def test_missing_seniority_rejected(self):
        with pytest.raises(ValidationError):
            JobUnderstanding.model_validate(MISSING_SENIORITY_INPUT)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            JobUnderstanding.model_validate({**VALID_JU_INPUT, "salary": "$200k"})

    def test_empty_business_problems_rejected(self):
        with pytest.raises(ValidationError):
            JobUnderstanding.model_validate({**VALID_JU_INPUT, "business_problems": []})

    def test_preferred_skills_default_empty(self):
        data = {k: v for k, v in VALID_JU_INPUT.items() if k != "preferred_skills"}
        ju = JobUnderstanding.model_validate(data)
        assert ju.preferred_skills == []

    def test_culture_default_empty(self):
        data = {k: v for k, v in VALID_JU_INPUT.items() if k != "culture"}
        ju = JobUnderstanding.model_validate(data)
        assert ju.culture == []

    def test_primary_business_problems_property(self):
        ju = JobUnderstanding.model_validate(VALID_JU_INPUT)
        assert all(bp.priority == "primary" for bp in ju.primary_business_problems)

    def test_all_skill_names_property(self):
        ju = JobUnderstanding.model_validate(VALID_JU_INPUT)
        names = ju.all_skill_names
        assert "Python" in names and "Kafka" in names

    def test_round_trip_json(self):
        ju = JobUnderstanding.model_validate(VALID_JU_INPUT)
        restored = JobUnderstanding.model_validate(ju.model_dump(mode="json"))
        assert restored.domain == ju.domain and restored.seniority == ju.seniority

    def test_json_schema_generatable(self):
        schema = JobUnderstanding.model_json_schema()
        assert schema["type"] == "object"
        assert "must_have_skills" in schema["properties"]
