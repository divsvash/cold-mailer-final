"""Lever postings API scraper."""
from __future__ import annotations
import json
import httpx
from agents.job_fetcher.models import JobSource, NormalizedJob, RawJob, ScrapeResult
from agents.job_fetcher.scrapers.base import BaseScraper, validate_company_slug

LEVER_API = "https://api.lever.co/v0/postings/{company}"


class LeverScraper(BaseScraper):
    source = JobSource.LEVER

    def __init__(self, companies: list[str], client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client)
        if not companies:
            raise ValueError("At least one company slug is required")
        self._companies = [validate_company_slug(company) for company in companies]

    async def scrape(self) -> ScrapeResult:
        result = ScrapeResult(source=self.source)
        for company in self._companies:
            url = LEVER_API.format(company=company)
            try:
                response = await self._client.get(url, params={"mode": "json"})
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                result.errors.append(f"Lever/{company}: HTTP {exc.response.status_code}")
                continue
            except httpx.RequestError as exc:
                result.errors.append(f"Lever/{company}: request error — {exc}")
                continue
            try:
                jobs_data: list[dict] = response.json()
            except Exception as exc:
                result.errors.append(f"Lever/{company}: invalid JSON — {exc}")
                continue
            if not isinstance(jobs_data, list):
                result.errors.append(f"Lever/{company}: unexpected response shape (expected list)")
                continue
            for job in jobs_data:
                job_id = str(job.get("id", ""))
                if not job_id:
                    continue
                raw = RawJob(
                    source=self.source, source_id=f"{company}:{job_id}",
                    raw_html=json.dumps(job),
                    source_metadata={"company_slug": company, "categories": job.get("categories", {})},
                )
                result.raw_jobs.append(raw)
                description = job.get("descriptionPlain") or self.strip_html(job.get("description") or "")
                for section in job.get("lists", []):
                    section_text = self.strip_html(section.get("content", ""))
                    if section_text:
                        description += f"\n\n{section.get('text', '')}\n{section_text}"
                categories = job.get("categories") or {}
                location = self.clean_location(categories.get("location"))
                try:
                    result.jobs.append(NormalizedJob(
                        title=job.get("text") or "",
                        company=company.replace("-", " ").title(),
                        location=location,
                        url=job.get("hostedUrl") or "",
                        description=description.strip(),
                        posted_at=self.parse_date(job.get("createdAt")),
                        source=self.source, source_id=f"{company}:{job_id}",
                    ))
                except Exception as exc:
                    result.errors.append(f"Lever/{company} job {job_id}: {exc}")
        return result
