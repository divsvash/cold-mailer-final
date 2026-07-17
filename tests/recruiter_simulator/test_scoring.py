"""Unit tests for recruiter_simulator scoring engine."""
from __future__ import annotations
import pytest
from agents.recruiter_simulator.matching import compute_skill_coverage
from agents.recruiter_simulator.schemas import (
    CandidateProfile, JobRequirements, SkillCoverage,
)
from agents.recruiter_simulator.scoring import (
    ZERO_MUST_HAVE_CAP, assess, compute_callback_probability,
    compute_fit_score, compute_interview_probability,
)
from tests.recruiter_simulator.fixtures import (
    CANDIDATE, JOB_EMPTY, JOB_OVERLEVELED, JOB_PARTIAL_MATCH,
    JOB_POOR_MATCH, JOB_STAFF_LEVEL, JOB_STRONG_MATCH,
)


class TestComputeFitScore:
    def test_perfect(self):
        c = SkillCoverage(must_have_total=3, must_have_matched=3, preferred_total=2, preferred_matched=2)
        assert compute_fit_score(c) == 1.0

    def test_zero(self):
        c = SkillCoverage(must_have_total=3, must_have_matched=0, preferred_total=2, preferred_matched=0)
        assert compute_fit_score(c) == 0.0

    def test_must_have_only(self):
        c = SkillCoverage(must_have_total=2, must_have_matched=2, preferred_total=2, preferred_matched=0)
        assert compute_fit_score(c) == 0.7

    def test_zero_must_have_capped(self):
        c = SkillCoverage(must_have_total=2, must_have_matched=0, preferred_total=2, preferred_matched=2)
        assert compute_fit_score(c) == ZERO_MUST_HAVE_CAP

    def test_no_requirements_gives_full(self):
        c = SkillCoverage(must_have_total=0, must_have_matched=0, preferred_total=2, preferred_matched=1)
        assert compute_fit_score(c) == 0.85


class TestComputeCallbackProbability:
    def test_matching_seniority_no_penalty(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)  # 2.0 yrs -> mid
        job = JobRequirements.model_validate({"seniority": "mid"})
        prob, _ = compute_callback_probability(0.8, candidate, job)
        assert prob == 0.8

    def test_underleveled_penalised(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        job = JobRequirements.model_validate({"seniority": "staff"})
        prob, _ = compute_callback_probability(0.8, candidate, job)
        assert prob < 0.8

    def test_overleveled_less_penalised(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        job_under = JobRequirements.model_validate({"seniority": "staff"})
        job_over  = JobRequirements.model_validate({"seniority": "intern"})
        prob_under, _ = compute_callback_probability(0.8, candidate, job_under)
        prob_over,  _ = compute_callback_probability(0.8, candidate, job_over)
        assert prob_over > prob_under  # over-leveled is less penalised

    def test_bounded(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        job = JobRequirements.model_validate({"seniority": "executive"})
        prob, _ = compute_callback_probability(0.9, candidate, job)
        assert 0.0 <= prob <= 1.0


class TestComputeInterviewProbability:
    def test_full_coverage_no_discount(self):
        c = SkillCoverage(must_have_total=3, must_have_matched=3, preferred_total=0, preferred_matched=0)
        assert compute_interview_probability(0.7, c) == 0.7

    def test_partial_coverage_discounts(self):
        c = SkillCoverage(must_have_total=4, must_have_matched=2, preferred_total=0, preferred_matched=0)
        assert compute_interview_probability(0.8, c) == 0.6

    def test_never_exceeds_callback(self):
        c = SkillCoverage(must_have_total=2, must_have_matched=1, preferred_total=0, preferred_matched=0)
        assert compute_interview_probability(0.5, c) <= 0.5


class TestAssessEndToEnd:
    def test_strong_match_high_scores(self):
        result = assess(CandidateProfile.model_validate(CANDIDATE), JobRequirements.model_validate(JOB_STRONG_MATCH))
        assert result.fit_score >= 0.9
        assert result.callback_probability >= 0.8
        assert result.interview_probability >= 0.8

    def test_poor_match_low_scores(self):
        result = assess(CandidateProfile.model_validate(CANDIDATE), JobRequirements.model_validate(JOB_POOR_MATCH))
        assert result.fit_score <= ZERO_MUST_HAVE_CAP
        assert result.callback_probability < 0.3

    def test_poor_match_has_high_concern(self):
        result = assess(CandidateProfile.model_validate(CANDIDATE), JobRequirements.model_validate(JOB_POOR_MATCH))
        assert any(c.severity == "high" for c in result.concerns)

    def test_strong_match_has_skill_strength(self):
        result = assess(CandidateProfile.model_validate(CANDIDATE), JobRequirements.model_validate(JOB_STRONG_MATCH))
        assert any("required skills" in s.title for s in result.strengths)

    def test_invariant_interview_lte_callback(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        for job_data in [JOB_STRONG_MATCH, JOB_PARTIAL_MATCH, JOB_POOR_MATCH, JOB_STAFF_LEVEL]:
            r = assess(candidate, JobRequirements.model_validate(job_data))
            assert r.interview_probability <= r.callback_probability + 1e-9

    def test_invariant_all_bounded(self):
        candidate = CandidateProfile.model_validate(CANDIDATE)
        for job_data in [JOB_STRONG_MATCH, JOB_PARTIAL_MATCH, JOB_POOR_MATCH, JOB_OVERLEVELED, JOB_EMPTY]:
            r = assess(candidate, JobRequirements.model_validate(job_data))
            assert 0.0 <= r.fit_score <= 1.0
            assert 0.0 <= r.callback_probability <= 1.0
            assert 0.0 <= r.interview_probability <= 1.0

    def test_result_json_serializable(self):
        result = assess(CandidateProfile.model_validate(CANDIDATE), JobRequirements.model_validate(JOB_STRONG_MATCH))
        dumped = result.model_dump(mode="json")
        assert "fit_score" in dumped and "callback_probability" in dumped
