"""Fact sheet builder — the anti-hallucination grounding source."""
from __future__ import annotations
from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis


def build_candidate_section(candidate: CandidateProfile) -> list[str]:
    lines = [f"CANDIDATE NAME: {candidate.full_name}"]
    if candidate.headline: lines.append(f"HEADLINE: {candidate.headline}")
    if candidate.summary:  lines.append(f"SUMMARY: {candidate.summary}")
    for skill in candidate.skills:
        detail = f"SKILL: {skill.name} ({skill.level}"
        if skill.years is not None: detail += f", {skill.years} yr"
        lines.append(detail + ")")
    for project in candidate.projects:
        lines.append(f"PROJECT: {project.name}")
        lines.append(f"  DESCRIPTION: {project.description}")
        if project.tech_stack: lines.append(f"  TECH STACK: {', '.join(project.tech_stack)}")
        for metric in project.metrics: lines.append(f"  METRIC: {metric}")
    for exp in candidate.experience:
        lines.append(f"EXPERIENCE: {exp.title} at {exp.company} ({exp.period})")
        for bullet in exp.bullets: lines.append(f"  - {bullet}")
        if exp.tech_used: lines.append(f"  TECH USED: {', '.join(exp.tech_used)}")
    return lines


def build_job_section(job: JobAnalysis) -> list[str]:
    lines = []
    if job.must_have_skills:
        lines.append(f"JOB MUST-HAVE SKILLS: {', '.join(s.name for s in job.must_have_skills)}")
    if job.preferred_skills:
        lines.append(f"JOB PREFERRED SKILLS: {', '.join(s.name for s in job.preferred_skills)}")
    if job.domain and job.domain != "unknown":   lines.append(f"JOB DOMAIN: {job.domain}")
    if job.seniority and job.seniority != "unknown": lines.append(f"JOB SENIORITY: {job.seniority}")
    for bp in job.business_problems:
        lines.append(f"JOB BUSINESS PROBLEM ({bp.priority}): {bp.description}")
    if job.culture: lines.append(f"JOB CULTURE: {', '.join(job.culture)}")
    return lines


def build_company_section(company: CompanyInfo) -> list[str]:
    lines = [f"COMPANY NAME: {company.name}"]
    if company.one_liner:      lines.append(f"COMPANY DESCRIPTION: {company.one_liner}")
    if company.role_title:     lines.append(f"ROLE TITLE: {company.role_title}")
    if company.recent_news:    lines.append(f"RECENT NEWS: {company.recent_news}")
    if company.recipient_name: lines.append(f"RECIPIENT NAME: {company.recipient_name}")
    if company.recipient_role: lines.append(f"RECIPIENT ROLE: {company.recipient_role}")
    return lines


def build_fact_sheet(candidate: CandidateProfile, job: JobAnalysis, company: CompanyInfo) -> str:
    lines: list[str] = []
    for section in [build_candidate_section(candidate), build_job_section(job), build_company_section(company)]:
        lines.extend(section)
    return "\n".join(lines)
