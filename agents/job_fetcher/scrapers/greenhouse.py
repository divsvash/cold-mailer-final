"""Greenhouse board API scraper."""
from __future__ import annotations
import json
from typing import Any
import httpx
from agents.job_fetcher.models import JobSource, NormalizedJob, RawJob, ScrapeResult
from agents.job_fetcher.scrapers.base import BaseScraper

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


class GreenhouseScraper(BaseScraper):
    source = JobSource.GREENHOUSE

    def __init__(self, companies: list[str], client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client)
        if not companies:
            raise ValueError("At least one company slug is required")
        self._companies = companies

    async def scrape(self) -> ScrapeResult:
        result = ScrapeResult(source=self.source)
        for company in self._companies:
            url = GREENHOUSE_API.format(company=company)
            try:
                response = await self._client.get(url, params={"content": "true"})
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                result.errors.append(f"Greenhouse/{company}: HTTP {exc.response.status_code}")
                continue
            except httpx.RequestError as exc:
                result.errors.append(f"Greenhouse/{company}: request error — {exc}")
                continue
            try:
                data: dict[str, Any] = response.json()
            except Exception as exc:
                result.errors.append(f"Greenhouse/{company}: invalid JSON — {exc}")
                continue
            for job in data.get("jobs", []):
                job_id = str(job.get("id", ""))
                if not job_id:
                    continue
                raw = RawJob(
                    source=self.source, source_id=f"{company}:{job_id}",
                    raw_html=json.dumps(job),
                    source_metadata={"company_slug": company, "departments": job.get("departments", [])},
                )
                result.raw_jobs.append(raw)
                try:
                    result.jobs.append(NormalizedJob(
                        title=job.get("title") or "",
                        company=company.replace("-", " ").title(),
                        location=self.clean_location(job.get("location")),
                        url=job.get("absolute_url") or "",
                        description=self.strip_html(job.get("content") or ""),
                        posted_at=self.parse_date(job.get("updated_at")),
                        source=self.source, source_id=f"{company}:{job_id}",
                    ))
                except Exception as exc:
                    result.errors.append(f"Greenhouse/{company} job {job_id}: {exc}")
        return result
