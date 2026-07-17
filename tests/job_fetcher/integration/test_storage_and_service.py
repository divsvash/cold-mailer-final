"""Integration tests: JobRepository + JobDiscoveryService with in-memory SQLite."""
from __future__ import annotations
from datetime import datetime
import httpx
import pytest
import pytest_asyncio
import respx
from agents.job_fetcher.models import JobSource, NormalizedJob, RawJob
from agents.job_fetcher.service import DiscoveryConfig, JobDiscoveryService
from agents.job_fetcher.storage import JobRepository, init_db, make_engine, make_session_factory
from agents.job_fetcher.scrapers.greenhouse import GREENHOUSE_API
from agents.job_fetcher.scrapers.lever import LEVER_API
from agents.job_fetcher.scrapers.yc import YC_JOBS_URL
from tests.job_fetcher.fixtures import GREENHOUSE_RESPONSE_JSON, LEVER_RESPONSE_JSON, YC_NEXT_DATA_RESPONSE

IN_MEMORY = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = make_engine(IN_MEMORY)
    await init_db(eng)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = make_session_factory(engine)
    async with factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def repo(session):
    return JobRepository(session)


def make_raw(source=JobSource.GREENHOUSE, source_id="acme:1") -> RawJob:
    return RawJob(source=source, source_id=source_id, raw_html="<div>job</div>")


def make_normalized(title="Engineer", company="Acme", url="https://example.com/1",
                    source=JobSource.GREENHOUSE, source_id="acme:1") -> NormalizedJob:
    return NormalizedJob(title=title, company=company, url=url,
                        description="A great role.", source=source, source_id=source_id)


class TestJobRepository:
    @pytest.mark.asyncio
    async def test_upsert_raw_inserts_new(self, repo, session):
        is_new = await repo.upsert_raw(make_raw())
        await session.commit()
        assert is_new is True

    @pytest.mark.asyncio
    async def test_upsert_raw_duplicate_returns_false(self, repo, session):
        raw = make_raw()
        await repo.upsert_raw(raw)
        await session.commit()
        assert await repo.upsert_raw(raw) is False

    @pytest.mark.asyncio
    async def test_upsert_normalized_inserts_new(self, repo, session):
        is_new = await repo.upsert_normalized(make_normalized())
        await session.commit()
        assert is_new is True

    @pytest.mark.asyncio
    async def test_upsert_normalized_duplicate_returns_false(self, repo, session):
        job = make_normalized()
        await repo.upsert_normalized(job)
        await session.commit()
        assert await repo.upsert_normalized(job) is False

    @pytest.mark.asyncio
    async def test_count_normalized(self, repo, session):
        for i in range(4):
            await repo.upsert_normalized(make_normalized(url=f"https://example.com/{i}", source_id=f"s:{i}"))
        await session.commit()
        assert await repo.count_normalized() == 4

    @pytest.mark.asyncio
    async def test_cross_source_dedup_via_dedup_key(self, repo, session):
        gh = NormalizedJob(title="SWE", company="Acme", url="https://acme.com/1",
                          description="d", source=JobSource.GREENHOUSE, source_id="gh:1")
        lv = NormalizedJob(title="SWE", company="Acme", url="https://acme.com/1",
                          description="d", source=JobSource.LEVER, source_id="lv:1")
        assert gh.dedup_key == lv.dedup_key
        assert await repo.upsert_normalized(gh) is True
        assert await repo.upsert_normalized(lv) is False
        await session.commit()
        assert await repo.count_normalized() == 1


class TestJobDiscoveryServicePipeline:
    def _cfg(self) -> DiscoveryConfig:
        return DiscoveryConfig(
            greenhouse_companies=["stripe"],
            lever_companies=["vercel"],
            include_yc=True,
            db_url=IN_MEMORY,
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_full_run_persists_jobs(self):
        respx.get(GREENHOUSE_API.format(company="stripe")).mock(
            return_value=httpx.Response(200, text=GREENHOUSE_RESPONSE_JSON))
        respx.get(LEVER_API.format(company="vercel")).mock(
            return_value=httpx.Response(200, text=LEVER_RESPONSE_JSON))
        respx.get(YC_JOBS_URL).mock(
            return_value=httpx.Response(200, text=YC_NEXT_DATA_RESPONSE))
        report = await JobDiscoveryService(self._cfg()).run()
        assert report.new_jobs > 0 and report.finished_at is not None

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_scrapers_returns_error(self):
        cfg = DiscoveryConfig(greenhouse_companies=[], lever_companies=[], include_yc=False, db_url=IN_MEMORY)
        report = await JobDiscoveryService(cfg).run()
        assert report.new_jobs == 0 and "No scrapers" in report.errors[0]

    @respx.mock
    @pytest.mark.asyncio
    async def test_partial_failure_continues(self):
        respx.get(GREENHOUSE_API.format(company="stripe")).mock(
            return_value=httpx.Response(500, text="err"))
        respx.get(LEVER_API.format(company="vercel")).mock(
            return_value=httpx.Response(200, text=LEVER_RESPONSE_JSON))
        respx.get(YC_JOBS_URL).mock(
            return_value=httpx.Response(200, text=YC_NEXT_DATA_RESPONSE))
        report = await JobDiscoveryService(self._cfg()).run()
        assert report.new_jobs > 0 and len(report.errors) >= 1
