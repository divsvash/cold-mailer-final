"""Optional live fetching of public pages for contact extraction.

Fetching only happens when a fetcher is injected (the CLI's --fetch-pages).
Owned clients follow the repo's hardened scraper pattern: no redirects,
bounded timeouts, bounded page size, script/style stripped before parsing.
"""
from __future__ import annotations
import re
from typing import Protocol
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from agents.job_fetcher.scrapers.base import BaseScraper, DEFAULT_HEADERS, DEFAULT_TIMEOUT

MAX_PAGE_BYTES = 1_000_000
MAX_LINKED_PAGES = 2

# Pages that never carry direct hiring contacts and sit behind login walls.
_SKIP_HOSTS = {
    "linkedin.com", "www.linkedin.com", "twitter.com", "x.com", "www.x.com",
    "facebook.com", "www.facebook.com", "instagram.com", "www.instagram.com",
    "glassdoor.com", "www.glassdoor.com", "indeed.com", "www.indeed.com",
}
_LINK_HINTS = ("career", "jobs", "team", "about", "contact", "people", "join")


def candidate_page_urls(job_url: str) -> list[str]:
    """The job's own public posting page is the starting point. http(s) only."""
    parsed = urlparse((job_url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return []
    return [f"{parsed.scheme}://{parsed.netloc}{parsed.path}"]


def extract_links(html: str, *, base_url: str, limit: int = MAX_LINKED_PAGES) -> list[str]:
    """Careers/team/about links quoted from a fetched page, for one hop deeper."""
    soup = BeautifulSoup(html or "", "html.parser")
    base_host = urlparse(base_url).netloc.lower()
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        text = (anchor.get_text() or "").lower()
        href = anchor["href"].strip().lower()
        if not any(hint in text or hint in href for hint in _LINK_HINTS):
            continue
        absolute = urljoin(base_url, anchor["href"])
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        host = parsed.netloc.lower()
        if host in _SKIP_HOSTS:
            continue
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean in seen:
            continue
        seen.add(clean)
        links.append(clean)
        if len(links) >= limit:
            break
    return links


def page_text(html: str) -> str:
    return BaseScraper.strip_html(html)


class PageFetcher(Protocol):
    async def fetch(self, url: str) -> str | None:
        """Return raw HTML for a public page, or None when unavailable."""


class HttpxPageFetcher:
    """Live fetcher used only on explicit --fetch-pages. Never follows redirects."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(
            headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=False
        )

    async def __aenter__(self) -> "HttpxPageFetcher":
        return self

    async def __aexit__(self, *_) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def fetch(self, url: str) -> str | None:
        try:
            response = await self._client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return None
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_PAGE_BYTES:
            return None
        body = response.text
        if len(body) > MAX_PAGE_BYTES:
            return None
        return body
