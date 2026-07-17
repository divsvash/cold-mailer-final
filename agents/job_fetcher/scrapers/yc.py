"""YC / workatastartup.com scraper — __NEXT_DATA__ first, HTML fallback."""
from __future__ import annotations
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
import httpx
from bs4 import BeautifulSoup, Tag
from agents.job_fetcher.models import JobSource, NormalizedJob, RawJob, ScrapeResult
from agents.job_fetcher.scrapers.base import BaseScraper

YC_JOBS_URL = "https://www.workatastartup.com/jobs"
YC_BASE_URL = "https://www.workatastartup.com"


def _parse_relative_date(text: str) -> datetime | None:
    text = text.lower().strip()
    now  = datetime.now(tz=timezone.utc)
    patterns = [
        (r"(\d+)\s+day",   lambda n: now - timedelta(days=int(n))),
        (r"(\d+)\s+week",  lambda n: now - timedelta(weeks=int(n))),
        (r"(\d+)\s+month", lambda n: now - timedelta(days=int(n) * 30)),
        (r"(\d+)\s+hour",  lambda n: now - timedelta(hours=int(n))),
        (r"today|just now", lambda _: now),
        (r"yesterday",      lambda _: now - timedelta(days=1)),
    ]
    for pattern, calc in patterns:
        m = re.search(pattern, text)
        if m:
            n = m.group(1) if m.lastindex else "0"
            return calc(n)
    return None


class YCScraper(BaseScraper):
    source = JobSource.YC

    async def scrape(self) -> ScrapeResult:
        result = ScrapeResult(source=self.source)
        try:
            response = await self._client.get(YC_JOBS_URL)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            result.errors.append(f"YC Jobs: HTTP {exc.response.status_code}")
            return result
        except httpx.RequestError as exc:
            result.errors.append(f"YC Jobs: request error — {exc}")
            return result

        page_html = response.text
        jobs_parsed = self._parse_next_data(page_html) or self._parse_html(page_html)

        if not jobs_parsed:
            result.errors.append("YC Jobs: could not extract any jobs from the page")
            return result

        for job_data in jobs_parsed:
            job_id = str(job_data.get("id", ""))
            if not job_id:
                continue
            raw = RawJob(
                source=self.source, source_id=job_id,
                raw_html=job_data.get("raw_html", page_html),
                source_metadata={
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in job_data.items() if k != "raw_html"
                },
            )
            result.raw_jobs.append(raw)
            try:
                result.jobs.append(NormalizedJob(
                    title=job_data.get("title") or "",
                    company=job_data.get("company") or "",
                    location=self.clean_location(job_data.get("location")),
                    url=job_data.get("url") or "",
                    description=self.strip_html(job_data.get("description") or ""),
                    posted_at=job_data.get("posted_at"),
                    source=self.source, source_id=job_id,
                ))
            except Exception as exc:
                result.errors.append(f"YC job {job_id}: {exc}")
        return result

    def _parse_next_data(self, html: str) -> list[dict[str, Any]]:
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
            raw_jobs = data["props"]["pageProps"].get("jobs") or data["props"]["pageProps"].get("jobListings") or []
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
        parsed: list[dict[str, Any]] = []
        for j in raw_jobs:
            job_id = str(j.get("id") or j.get("jobId") or "")
            if not job_id:
                continue
            company_info = j.get("company") or {}
            company_name = company_info.get("name") if isinstance(company_info, dict) else str(company_info)
            parsed.append({
                "id": job_id, "title": j.get("title") or j.get("role") or "",
                "company": company_name or "", "location": j.get("location") or "",
                "url": j.get("url") or f"{YC_BASE_URL}/jobs/{job_id}",
                "description": j.get("description") or j.get("body") or "",
                "posted_at": self.parse_date(j.get("createdAt") or j.get("postedAt")),
                "raw_html": json.dumps(j),
            })
        return parsed

    def _parse_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        cards: list[Tag] = soup.find_all(True, attrs={"data-jobid": True}) or \
                           soup.find_all(True, class_=re.compile(r"job-listing|job-card|posting"))
        parsed: list[dict[str, Any]] = []
        for card in cards:
            job_id = card.get("data-jobid") or card.get("data-id") or card.get("id", "").replace("job-", "")
            if not job_id:
                continue
            title_el    = card.find(class_=re.compile(r"job-name|job-title|title"))
            company_el  = card.find(class_=re.compile(r"company-name|startup-name"))
            location_el = card.find(class_=re.compile(r"location|job-location"))
            date_el     = card.find(class_=re.compile(r"date|posted"))
            link_el     = card.find("a", href=re.compile(r"/jobs/"))
            title   = title_el.get_text(strip=True)   if title_el   else ""
            company = company_el.get_text(strip=True)  if company_el else ""
            if not title:
                continue
            url = (f"{YC_BASE_URL}{link_el['href']}" if link_el and link_el.get("href") else f"{YC_BASE_URL}/jobs/{job_id}")
            date_text = date_el.get_text(strip=True) if date_el else ""
            parsed.append({
                "id": str(job_id), "title": title, "company": company,
                "location": location_el.get_text(strip=True) if location_el else None,
                "url": url, "description": str(card),
                "posted_at": _parse_relative_date(date_text) or self.parse_date(date_text),
                "raw_html": str(card),
            })
        return parsed
