"""Recipient discovery: quoted contacts for stored jobs, review-gated."""
from __future__ import annotations
from datetime import datetime
from agents.job_fetcher.storage import JobRepository, NormalizedJobRow
from agents.recipient_discovery.extract import extract_emails, find_hiring_leads
from agents.recipient_discovery.models import (
    ContactCandidate, ContactSource, DiscoveryScanReport, JobDiscoveryResult,
)
from agents.recipient_discovery.scout import (
    PageFetcher, candidate_page_urls, extract_links, page_text,
)
from agents.recipient_discovery.storage import ContactRepository

MAX_PAGES_PER_JOB = 3


class RecipientDiscoveryService:
    """Finds candidate contacts. A fetcher enables live page fetching; without
    one the scan is fully offline over stored posting text. Either way every
    candidate lands as PROPOSED and only explicit review approves it."""

    def __init__(self, contacts: ContactRepository, jobs: JobRepository,
                 fetcher: PageFetcher | None = None) -> None:
        self._contacts = contacts
        self._jobs = jobs
        self._fetcher = fetcher

    async def scan(self, job_limit: int = 100) -> DiscoveryScanReport:
        report = DiscoveryScanReport()
        jobs = await self._jobs.list_normalized(job_limit)
        for job in jobs:
            result = await self._scan_one(job)
            report.results.append(result)
            added = await self._contacts.add_candidates(result.candidates)
            report.new_candidates += added
            await self._commit_one(result)
        report.finished_at = datetime.utcnow()
        return report

    async def _commit_one(self, result: JobDiscoveryResult) -> None:
        session = self._contacts._session  # same session the repo writes through
        try:
            await session.commit()
        except Exception as exc:  # one job's storage failure must not abort others
            await session.rollback()
            result.errors.append(f"storage failure: {type(exc).__name__}")

    async def _scan_one(self, job: NormalizedJobRow) -> JobDiscoveryResult:
        result = JobDiscoveryResult(
            job_dedup_key=job.dedup_key, company=job.company, title=job.title)
        try:
            candidates = extract_emails(
                job.description, job_dedup_key=job.dedup_key,
                source=ContactSource.POSTING, provenance="job posting")
            leads = find_hiring_leads(
                job.description, job_dedup_key=job.dedup_key, provenance="job posting")
            if self._fetcher is not None:
                page_candidates, page_leads = await self._scan_pages(job)
                candidates.extend(page_candidates)
                leads.extend(page_leads)
            result.candidates = _dedupe(candidates)
            result.leads = leads
        except Exception as exc:
            # Errors stay generic on purpose: upstream text can be private.
            result.errors.append(f"discovery failed: {type(exc).__name__}")
        return result

    async def _scan_pages(self, job: NormalizedJobRow):
        candidates: list[ContactCandidate] = []
        leads: list = []
        queue = candidate_page_urls(job.url)
        fetched = 0
        while queue and fetched < MAX_PAGES_PER_JOB:
            url = queue.pop(0)
            fetched += 1
            try:
                html = await self._fetcher.fetch(url)
            except Exception:
                continue
            if not html:
                continue
            text = page_text(html)
            candidates.extend(extract_emails(
                text, job_dedup_key=job.dedup_key,
                source=ContactSource.COMPANY_PAGE, provenance=url))
            leads.extend(find_hiring_leads(
                text, job_dedup_key=job.dedup_key, provenance=url))
            if fetched == 1:  # only the posting page gets one hop deeper
                queue.extend(u for u in extract_links(html, base_url=url) if u not in queue)
        return candidates, leads


def _dedupe(candidates: list[ContactCandidate]) -> list[ContactCandidate]:
    """First provenance wins: the posting beats any company page."""
    seen: set[str] = set()
    unique: list[ContactCandidate] = []
    for candidate in candidates:
        key = str(candidate.email)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique
