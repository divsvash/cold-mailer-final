"""End-to-end offline flow: stored jobs -> discovery -> human review -> pipeline.

Exercises the pieces together the way the CLIs chain them: jobs in storage,
recipient discovery proposes quoted contacts, review approves one, the export
feeds the orchestrator, preview and draft-reservation behave. Model and Gmail
adapters are injected fakes; storage and scoring are real. No network.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from agents.email_generator.schemas import (
    CandidateProfile, EmailRanking, EmailVariant, RankedEmailResult,
)
from agents.job_analyzer.schemas import JobUnderstanding, JobUnderstandingResponse
from agents.job_fetcher.models import NormalizedJob
from agents.job_fetcher.storage import JobRepository, init_db, make_engine, make_session_factory
from agents.recipient_discovery.models import ContactStatus
from agents.recipient_discovery.service import RecipientDiscoveryService
from agents.recipient_discovery.storage import ContactRepository, init_contact_db
from orchestrator import DraftAttempt, Orchestrator, PipelineOptions, Recipient, init_pipeline_db


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("No external calls in end-to-end tests")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr("anthropic.Anthropic", denied)
    monkeypatch.setattr("database.gmail_auth.get_gmail_service", denied)


@pytest.fixture
async def store():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    await init_contact_db(engine)
    await init_pipeline_db(engine)
    yield make_session_factory(engine)
    await engine.dispose()


@pytest.fixture
def candidate():
    return CandidateProfile(full_name="Test Candidate", skills=[{
        "name": "Python", "category": "language", "years": 3,
        "evidence": ["Built the sample parser"],
    }])


def adapters():
    analyzer = MagicMock()
    analyzer.analyze.return_value = JobUnderstandingResponse(
        model="offline",
        result=JobUnderstanding(
            must_have_skills=[{"name": "Python", "category": "language"}],
            domain="devtools", seniority="mid",
            business_problems=[{"description": "Build reliable developer tools",
                                "priority": "primary"}]))
    variants = [EmailVariant(variant_type=kind, subject="Developer tools role",
                            body="I built a sample parser. Could we talk?", word_count=9)
                for kind in ("technical", "founder", "concise")]
    generator = MagicMock()
    generator.generate.return_value = RankedEmailResult(
        variants=variants,
        rankings=[EmailRanking(variant_type=v.variant_type,
                               expected_reply_rate=0.2 + i / 10,
                               reasoning="Offline fixture, not a forecast")
                  for i, v in enumerate(variants)],
        best_variant=variants[2])
    return analyzer, generator


async def seed(store):
    jobs = [
        NormalizedJob(title="Backend Engineer", company="Acme",
                      description="Use Python. Questions: priya@acme.com",
                      url="https://acme.test/jobs/1", source="lever", source_id="1"),
        NormalizedJob(title="Platform Engineer", company="Beta",
                      description="Use Python. No address anywhere here.",
                      url="https://beta.test/jobs/2", source="lever", source_id="2"),
        NormalizedJob(title="Tools Engineer", company="Gamma",
                      description="Use Python. Mail team@gamma.io",
                      url="https://gamma.test/jobs/3", source="lever", source_id="3"),
    ]
    async with store.begin() as session:
        for job in jobs:
            await JobRepository(session).upsert_normalized(job)
    return jobs


async def test_full_flow_respects_the_review_gate(store, candidate):
    jobs = await seed(store)
    by_company = {job.company: job for job in jobs}

    # Discovery proposes; nothing is usable yet.
    async with store() as session:
        report = await RecipientDiscoveryService(
            ContactRepository(session), JobRepository(session)).scan()
    proposals = {c.job_dedup_key: str(c.email) for r in report.results for c in r.candidates}
    assert proposals == {
        by_company["Acme"].dedup_key: "priya@acme.com",
        by_company["Gamma"].dedup_key: "team@gamma.io",
    }
    async with store() as session:
        assert await ContactRepository(session).approved_map() == {}

    # Human approves exactly one contact; the export is what the pipeline sees.
    async with store.begin() as session:
        repo = ContactRepository(session)
        assert await repo.set_status(by_company["Acme"].dedup_key, "priya@acme.com",
                                     ContactStatus.APPROVED)
    async with store() as session:
        recipients = await ContactRepository(session).approved_map()
    assert list(recipients) == [by_company["Acme"].dedup_key]

    # Pipeline: approved job previews with the reviewed recipient; unreviewed
    # jobs are reported, never emailed, and consume no model calls.
    analyzer, generator = adapters()
    writer = AsyncMock()
    result = await Orchestrator(store, analyzer, generator, writer).run(
        candidate, "plain", recipients)
    outcomes = {o.company: o for o in result.jobs}
    assert outcomes["Acme"].status == "preview"
    assert outcomes["Acme"].request.to == "priya@acme.com"
    assert outcomes["Acme"].emails is not None
    assert outcomes["Beta"].status == "missing_recipient"
    assert outcomes["Gamma"].status == "missing_recipient"
    analyzer.analyze.assert_called_once()
    generator.generate.assert_called_once()
    writer.assert_not_awaited()


async def test_full_flow_draft_opt_in_and_rerun_guard(store, candidate):
    jobs = await seed(store)
    acme = next(j for j in jobs if j.company == "Acme")
    async with store() as session:
        repo = ContactRepository(session)
        service = RecipientDiscoveryService(repo, JobRepository(session))
        await service.scan()
    async with store.begin() as session:
        await ContactRepository(session).set_status(
            acme.dedup_key, "priya@acme.com", ContactStatus.APPROVED)
    async with store() as session:
        recipients = await ContactRepository(session).approved_map()

    analyzer, generator = adapters()
    writer = AsyncMock(return_value="draft-e2e-1")
    pipeline = Orchestrator(store, analyzer, generator, writer)
    first = await pipeline.run(candidate, "plain", recipients,
                               PipelineOptions(create_drafts=True))
    acme_outcome = next(o for o in first.jobs if o.company == "Acme")
    assert acme_outcome.status == "draft_created"
    assert acme_outcome.gmail_draft_id == "draft-e2e-1"
    assert writer.await_count == 1

    # A repeat run must not create a duplicate draft for the same identity.
    second = await pipeline.run(candidate, "plain", recipients,
                                PipelineOptions(create_drafts=True))
    assert next(o for o in second.jobs if o.company == "Acme").status == "already_drafted"
    assert writer.await_count == 1
    async with store() as session:
        attempts = (await session.execute(select(DraftAttempt))).scalars().all()
        assert len(attempts) == 1 and attempts[0].status == "created"


async def test_export_file_round_trips_into_pipeline_validation(store, candidate, tmp_path):
    import json
    from security import private_write
    jobs = await seed(store)
    acme = next(j for j in jobs if j.company == "Acme")
    async with store() as session:
        repo = ContactRepository(session)
        await RecipientDiscoveryService(repo, JobRepository(session)).scan()
    async with store.begin() as session:
        await ContactRepository(session).set_status(
            acme.dedup_key, "priya@acme.com", ContactStatus.APPROVED)
    async with store() as session:
        mapping = await ContactRepository(session).approved_map()
    path = tmp_path / "recipients.json"
    private_write(path, json.dumps(mapping))
    loaded = json.loads(path.read_text())
    # Exactly what run_pipeline.py does with --recipients.
    recipients = {key: Recipient.model_validate(value) for key, value in loaded.items()}
    analyzer, generator = adapters()
    result = await Orchestrator(store, analyzer, generator, AsyncMock()).run(
        candidate, "plain", recipients)
    assert next(o for o in result.jobs if o.company == "Acme").status == "preview"
