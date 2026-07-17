"""Unit tests for Greenhouse, Lever, YC scrapers with mocked HTTP."""
from __future__ import annotations
import json
import httpx
import pytest
import respx
from agents.job_fetcher.models import JobSource
from agents.job_fetcher.scrapers.greenhouse import GREENHOUSE_API, GreenhouseScraper
from agents.job_fetcher.scrapers.lever import LEVER_API, LeverScraper
from agents.job_fetcher.scrapers.yc import YC_JOBS_URL, YCScraper
from tests.job_fetcher.fixtures import (
    GREENHOUSE_RESPONSE_JSON, GREENHOUSE_EMPTY_RESPONSE, GREENHOUSE_MALFORMED_RESPONSE,
    LEVER_RESPONSE_JSON, LEVER_EMPTY_RESPONSE, LEVER_WRONG_SHAPE_RESPONSE,
    YC_NEXT_DATA_RESPONSE, YC_EMPTY_HTML_RESPONSE,
)


class TestGreenhouseScraper:
    @pytest.fixture
    def client(self): return httpx.AsyncClient()

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_normalized_jobs(self, client):
        respx.get(GREENHOUSE_API.format(company="stripe")).mock(
            return_value=httpx.Response(200, text=GREENHOUSE_RESPONSE_JSON))
        result = await GreenhouseScraper(["stripe"], client=client).scrape()
        assert len(result.jobs) == 2 and result.source == JobSource.GREENHOUSE

    @respx.mock
    @pytest.mark.asyncio
    async def test_job_fields_populated(self, client):
        respx.get(GREENHOUSE_API.format(company="stripe")).mock(
            return_value=httpx.Response(200, text=GREENHOUSE_RESPONSE_JSON))
        result = await GreenhouseScraper(["stripe"], client=client).scrape()
        job = result.jobs[0]
        assert job.title == "Senior Software Engineer, Backend"
        assert "stripe" in job.company.lower()
        assert job.location == "San Francisco, CA"
        assert job.posted_at is not None
        assert "<p>" not in job.description

    @respx.mock
    @pytest.mark.asyncio
    async def test_raw_html_stored_as_json(self, client):
        respx.get(GREENHOUSE_API.format(company="stripe")).mock(
            return_value=httpx.Response(200, text=GREENHOUSE_RESPONSE_JSON))
        result = await GreenhouseScraper(["stripe"], client=client).scrape()
        parsed = json.loads(result.raw_jobs[0].raw_html)
        assert "title" in parsed

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_response(self, client):
        respx.get(GREENHOUSE_API.format(company="x")).mock(
            return_value=httpx.Response(200, json=GREENHOUSE_EMPTY_RESPONSE))
        result = await GreenhouseScraper(["x"], client=client).scrape()
        assert result.jobs == [] and result.errors == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_error_captured(self, client):
        respx.get(GREENHOUSE_API.format(company="x")).mock(
            return_value=httpx.Response(404, text="Not Found"))
        result = await GreenhouseScraper(["x"], client=client).scrape()
        assert result.jobs == [] and "404" in result.errors[0]

    @respx.mock
    @pytest.mark.asyncio
    async def test_malformed_json_captured(self, client):
        respx.get(GREENHOUSE_API.format(company="x")).mock(
            return_value=httpx.Response(200, text=GREENHOUSE_MALFORMED_RESPONSE))
        result = await GreenhouseScraper(["x"], client=client).scrape()
        assert result.jobs == [] and len(result.errors) == 1

    def test_empty_companies_raises(self):
        with pytest.raises(ValueError):
            GreenhouseScraper([])


class TestLeverScraper:
    @pytest.fixture
    def client(self): return httpx.AsyncClient()

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_normalized_jobs(self, client):
        respx.get(LEVER_API.format(company="vercel")).mock(
            return_value=httpx.Response(200, text=LEVER_RESPONSE_JSON))
        result = await LeverScraper(["vercel"], client=client).scrape()
        assert len(result.jobs) == 2 and result.source == JobSource.LEVER

    @respx.mock
    @pytest.mark.asyncio
    async def test_job_fields_populated(self, client):
        respx.get(LEVER_API.format(company="vercel")).mock(
            return_value=httpx.Response(200, text=LEVER_RESPONSE_JSON))
        result = await LeverScraper(["vercel"], client=client).scrape()
        job = result.jobs[0]
        assert job.title == "Staff Infrastructure Engineer"
        assert job.location == "Remote (US)"
        assert job.posted_at is not None
        assert "<p>" not in job.description

    @respx.mock
    @pytest.mark.asyncio
    async def test_plain_text_preferred(self, client):
        respx.get(LEVER_API.format(company="vercel")).mock(
            return_value=httpx.Response(200, text=LEVER_RESPONSE_JSON))
        result = await LeverScraper(["vercel"], client=client).scrape()
        assert "Vercel is building the frontend cloud" in result.jobs[0].description

    @respx.mock
    @pytest.mark.asyncio
    async def test_wrong_shape_captured(self, client):
        respx.get(LEVER_API.format(company="x")).mock(
            return_value=httpx.Response(200, text=LEVER_WRONG_SHAPE_RESPONSE))
        result = await LeverScraper(["x"], client=client).scrape()
        assert result.jobs == [] and "expected list" in result.errors[0]

    def test_empty_companies_raises(self):
        with pytest.raises(ValueError):
            LeverScraper([])


class TestYCScraper:
    @pytest.fixture
    def client(self): return httpx.AsyncClient()

    @respx.mock
    @pytest.mark.asyncio
    async def test_parses_next_data(self, client):
        respx.get(YC_JOBS_URL).mock(return_value=httpx.Response(200, text=YC_NEXT_DATA_RESPONSE))
        result = await YCScraper(client=client).scrape()
        assert len(result.jobs) == 2 and result.source == JobSource.YC

    @respx.mock
    @pytest.mark.asyncio
    async def test_next_data_fields(self, client):
        respx.get(YC_JOBS_URL).mock(return_value=httpx.Response(200, text=YC_NEXT_DATA_RESPONSE))
        result = await YCScraper(client=client).scrape()
        job = result.jobs[0]
        assert job.title == "Founding Engineer"
        assert job.company == "Stealth AI Startup"
        assert job.location == "San Francisco, CA"
        assert "<p>" not in job.description

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_page_returns_error(self, client):
        respx.get(YC_JOBS_URL).mock(return_value=httpx.Response(200, text=YC_EMPTY_HTML_RESPONSE))
        result = await YCScraper(client=client).scrape()
        assert result.jobs == [] and len(result.errors) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_error_captured(self, client):
        respx.get(YC_JOBS_URL).mock(return_value=httpx.Response(503, text="down"))
        result = await YCScraper(client=client).scrape()
        assert result.jobs == [] and "503" in result.errors[0]

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_captured(self, client):
        respx.get(YC_JOBS_URL).mock(side_effect=httpx.ConnectError("refused"))
        result = await YCScraper(client=client).scrape()
        assert result.jobs == [] and "request error" in result.errors[0]
