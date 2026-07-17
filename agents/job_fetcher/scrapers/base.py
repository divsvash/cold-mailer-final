"""Base scraper with shared HTML-stripping and date-parsing utilities."""
from __future__ import annotations
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
import httpx
from bs4 import BeautifulSoup
from agents.job_fetcher.models import JobSource, ScrapeResult

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*;q=0.9",
}
DEFAULT_TIMEOUT = httpx.Timeout(connect=15.0, read=30.0, write=10.0, pool=5.0)


class BaseScraper(ABC):
    source: JobSource

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(
            headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True
        )

    async def __aenter__(self) -> "BaseScraper":
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._owned_client:
            await self._client.aclose()

    @abstractmethod
    async def scrape(self) -> ScrapeResult: ...

    @staticmethod
    def strip_html(html: str) -> str:
        if not html:
            return ""
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def parse_date(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, (int, float)) and value > 1_000_000_000_000:
            try:
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None
        if isinstance(value, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(value.strip(), fmt)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return None

    @staticmethod
    def clean_location(raw: Any) -> str | None:
        if raw is None:
            return None
        if isinstance(raw, dict):
            raw = raw.get("name") or raw.get("city") or raw.get("location") or ""
        if not isinstance(raw, str):
            return None
        return raw.strip() or None
