"""Job discovery service — runs all scrapers, deduplicates, persists."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
import httpx
from config import get_settings
from agents.job_fetcher.deduplicator import DeduplicationReport, merge_results
from agents.job_fetcher.models import JobSource, ScrapeResult
from agents.job_fetcher.scrapers.base import BaseScraper
from agents.job_fetcher.scrapers.greenhouse import GreenhouseScraper
from agents.job_fetcher.scrapers.lever import LeverScraper
from agents.job_fetcher.scrapers.yc import YCScraper
from agents.job_fetcher.storage import JobRepository, init_db, make_engine, make_session_factory

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    greenhouse_companies: list[str] = field(default_factory=lambda: get_settings().GREENHOUSE_COMPANIES.copy())
    lever_companies:      list[str] = field(default_factory=lambda: get_settings().LEVER_COMPANIES.copy())
    include_yc:           bool      = field(default_factory=lambda: get_settings().INCLUDE_YC_JOBS)
    db_url:               str       = field(default_factory=lambda: get_settings().DATABASE_URL)
    concurrency:          int       = field(default_factory=lambda: get_settings().MAX_CONCURRENT_SCRAPERS)


@dataclass
class DiscoveryReport:
    started_at:     datetime            = field(default_factory=datetime.utcnow)
    finished_at:    datetime | None     = None
    scrape_results: list[ScrapeResult]  = field(default_factory=list)
    dedup_report:   DeduplicationReport | None = None
    new_jobs:       int                 = 0
    errors:         list[str]           = field(default_factory=list)

    @property
    def total_scraped(self) -> int:
        return sum(len(r.jobs) for r in self.scrape_results)

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


async def _run_scraper(scraper: BaseScraper) -> ScrapeResult:
    try:
        async with scraper:
            return await scraper.scrape()
    except Exception as exc:
        result = ScrapeResult(source=scraper.source)
        result.errors.append(f"Unhandled error in {scraper.source}: {exc}")
        return result


class JobDiscoveryService:
    def __init__(self, config: DiscoveryConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._client = client

    def _build_scrapers(self) -> list[BaseScraper]:
        scrapers: list[BaseScraper] = []
        if self._config.greenhouse_companies:
            scrapers.append(GreenhouseScraper(self._config.greenhouse_companies, client=self._client))
        if self._config.lever_companies:
            scrapers.append(LeverScraper(self._config.lever_companies, client=self._client))
        if self._config.include_yc:
            scrapers.append(YCScraper(client=self._client))
        return scrapers

    async def run(self) -> DiscoveryReport:
        report = DiscoveryReport()
        scrapers = self._build_scrapers()
        if not scrapers:
            report.errors.append("No scrapers configured.")
            report.finished_at = datetime.utcnow()
            return report

        sem = asyncio.Semaphore(self._config.concurrency)

        async def bounded(s: BaseScraper) -> ScrapeResult:
            async with sem:
                return await _run_scraper(s)

        scrape_results = list(await asyncio.gather(*(bounded(s) for s in scrapers)))
        report.scrape_results = scrape_results
        for sr in scrape_results:
            report.errors.extend(sr.errors)

        deduped_jobs, dedup_report = merge_results(*scrape_results)
        report.dedup_report = dedup_report

        engine  = make_engine(self._config.db_url)
        await init_db(engine)
        factory = make_session_factory(engine)

        async with factory() as session:
            async with session.begin():
                repo = JobRepository(session)
                for sr in scrape_results:
                    for raw in sr.raw_jobs:
                        await repo.upsert_raw(raw)
                new_count = 0
                for job in deduped_jobs:
                    if await repo.upsert_normalized(job):
                        new_count += 1

        report.new_jobs    = new_count
        report.finished_at = datetime.utcnow()
        await engine.dispose()
        return report
