"""Stored jobs -> analysis -> scored shortlist -> email previews or Gmail drafts.

No scraping, contact guessing, authentication, or sending happens in this module.
External adapters are injected. Preview mode never calls the draft writer.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import String, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis, RankedEmailResult
from agents.job_analyzer.schemas import JobUnderstandingResponse
from agents.job_fetcher.storage import JobRepository
from agents.recruiter_simulator.schemas import CandidateProfile as ScoringProfile, JobRequirements, RecruiterAssessment
from agents.recruiter_simulator.scoring import assess
from database.draft_models import DraftRequest


class Recipient(BaseModel):
    """A supplied, reviewed contact for one exact job dedup_key, not a guess."""
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    name: str | None = None
    role: str | None = None


class Analyzer(Protocol):
    def analyze(self, job_description: str) -> JobUnderstandingResponse: ...


class Generator(Protocol):
    def generate(self, candidate: CandidateProfile, job: JobAnalysis,
                 company: CompanyInfo, personality_prompt: str) -> RankedEmailResult: ...


class Base(DeclarativeBase):
    pass


class DraftAttempt(Base):
    """Reserve before calling Gmail. Uncertain attempts require manual reconciliation."""
    __tablename__ = "pipeline_draft_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_key: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    gmail_draft_id: Mapped[str | None] = mapped_column(String(128))
    request_json: Mapped[str] = mapped_column(Text, nullable=False)


async def init_pipeline_db(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@dataclass(frozen=True)
class PipelineOptions:
    min_fit: float = 0.6
    max_selected: int = 5
    job_limit: int = 100
    create_drafts: bool = False

    def __post_init__(self):
        if not 0 <= self.min_fit <= 1:
            raise ValueError("min_fit must be between 0 and 1")
        if self.max_selected < 1 or self.job_limit < 1:
            raise ValueError("max_selected and job_limit must be positive")


@dataclass
class JobOutcome:
    job_key: str
    company: str
    title: str
    status: str
    assessment: RecruiterAssessment | None = None
    emails: RankedEmailResult | None = None
    request: DraftRequest | None = None
    gmail_draft_id: str | None = None
    error: str | None = None


@dataclass
class PipelineReport:
    jobs: list[JobOutcome] = field(default_factory=list)

    def to_dict(self) -> dict:
        # Only intentional report fields, not raw exceptions, secrets, or input profiles.
        return {"jobs": [{
            "job_key": j.job_key, "company": j.company, "title": j.title,
            "status": j.status, "error": j.error,
            "assessment": j.assessment.model_dump(mode="json") if j.assessment else None,
            "emails": j.emails.model_dump(mode="json") if j.emails else None,
            "request": j.request.model_dump(mode="json") if j.request else None,
            "gmail_draft_id": j.gmail_draft_id,
        } for j in self.jobs]}


DraftWriter = Callable[[DraftRequest], Awaitable[str]]


class Orchestrator:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], analyzer: Analyzer,
                 generator: Generator, draft_writer: DraftWriter | None = None):
        self.sessions = sessions
        self.analyzer = analyzer
        self.generator = generator
        self.draft_writer = draft_writer

    async def run(self, candidate: CandidateProfile, personality: str,
                  recipients: Mapping[str, Recipient], options: PipelineOptions | None = None) -> PipelineReport:
        options = options or PipelineOptions()
        if options.create_drafts and self.draft_writer is None:
            raise ValueError("create_drafts requires an explicit draft writer")
        # Validate the entire recipient map before any model or Gmail call.
        recipients = {key: Recipient.model_validate(value) for key, value in recipients.items()}
        scoring_candidate = ScoringProfile.model_validate(candidate.model_dump(mode="json"))
        async with self.sessions() as session:
            jobs = await JobRepository(session).list_normalized(options.job_limit)
        report = PipelineReport()
        eligible = []
        for job in jobs:
            outcome = JobOutcome(job.dedup_key, job.company, job.title, "pending")
            report.jobs.append(outcome)
            # Missing contacts must not consume shortlist slots or generation calls.
            if job.dedup_key not in recipients:
                outcome.status = "missing_recipient"
                continue
            try:
                understanding = self.analyzer.analyze(job.description).result
                if not understanding.must_have_skills and not understanding.preferred_skills:
                    outcome.status = "insufficient_requirements"
                    continue
                payload = understanding.model_dump(mode="json")
                outcome.assessment = assess(scoring_candidate, JobRequirements.model_validate(payload))
                if outcome.assessment.fit_score < options.min_fit:
                    outcome.status = "below_threshold"
                else:
                    outcome.status = "not_selected"
                    eligible.append((job, outcome, payload))
            except Exception as exc:
                outcome.status = "analysis_failed"
                outcome.error = type(exc).__name__
        eligible.sort(key=lambda item: (-item[1].assessment.fit_score, item[0].dedup_key))
        for job, outcome, payload in eligible[:options.max_selected]:
            recipient = recipients[job.dedup_key]
            key = self._draft_key(candidate, job.dedup_key, str(recipient.email))
            if options.create_drafts:
                async with self.sessions() as session:
                    prior = await session.get(DraftAttempt, key)
                    if prior:
                        outcome.status = "already_drafted" if prior.status == "created" else "needs_reconciliation"
                        outcome.gmail_draft_id = prior.gmail_draft_id
                        continue
            try:
                emails = self.generator.generate(
                    candidate, JobAnalysis.model_validate(payload),
                    CompanyInfo(name=job.company, role_title=job.title,
                                recipient_name=recipient.name, recipient_role=recipient.role), personality)
                # The selected variant must really be one of the generated variants.
                if emails.best_variant not in emails.variants:
                    raise ValueError("Best variant is not in generated variants")
                outcome.emails = emails
                best = emails.best_variant
                outcome.request = DraftRequest(
                    to=recipient.email, subject=best.subject, body=best.body,
                    candidate_name=candidate.full_name, company_name=job.company,
                    variant_type=best.variant_type.value,
                    expected_reply_rate=emails.best_expected_reply_rate)
            except Exception as exc:
                outcome.status = "generation_failed"
                outcome.error = type(exc).__name__
                continue
            if not options.create_drafts:
                outcome.status = "preview"
                continue
            # A committed reservation prevents duplicate drafts across runs/workers.
            if not await self._reserve(key, job.dedup_key, outcome.request):
                outcome.status = "needs_reconciliation"
                continue
            try:
                draft_id = await self.draft_writer(outcome.request)
                if not isinstance(draft_id, str) or not draft_id.strip():
                    raise ValueError("Draft writer returned no Gmail draft ID")
                outcome.gmail_draft_id = draft_id
                async with self.sessions.begin() as session:
                    attempt = await session.get(DraftAttempt, key)
                    attempt.status = "created"
                    attempt.gmail_draft_id = draft_id
                outcome.status = "draft_created"
            except Exception as exc:
                # Gmail may have succeeded before metadata/connection failed. Never retry blindly.
                outcome.status = "needs_reconciliation"
                outcome.error = type(exc).__name__
        return report

    @staticmethod
    def _draft_key(candidate: CandidateProfile, job_key: str, recipient: str) -> str:
        # Stable identity, deliberately independent of generated body/profile changes.
        identity = [candidate.full_name.strip().casefold(), job_key, recipient]
        return hashlib.sha256(json.dumps(identity).encode()).hexdigest()

    async def _reserve(self, key: str, job_key: str, request: DraftRequest) -> bool:
        try:
            async with self.sessions.begin() as session:
                session.add(DraftAttempt(key=key, job_key=job_key, recipient=str(request.to),
                                         status="attempted", request_json=request.model_dump_json()))
            return True
        except IntegrityError:
            return False
