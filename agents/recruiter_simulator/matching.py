"""Deterministic skill matching and seniority comparison utilities."""
from __future__ import annotations
import re
from agents.recruiter_simulator.schemas import CandidateProfile, JobRequirements, SkillCoverage

SKILL_ALIASES: dict[str, str] = {
    "js": "javascript", "ts": "typescript", "postgres": "postgresql",
    "psql": "postgresql", "k8s": "kubernetes", "gh actions": "github actions",
    "py": "python", "node": "node.js", "nodejs": "node.js",
    "next": "next.js", "nextjs": "next.js", "reactjs": "react", "tailwind": "tailwind css",
}

SENIORITY_ORDER: list[str] = [
    "intern", "junior", "mid", "senior", "staff",
    "principal", "lead", "manager", "director", "executive",
]


def normalize_skill(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"\s+\d+(\.\d+)*$", "", n)
    return SKILL_ALIASES.get(n, n)


def skill_matches(candidate_skill: str, job_skill: str) -> bool:
    c = normalize_skill(candidate_skill)
    j = normalize_skill(job_skill)
    if c == j:
        return True
    if len(c) >= 3 and len(j) >= 3:
        if c in j or j in c:
            return True
    return False


def compute_skill_coverage(candidate: CandidateProfile, job: JobRequirements) -> SkillCoverage:
    candidate_terms: set[str] = set()
    for skill in candidate.skills:
        candidate_terms.add(skill.name)
    for project in candidate.projects:
        candidate_terms.update(project.tech_stack)
    for exp in candidate.experience:
        candidate_terms.update(exp.tech_used)

    matched_must, missing_must = [], []
    for js in job.must_have_skills:
        if any(skill_matches(ct, js.name) for ct in candidate_terms):
            matched_must.append(js.name)
        else:
            missing_must.append(js.name)

    matched_pref, missing_pref = [], []
    for js in job.preferred_skills:
        if any(skill_matches(ct, js.name) for ct in candidate_terms):
            matched_pref.append(js.name)
        else:
            missing_pref.append(js.name)

    return SkillCoverage(
        must_have_total=len(job.must_have_skills), must_have_matched=len(matched_must),
        preferred_total=len(job.preferred_skills), preferred_matched=len(matched_pref),
        missing_must_haves=missing_must, missing_preferred=missing_pref,
        matched_must_haves=matched_must, matched_preferred=matched_pref,
    )


def seniority_rank(level: str) -> int | None:
    level = level.lower()
    return SENIORITY_ORDER.index(level) if level in SENIORITY_ORDER else None


def seniority_gap(candidate_years: float) -> str:
    if candidate_years >= 8:   return "staff"
    if candidate_years >= 5:   return "senior"
    if candidate_years >= 2:   return "mid"
    if candidate_years >= 0.5: return "junior"
    return "intern"


def seniority_alignment(candidate_years: float, job_seniority: str) -> tuple[int, str]:
    job_rank = seniority_rank(job_seniority)
    if job_rank is None:
        return 0, "Job seniority not specified"
    candidate_level = seniority_gap(candidate_years)
    candidate_rank  = seniority_rank(candidate_level)
    if candidate_rank is None:
        return 0, "Could not infer candidate seniority"
    gap = job_rank - candidate_rank
    if gap == 0:
        return 0, f"Candidate level ({candidate_level}) matches job requirement ({job_seniority})"
    if gap > 0:
        return gap, f"Candidate appears {gap} level(s) below required '{job_seniority}'"
    return gap, f"Candidate appears {abs(gap)} level(s) above required '{job_seniority}' (may be over-leveled)"
