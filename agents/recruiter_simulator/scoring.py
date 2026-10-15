"""Deterministic scoring engine — fit_score, callback/interview probability, strengths/concerns."""
from __future__ import annotations
from agents.recruiter_simulator.matching import compute_skill_coverage, seniority_alignment
from agents.recruiter_simulator.schemas import (
    CandidateProfile, Concern, JobRequirements,
    RecruiterAssessment, SkillCoverage, Strength,
)

MUST_HAVE_WEIGHT           = 0.70
PREFERRED_WEIGHT           = 0.30
ZERO_MUST_HAVE_CAP         = 0.30
UNDERLEVEL_PENALTY_PER_RANK = 0.20
OVERLEVEL_PENALTY_PER_RANK  = 0.10
INTERVIEW_MUST_HAVE_DISCOUNT = 0.5


def compute_fit_score(coverage: SkillCoverage) -> float:
    if coverage.must_have_total == 0 and coverage.preferred_total == 0:
        return 0.0
    score = MUST_HAVE_WEIGHT * coverage.must_have_ratio + PREFERRED_WEIGHT * coverage.preferred_ratio
    if coverage.must_have_total > 0 and coverage.must_have_matched == 0:
        score = min(score, ZERO_MUST_HAVE_CAP)
    return round(max(0.0, min(1.0, score)), 4)


def compute_callback_probability(
    fit_score: float, candidate: CandidateProfile, job: JobRequirements
) -> tuple[float, str]:
    gap, explanation = seniority_alignment(candidate.total_experience_years(), job.seniority)
    prob = fit_score
    if gap > 0:
        prob *= max(0.0, 1 - UNDERLEVEL_PENALTY_PER_RANK * gap)
    elif gap < 0:
        prob *= max(0.0, 1 - OVERLEVEL_PENALTY_PER_RANK * abs(gap))
    return round(max(0.0, min(1.0, prob)), 4), explanation


def compute_interview_probability(callback_probability: float, coverage: SkillCoverage) -> float:
    discount = INTERVIEW_MUST_HAVE_DISCOUNT * (1 - coverage.must_have_ratio)
    return round(max(0.0, min(1.0, callback_probability * (1 - discount))), 4)


def derive_strengths(
    candidate: CandidateProfile, job: JobRequirements, coverage: SkillCoverage
) -> list[Strength]:
    strengths: list[Strength] = []
    if coverage.must_have_total > 0 and coverage.must_have_ratio >= 0.8:
        strengths.append(Strength(
            title="Strong match on required skills",
            detail=f"Candidate matches {coverage.must_have_matched} of {coverage.must_have_total} "
                   f"must-have skills: {', '.join(coverage.matched_must_haves)}.",
        ))
    if coverage.preferred_total > 0 and coverage.preferred_matched > 0:
        strengths.append(Strength(
            title="Covers preferred/bonus skills",
            detail=f"Candidate also matches {coverage.preferred_matched} of "
                   f"{coverage.preferred_total} preferred skills: {', '.join(coverage.matched_preferred)}.",
        ))
    if any(p.metrics for p in candidate.projects):
        names = ", ".join([p.name for p in candidate.projects if p.metrics][:3])
        strengths.append(Strength(
            title="Track record of quantified impact",
            detail=f"Projects with measured outcomes: {names}.",
        ))
    gap, _ = seniority_alignment(candidate.total_experience_years(), job.seniority)
    if gap == -1:
        strengths.append(Strength(
            title="Slightly senior relative to role",
            detail="Candidate's experience level appears one rank above the stated requirement.",
        ))
    return strengths


def derive_concerns(
    candidate: CandidateProfile, job: JobRequirements, coverage: SkillCoverage
) -> list[Concern]:
    concerns: list[Concern] = []
    if coverage.must_have_total == 0 and coverage.preferred_total == 0:
        concerns.append(Concern(title="Insufficient job requirements",
                                detail="No skills were supplied; a meaningful fit score cannot be computed.",
                                severity="high"))
    if coverage.missing_must_haves:
        severity = "high" if coverage.must_have_ratio < 0.5 else "medium"
        concerns.append(Concern(
            title="Missing required skills",
            detail=f"Candidate has no evidence of: {', '.join(coverage.missing_must_haves)}.",
            severity=severity,
        ))
    if coverage.missing_preferred and coverage.preferred_total > 0:
        concerns.append(Concern(
            title="Missing some preferred skills",
            detail=f"Candidate has no evidence of: {', '.join(coverage.missing_preferred)}.",
            severity="low",
        ))
    gap, explanation = seniority_alignment(candidate.total_experience_years(), job.seniority)
    if gap >= 2:
        concerns.append(Concern(title="Significant seniority gap", detail=explanation, severity="high"))
    elif gap == 1:
        concerns.append(Concern(title="Possible seniority gap", detail=explanation, severity="medium"))
    if not any(p.metrics for p in candidate.projects):
        concerns.append(Concern(
            title="No quantified project outcomes",
            detail="None of the candidate's projects list measurable metrics or impact.",
            severity="low",
        ))
    return concerns


def assess(candidate: CandidateProfile, job: JobRequirements) -> RecruiterAssessment:
    coverage              = compute_skill_coverage(candidate, job)
    fit_score             = compute_fit_score(coverage)
    callback_probability, _ = compute_callback_probability(fit_score, candidate, job)
    interview_probability = compute_interview_probability(callback_probability, coverage)
    return RecruiterAssessment(
        fit_score=fit_score,
        callback_probability=callback_probability,
        interview_probability=interview_probability,
        strengths=derive_strengths(candidate, job, coverage),
        concerns=derive_concerns(candidate, job, coverage),
        skill_coverage=coverage,
        candidate_name=candidate.full_name,
        job_seniority=job.seniority,
        job_domain=job.domain,
    )
