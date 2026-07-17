"""Unit tests for recruiter_simulator matching utilities."""
from __future__ import annotations
import pytest
from agents.recruiter_simulator.matching import (
    compute_skill_coverage, normalize_skill, seniority_alignment,
    seniority_gap, seniority_rank, skill_matches,
)
from agents.recruiter_simulator.schemas import CandidateProfile, JobRequirements
from tests.recruiter_simulator.fixtures import CANDIDATE, JOB_PARTIAL_MATCH, JOB_STRONG_MATCH


class TestNormalizeSkill:
    def test_lowercase(self):           assert normalize_skill("Python") == "python"
    def test_strips_version(self):      assert normalize_skill("Next.js 15") == "next.js"
    def test_alias_js(self):            assert normalize_skill("JS") == "javascript"
    def test_alias_postgres(self):      assert normalize_skill("Postgres") == "postgresql"
    def test_alias_k8s(self):           assert normalize_skill("k8s") == "kubernetes"
    def test_strips_whitespace(self):   assert normalize_skill("  Python  ") == "python"
    def test_passthrough(self):         assert normalize_skill("FastAPI") == "fastapi"


class TestSkillMatches:
    def test_exact(self):               assert skill_matches("Python", "Python") is True
    def test_case_insensitive(self):    assert skill_matches("python", "PYTHON") is True
    def test_version_stripped(self):    assert skill_matches("Next.js 15", "Next.js") is True
    def test_alias(self):               assert skill_matches("JS", "JavaScript") is True
    def test_substring(self):           assert skill_matches("AWS EC2", "AWS") is True
    def test_no_match(self):            assert skill_matches("Python", "Rust") is False
    def test_short_no_false_positive(self): assert skill_matches("Go", "Django") is False


class TestComputeSkillCoverage:
    def test_full_coverage(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        job       = JobRequirements.model_validate(JOB_STRONG_MATCH)
        coverage  = compute_skill_coverage(candidate, job)
        assert coverage.must_have_matched == 3 and coverage.missing_must_haves == []

    def test_preferred_coverage(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        job       = JobRequirements.model_validate(JOB_STRONG_MATCH)
        coverage  = compute_skill_coverage(candidate, job)
        assert coverage.preferred_matched == 2

    def test_partial_identifies_missing(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        job       = JobRequirements.model_validate(JOB_PARTIAL_MATCH)
        coverage  = compute_skill_coverage(candidate, job)
        assert "Django" in coverage.missing_must_haves
        assert "GraphQL" in coverage.missing_must_haves
        assert coverage.must_have_matched == 2

    def test_checks_project_tech_stack(self):
        candidate = CandidateProfile.model_validate({
            "full_name": "Test", "skills": [],
            "projects": [{"name": "P", "description": "d", "tech_stack": ["Kubernetes"], "metrics": [], "highlights": []}],
            "experience": [],
        })
        job = JobRequirements.model_validate({
            "must_have_skills": [{"name": "Kubernetes", "category": "devops"}], "preferred_skills": [],
        })
        assert compute_skill_coverage(candidate, job).must_have_matched == 1

    def test_checks_experience_tech_used(self):
        candidate = CandidateProfile.model_validate({
            "full_name": "Test", "skills": [], "projects": [],
            "experience": [{"title": "E", "company": "X", "period": "2024", "bullets": [], "tech_used": ["Terraform"]}],
        })
        job = JobRequirements.model_validate({
            "must_have_skills": [{"name": "Terraform", "category": "devops"}], "preferred_skills": [],
        })
        assert compute_skill_coverage(candidate, job).must_have_matched == 1


class TestSeniorityHelpers:
    def test_rank_known(self):     assert seniority_rank("junior") == 1
    def test_rank_unknown(self):   assert seniority_rank("unknown") is None
    def test_gap_1yr(self):        assert seniority_gap(1.0) == "junior"
    def test_gap_3yr(self):        assert seniority_gap(3.0) == "mid"
    def test_gap_6yr(self):        assert seniority_gap(6.0) == "senior"

    def test_alignment_match(self):
        gap, msg = seniority_alignment(3.0, "mid")
        assert gap == 0 and "matches" in msg

    def test_alignment_under(self):
        gap, msg = seniority_alignment(1.0, "senior")
        assert gap == 2 and "below" in msg

    def test_alignment_over(self):
        gap, msg = seniority_alignment(6.0, "junior")
        assert gap == -2 and "above" in msg

    def test_alignment_unknown(self):
        gap, msg = seniority_alignment(2.0, "unknown")
        assert gap == 0
