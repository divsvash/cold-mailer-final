"""Unit tests for the fact_sheet builder."""
from __future__ import annotations
import pytest
from agents.email_generator.fact_sheet import (
    build_candidate_section,
    build_company_section,
    build_fact_sheet,
    build_job_section,
)
from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis
from tests.email_generator.fixtures import (
    CANDIDATE, COMPANY_MINIMAL_INFO, COMPANY_WITH_FULL_INFO, JOB_ANALYSIS,
)


class TestBuildCandidateSection:
    def test_includes_name(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        lines = build_candidate_section(c)
        assert any("Divyansh Sharma" in l for l in lines)

    def test_includes_skills(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        lines = build_candidate_section(c)
        text = "\n".join(lines)
        assert "Python" in text and "FastAPI" in text

    def test_includes_skill_level(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        text = "\n".join(build_candidate_section(c))
        assert "advanced" in text

    def test_includes_skill_years(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        text = "\n".join(build_candidate_section(c))
        assert "2.0 yr" in text

    def test_includes_project_metrics(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        text = "\n".join(build_candidate_section(c))
        assert "3x higher callback rate" in text

    def test_includes_experience_bullets(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        text = "\n".join(build_candidate_section(c))
        assert "10K+" in text

    def test_includes_tech_stack(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        text = "\n".join(build_candidate_section(c))
        assert "pgvector" in text


class TestBuildJobSection:
    def test_includes_must_have_skills(self):
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        text = "\n".join(build_job_section(j))
        assert "Python" in text and "FastAPI" in text

    def test_includes_preferred_skills(self):
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        text = "\n".join(build_job_section(j))
        assert "pgvector" in text

    def test_includes_domain(self):
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        text = "\n".join(build_job_section(j))
        assert "ai_ml" in text

    def test_includes_business_problem(self):
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        text = "\n".join(build_job_section(j))
        assert "LLM-integrated" in text

    def test_empty_job_returns_empty_list(self):
        j = JobAnalysis.model_validate({"seniority": "unknown", "domain": "unknown"})
        lines = build_job_section(j)
        assert lines == []


class TestBuildCompanySection:
    def test_includes_name(self):
        c = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        text = "\n".join(build_company_section(c))
        assert "Vectorly" in text

    def test_includes_one_liner(self):
        c = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        text = "\n".join(build_company_section(c))
        assert "embedding-based developer search" in text

    def test_includes_recent_news(self):
        c = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        text = "\n".join(build_company_section(c))
        assert "open-source code search API" in text

    def test_includes_recipient_name(self):
        c = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        text = "\n".join(build_company_section(c))
        assert "Alex" in text

    def test_minimal_company_no_absent_fields(self):
        c = CompanyInfo.model_validate(COMPANY_MINIMAL_INFO)
        text = "\n".join(build_company_section(c))
        assert "RECENT NEWS" not in text
        assert "RECIPIENT NAME" not in text
        assert "Vectorly" in text


class TestBuildFactSheet:
    def test_combines_all_sections(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        company = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        sheet = build_fact_sheet(c, j, company)

        assert "Divyansh Sharma" in sheet
        assert "Python" in sheet
        assert "Vectorly" in sheet
        assert "Alex" in sheet
        assert "LLM-integrated" in sheet

    def test_fact_sheet_is_string(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        company = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        sheet = build_fact_sheet(c, j, company)
        assert isinstance(sheet, str)
        assert len(sheet) > 100

    def test_fact_sheet_contains_metrics(self):
        c = CandidateProfile.model_validate(CANDIDATE)
        j = JobAnalysis.model_validate(JOB_ANALYSIS)
        company = CompanyInfo.model_validate(COMPANY_WITH_FULL_INFO)
        sheet = build_fact_sheet(c, j, company)
        assert "<100ms" in sheet
        assert "3x higher" in sheet
