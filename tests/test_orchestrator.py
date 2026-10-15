"""Offline pipeline tests: real SQLite + scoring + Gmail service, injected model/Gmail."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from agents.email_generator.schemas import CandidateProfile, EmailVariant, RankedEmailResult, EmailRanking
from agents.job_analyzer.schemas import JobUnderstanding, JobUnderstandingResponse
from agents.job_fetcher.models import NormalizedJob
from agents.job_fetcher.storage import JobRepository, init_db, make_engine, make_session_factory
from database.draft_storage import init_db as init_drafts, DraftMetadataRepository
from database.gmail_service import DraftService
from orchestrator import DraftAttempt, Orchestrator, PipelineOptions, Recipient, init_pipeline_db


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("No external calls in pipeline tests")
    monkeypatch.setattr(socket.socket, "connect", denied)
    # Hard-fail even SDK construction/auth, not merely network calls.
    monkeypatch.setattr("anthropic.Anthropic", denied)
    monkeypatch.setattr("database.gmail_auth.get_gmail_service", denied)


@pytest.fixture
async def store():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    await init_drafts(engine)
    await init_pipeline_db(engine)
    sessions = make_session_factory(engine)
    yield sessions
    await engine.dispose()


@pytest.fixture
def candidate():
    return CandidateProfile(full_name="Test Candidate", skills=[{
        "name": "Python", "category": "language", "years": 3,
        "evidence": ["Built the sample parser"],
    }])


def understanding(skill="Python"):
    return JobUnderstandingResponse(model="offline", result=JobUnderstanding(
        must_have_skills=[{"name": skill, "category": "language"}],
        domain="devtools", seniority="mid",
        business_problems=[{"description": "Build reliable developer tools", "priority": "primary"}]))


def generated():
    variants = [EmailVariant(variant_type=kind, subject="Developer tools role",
                            body="I built a sample parser. Could we talk?", word_count=9)
                for kind in ("technical", "founder", "concise")]
    return RankedEmailResult(variants=variants, rankings=[
        EmailRanking(variant_type=v.variant_type, expected_reply_rate=0.2 + i / 10,
                     reasoning="Offline fixture, not a forecast") for i, v in enumerate(variants)],
        best_variant=variants[2])


async def seed(store, count=1):
    jobs = [NormalizedJob(title=f"Engineer {i}", company=f"Example {i}",
                          description=f"Use Python to build developer tooling for team {i}.",
                          url=f"https://example.test/jobs/{i}", source="lever", source_id=str(i))
            for i in range(count)]
    async with store.begin() as session:
        for job in jobs:
            await JobRepository(session).upsert_normalized(job)
    return jobs


def adapters():
    analyzer = MagicMock()
    analyzer.analyze.return_value = understanding()
    generator = MagicMock()
    generator.generate.return_value = generated()
    return analyzer, generator


def contacts(jobs):
    return {job.dedup_key: Recipient(email=f"person{i}@example.com", name=f"Person {i}", role="Hiring")
            for i, job in enumerate(jobs)}


async def test_preview_connects_real_storage_analysis_scoring_generation(store, candidate):
    jobs = await seed(store)
    analyzer, generator = adapters()
    writer = AsyncMock()
    report = await Orchestrator(store, analyzer, generator, writer).run(candidate, "plain", contacts(jobs))
    out = report.jobs[0]
    assert out.status == "preview"
    assert out.assessment.fit_score == 1
    assert out.request.to == "person0@example.com"
    assert out.request.body == generated().best_variant.body
    assert out.request.expected_reply_rate == 0.4
    analyzer.analyze.assert_called_once_with(jobs[0].description)
    args = generator.generate.call_args.args
    assert args[1].domain == "devtools"
    assert args[2].role_title == jobs[0].title
    assert args[2].recipient_name == "Person 0"
    assert args[3] == "plain"
    writer.assert_not_awaited()
    async with store() as session:
        assert not (await session.execute(select(DraftAttempt))).scalars().all()
    assert report.to_dict()["jobs"][0]["emails"]["best_variant"]["variant_type"] == "concise"


async def test_draft_uses_real_service_metadata_and_rerun_is_idempotent(store, candidate):
    jobs = await seed(store)
    analyzer, generator = adapters()
    gmail = MagicMock()
    gmail.create_draft.return_value = ({"id": "draft-offline", "message": {"id": "msg"}}, 1)
    async def writer(request):
        async with store.begin() as session:
            return (await DraftService(gmail, session).create_draft(request)).gmail_draft_id
    pipeline = Orchestrator(store, analyzer, generator, writer)
    report = await pipeline.run(candidate, "plain", contacts(jobs), PipelineOptions(create_drafts=True))
    assert report.jobs[0].status == "draft_created"
    assert report.jobs[0].gmail_draft_id == "draft-offline"
    async with store() as session:
        assert await DraftMetadataRepository(session).count() == 1
    report = await pipeline.run(candidate, "changed voice", contacts(jobs), PipelineOptions(create_drafts=True))
    assert report.jobs[0].status == "already_drafted"
    assert generator.generate.call_count == 1
    assert gmail.create_draft.call_count == 1
    gmail.send.assert_not_called()


async def test_ambiguous_draft_failure_never_auto_retries(store, candidate):
    jobs = await seed(store)
    analyzer, generator = adapters()
    writer = AsyncMock(side_effect=TimeoutError("private upstream text"))
    pipeline = Orchestrator(store, analyzer, generator, writer)
    opts = PipelineOptions(create_drafts=True)
    first = await pipeline.run(candidate, "plain", contacts(jobs), opts)
    second = await pipeline.run(candidate, "plain", contacts(jobs), opts)
    assert first.jobs[0].status == second.jobs[0].status == "needs_reconciliation"
    assert first.jobs[0].error == "TimeoutError"
    assert "private upstream text" not in str(first.to_dict())
    writer.assert_awaited_once()


async def test_rank_selection_missing_recipient_threshold_and_ties(store, candidate):
    jobs = await seed(store, 4)
    analyzer, generator = adapters()
    def analyze(text):
        return understanding("Rust" if "team 1" in text else "Python")
    analyzer.analyze.side_effect = analyze
    recipients = contacts(jobs)
    del recipients[jobs[0].dedup_key]
    report = await Orchestrator(store, analyzer, generator).run(
        candidate, "plain", recipients, PipelineOptions(max_selected=1))
    outcomes = {o.job_key: o for o in report.jobs}
    assert outcomes[jobs[0].dedup_key].status == "missing_recipient"
    assert outcomes[jobs[1].dedup_key].status == "below_threshold"
    selected = min(jobs[2].dedup_key, jobs[3].dedup_key)
    assert outcomes[selected].status == "preview"
    assert sum(o.status == "not_selected" for o in report.jobs) == 1
    generator.generate.assert_called_once()


@pytest.mark.parametrize("stage", ["analysis", "generation"])
async def test_one_bad_job_does_not_abort_others(store, candidate, stage):
    jobs = await seed(store, 2)
    analyzer, generator = adapters()
    if stage == "analysis":
        analyzer.analyze.side_effect = [ValueError("private"), understanding()]
    else:
        generator.generate.side_effect = [ValueError("private"), generated()]
    report = await Orchestrator(store, analyzer, generator).run(candidate, "plain", contacts(jobs))
    assert sorted(j.status for j in report.jobs) == [stage + "_failed", "preview"]


async def test_empty_storage_calls_nothing(store, candidate):
    analyzer, generator = adapters()
    report = await Orchestrator(store, analyzer, generator).run(candidate, "plain", {})
    assert report.jobs == []
    analyzer.analyze.assert_not_called()
    generator.generate.assert_not_called()


async def test_invalid_recipient_and_missing_writer_fail_before_model_calls(store, candidate):
    jobs = await seed(store)
    analyzer, generator = adapters()
    pipeline = Orchestrator(store, analyzer, generator)
    with pytest.raises(ValueError):
        await pipeline.run(candidate, "plain", {jobs[0].dedup_key: {"email": "not-email"}})
    with pytest.raises(ValueError, match="writer"):
        await pipeline.run(candidate, "plain", contacts(jobs), PipelineOptions(create_drafts=True))
    analyzer.analyze.assert_not_called()


async def test_invalid_selected_variant_cannot_create_draft(store, candidate):
    jobs = await seed(store)
    analyzer, generator = adapters()
    result = generated()
    result.best_variant = result.best_variant.model_copy(update={"body": "Not generated"})
    generator.generate.return_value = result
    writer = AsyncMock()
    report = await Orchestrator(store, analyzer, generator, writer).run(
        candidate, "plain", contacts(jobs), PipelineOptions(create_drafts=True))
    assert report.jobs[0].status == "generation_failed"
    writer.assert_not_awaited()


@pytest.mark.parametrize("values", [{"min_fit": -1}, {"min_fit": 2}, {"min_fit": float("nan")},
                                   {"max_selected": 0}, {"job_limit": 0}])
def test_invalid_options(values):
    with pytest.raises(ValueError):
        PipelineOptions(**values)


def test_cli_preview_default_requires_explicit_profile_and_contacts():
    from run_pipeline import build_parser
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = parser.parse_args(["--profile", "reviewed.json", "--recipients", "contacts.json"])
    assert not args.create_drafts


async def test_unknown_requirements_do_not_score_as_perfect_match(store, candidate):
    jobs = await seed(store)
    analyzer, generator = adapters()
    result = understanding()
    result.result.must_have_skills = []
    analyzer.analyze.return_value = result
    report = await Orchestrator(store, analyzer, generator).run(candidate, "plain", contacts(jobs))
    assert report.jobs[0].status == "insufficient_requirements"
    generator.generate.assert_not_called()


async def test_concurrent_runs_reserve_before_gmail(store, candidate):
    import asyncio
    jobs = await seed(store)
    analyzer, generator = adapters()
    entered = asyncio.Event()
    finish = asyncio.Event()
    async def writer(request):
        entered.set()
        await finish.wait()
        return "draft-one"
    pipeline = Orchestrator(store, analyzer, generator, writer)
    opts = PipelineOptions(create_drafts=True)
    task = asyncio.create_task(pipeline.run(candidate, "plain", contacts(jobs), opts))
    await entered.wait()
    second = await pipeline.run(candidate, "plain", contacts(jobs), opts)
    assert second.jobs[0].status == "needs_reconciliation"
    finish.set()
    first = await task
    assert first.jobs[0].status == "draft_created"


@pytest.mark.parametrize("value", [None, "", " "])
async def test_missing_draft_id_is_not_reported_as_success(store, candidate, value):
    jobs = await seed(store)
    analyzer, generator = adapters()
    pipeline = Orchestrator(store, analyzer, generator, AsyncMock(return_value=value))
    report = await pipeline.run(candidate, "plain", contacts(jobs), PipelineOptions(create_drafts=True))
    assert report.jobs[0].status == "needs_reconciliation"


@pytest.mark.parametrize("create_drafts", [False, True])
async def test_cli_offline_storage_to_report(tmp_path, monkeypatch, candidate, create_drafts):
    import json
    from run_pipeline import build_parser, run
    db = f"sqlite+aiosqlite:///{tmp_path}/pipeline.db"
    engine = make_engine(db)
    await init_db(engine)
    jobs = await seed(make_session_factory(engine))
    await engine.dispose()
    profile = tmp_path / "profile.json"
    profile.write_text(candidate.model_dump_json())
    recipients = tmp_path / "recipients.json"
    recipients.write_text(json.dumps({k: v.model_dump(mode="json") for k, v in contacts(jobs).items()}))
    personality = tmp_path / "personality.md"
    personality.write_text("Plain voice")
    output = tmp_path / "report.json"
    analyzer, generator = adapters()
    monkeypatch.setattr("agents.job_analyzer.engine.JobUnderstandingEngine", lambda: analyzer)
    monkeypatch.setattr("agents.email_generator.engine.EmailGenerationEngine", lambda: generator)
    auth = MagicMock(return_value=object())
    client = MagicMock()
    client.create_draft.return_value = ({"id": "cli-draft", "message": {}}, 1)
    client_factory = MagicMock(return_value=client)
    monkeypatch.setattr("database.gmail_auth.get_gmail_service", auth)
    monkeypatch.setattr("database.gmail_client.GmailDraftClient", client_factory)
    args = build_parser().parse_args([
        "--profile", str(profile), "--recipients", str(recipients),
        "--personality", str(personality), "--database", db, "--output", str(output)]
        + (["--create-drafts"] if create_drafts else []))
    report = await run(args)
    assert report.jobs[0].status == ("draft_created" if create_drafts else "preview")
    if create_drafts:
        auth.assert_called_once()
        assert client_factory.call_args.kwargs["max_attempts"] == 1
        client.create_draft.assert_called_once()
    else:
        auth.assert_not_called()
        client_factory.assert_not_called()
    assert json.loads(output.read_text())["jobs"][0]["request"]["to"] == "person0@example.com"


async def test_reservation_unique_constraint_blocks_second_writer(store):
    from database.draft_models import DraftRequest
    analyzer, generator = adapters()
    pipeline = Orchestrator(store, analyzer, generator)
    request = DraftRequest(to="person@example.com", subject="Review", body="Text")
    assert await pipeline._reserve("same-key", "job-key", request)
    assert not await pipeline._reserve("same-key", "job-key", request)
