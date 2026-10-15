"""Offline recipient-discovery tests: real SQLite, fake fetchers, no network."""
import json
import os
import stat
from types import SimpleNamespace

import pytest

from agents.job_fetcher.models import NormalizedJob
from agents.job_fetcher.storage import JobRepository, init_db, make_engine, make_session_factory
from agents.recipient_discovery.extract import extract_emails, find_hiring_leads
from agents.recipient_discovery.models import ContactSource, ContactStatus
from agents.recipient_discovery.scout import candidate_page_urls, extract_links, page_text
from agents.recipient_discovery.service import RecipientDiscoveryService
from agents.recipient_discovery.storage import ContactRepository, init_contact_db
from orchestrator import Recipient


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("No external calls in discovery tests")
    monkeypatch.setattr(socket.socket, "connect", denied)


@pytest.fixture
async def store():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    await init_contact_db(engine)
    yield make_session_factory(engine)
    await engine.dispose()


async def seed(store, **kwargs):
    job = NormalizedJob(
        title=kwargs.get("title", "Backend Engineer"),
        company=kwargs.get("company", "Acme"),
        description=kwargs.get("description", "Build APIs."),
        url=kwargs.get("url", "https://acme.test/jobs/1"),
        source="lever", source_id=kwargs.get("source_id", "1"))
    async with store.begin() as session:
        await JobRepository(session).upsert_normalized(job)
    return job


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    async def fetch(self, url):
        self.requested.append(url)
        page = self.pages.get(url)
        if isinstance(page, Exception):
            raise page
        return page


# --- extraction -------------------------------------------------------------

def test_extracts_email_with_provenance_and_quote():
    text = "Questions? Mail Priya at priya@acme.com for details about the role."
    found = extract_emails(text, job_dedup_key="k", source=ContactSource.POSTING,
                           provenance="job posting")
    assert [str(c.email) for c in found] == ["priya@acme.com"]
    assert found[0].provenance == "job posting"
    assert "priya@acme.com" in found[0].context
    assert len(found[0].context) <= 160


@pytest.mark.parametrize("address", [
    "noreply@acme.com", "no-reply@acme.com", "donotreply@acme.com",
    "user@example.com", "name@domain.com", "test@test.com",
    "image@2x.png", "someone@sentry.io",
])
def test_rejects_non_contact_addresses(address):
    assert extract_emails(f"contact {address} now", job_dedup_key="k",
                          source=ContactSource.POSTING, provenance="p") == []


def test_keeps_recruiting_aliases():
    found = extract_emails("Write to careers@acme.com or talent@acme.io.",
                           job_dedup_key="k", source=ContactSource.POSTING, provenance="p")
    assert {str(c.email) for c in found} == {"careers@acme.com", "talent@acme.io"}


def test_dedupes_case_insensitively():
    found = extract_emails("Priya@Acme.com then priya@acme.com",
                           job_dedup_key="k", source=ContactSource.POSTING, provenance="p")
    assert len(found) == 1


def test_leads_find_hiring_keywords_only():
    leads = find_hiring_leads("Our recruiter will reach out.", job_dedup_key="k", provenance="p")
    assert len(leads) == 1 and "recruiter" in leads[0].description
    assert find_hiring_leads("Build software.", job_dedup_key="k", provenance="p") == []


# --- scout ------------------------------------------------------------------

def test_candidate_urls_only_http():
    assert candidate_page_urls("https://acme.test/jobs/1?utm=x") == ["https://acme.test/jobs/1"]
    assert candidate_page_urls("ftp://acme.test/x") == []
    assert candidate_page_urls("not a url") == []


def test_extract_links_finds_careers_skips_social():
    html = ('<a href="/careers">Careers</a><a href="https://linkedin.com/x">LinkedIn</a>'
            '<a href="/blog">Blog</a><a href="https://acme.test/team">Team</a>')
    links = extract_links(html, base_url="https://acme.test/jobs/1")
    assert "https://acme.test/careers" in links
    assert "https://acme.test/team" in links
    assert all("linkedin" not in l for l in links)


def test_page_text_strips_scripts():
    assert "evil" not in page_text("<script>evil()</script><p>Hello team</p>")
    assert "Hello team" in page_text("<script>evil()</script><p>Hello team</p>")


# --- storage ----------------------------------------------------------------

async def test_storage_dedupes_and_tracks_status(store):
    job = await seed(store, description="Mail priya@acme.com")
    async with store.begin() as session:
        repo = ContactRepository(session)
        candidates = extract_emails("Mail priya@acme.com", job_dedup_key=job.dedup_key,
                                    source=ContactSource.POSTING, provenance="p")
        assert await repo.add_candidates(candidates) == 1
        assert await repo.add_candidates(candidates) == 0
    async with store.begin() as session:
        repo = ContactRepository(session)
        assert await repo.set_status(job.dedup_key, "priya@acme.com",
                                     ContactStatus.APPROVED) is True
        assert await repo.set_status(job.dedup_key, "ghost@acme.com",
                                     ContactStatus.APPROVED) is False
    async with store() as session:
        rows = await ContactRepository(session).list_candidates(ContactStatus.APPROVED)
        assert len(rows) == 1 and rows[0].reviewed_at is not None


async def test_approved_map_matches_pipeline_recipient_schema(store):
    job = await seed(store, description="Mail priya@acme.com")
    async with store.begin() as session:
        repo = ContactRepository(session)
        await repo.add_candidates(extract_emails(
            "Mail priya@acme.com or sam@acme.com", job_dedup_key=job.dedup_key,
            source=ContactSource.POSTING, provenance="p"))
        await repo.set_status(job.dedup_key, "priya@acme.com", ContactStatus.APPROVED)
    async with store() as session:
        mapping = await ContactRepository(session).approved_map()
    assert list(mapping) == [job.dedup_key]
    # The exact schema run_pipeline.py validates.
    Recipient.model_validate(mapping[job.dedup_key])


# --- service ----------------------------------------------------------------

async def test_offline_scan_stores_proposals(store):
    job = await seed(store, description="Questions: priya@acme.com. Our recruiter helps.")
    async with store() as session:
        service = RecipientDiscoveryService(ContactRepository(session), JobRepository(session))
        report = await service.scan()
    assert report.new_candidates == 1
    result = report.results[0]
    assert [str(c.email) for c in result.candidates] == ["priya@acme.com"]
    assert result.candidates[0].status == ContactStatus.PROPOSED
    assert any("recruiter" in lead.description for lead in result.leads)
    async with store() as session:
        rows = await ContactRepository(session).list_candidates()
        assert len(rows) == 1 and rows[0].status == "proposed"


async def test_scan_with_pages_quotes_page_contacts(store):
    posting = "https://acme.test/jobs/1"
    careers = "https://acme.test/careers"
    job = await seed(store, description="No address here.", url=posting)
    fetcher = FakeFetcher({
        posting: f'<p>Role details</p><a href="/careers">Careers</a>',
        careers: "<script>junk()</script><p>Reach hiring@acme.com about roles</p>",
    })
    async with store() as session:
        service = RecipientDiscoveryService(
            ContactRepository(session), JobRepository(session), fetcher=fetcher)
        report = await service.scan()
    found = {str(c.email): c for c in report.results[0].candidates}
    assert "hiring@acme.com" in found
    assert found["hiring@acme.com"].source == ContactSource.COMPANY_PAGE
    assert found["hiring@acme.com"].provenance == careers
    assert "junk" not in found["hiring@acme.com"].context
    assert set(fetcher.requested) == {posting, careers}


async def test_scan_survives_page_failures(store):
    posting = "https://acme.test/jobs/1"
    await seed(store, description="Mail priya@acme.com", url=posting)
    fetcher = FakeFetcher({posting: RuntimeError("boom")})
    async with store() as session:
        service = RecipientDiscoveryService(
            ContactRepository(session), JobRepository(session), fetcher=fetcher)
        report = await service.scan()
    assert report.results[0].errors == []
    assert [str(c.email) for c in report.results[0].candidates] == ["priya@acme.com"]


async def test_rescan_does_not_duplicate(store):
    await seed(store, description="Mail priya@acme.com")
    async with store() as session:
        service = RecipientDiscoveryService(ContactRepository(session), JobRepository(session))
        await service.scan()
        second = await service.scan()
    assert second.new_candidates == 0


# --- CLI lifecycle ----------------------------------------------------------

def _cli_args(**over):
    base = dict(database=None, command="scan", fetch_pages=False, job_limit=100,
                output=None, status="proposed", job=None, email=None)
    base.update(over)
    return SimpleNamespace(**base)


async def _seed_file_db(path):
    url = f"sqlite+aiosqlite:///{path}"
    engine = make_engine(url)
    await init_db(engine)
    await init_contact_db(engine)
    sessions = make_session_factory(engine)
    async with sessions.begin() as session:
        await JobRepository(session).upsert_normalized(NormalizedJob(
            title="Backend Engineer", company="Acme",
            description="Talk to priya@acme.com", url="https://acme.test/jobs/1",
            source="lever", source_id="1"))
        row = (await session.execute(
            __import__("sqlalchemy").select(
                __import__("agents.job_fetcher.storage", fromlist=["NormalizedJobRow"]).NormalizedJobRow
            ))).scalars().first()
        key = row.dedup_key
    await engine.dispose()
    return url, key


async def test_cli_scan_approve_export(tmp_path, capsys):
    from discover_recipients import cmd_scan, cmd_export, cmd_mark
    url, key = await _seed_file_db(tmp_path / "contacts.db")
    assert await cmd_scan(_cli_args(database=url)) == 0
    assert "priya@acme.com" in capsys.readouterr().out

    assert await cmd_mark(_cli_args(database=url, job=[key], email=["priya@acme.com"]),
                          ContactStatus.APPROVED) == 0
    out = tmp_path / "recipients.json"
    assert await cmd_export(_cli_args(database=url, output=str(out))) == 0
    exported = json.loads(out.read_text())
    assert list(exported) == [key]
    Recipient.model_validate(exported[key])
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o600


async def test_cli_export_requires_approval(tmp_path):
    from discover_recipients import cmd_export
    url, _ = await _seed_file_db(tmp_path / "contacts.db")
    out = tmp_path / "recipients.json"
    assert await cmd_export(_cli_args(database=url, output=str(out))) == 1
    assert not out.exists()


async def test_cli_approve_unknown_fails(tmp_path):
    from discover_recipients import cmd_mark
    url, key = await _seed_file_db(tmp_path / "contacts.db")
    assert await cmd_mark(_cli_args(database=url, job=[key], email=["ghost@acme.com"]),
                          ContactStatus.APPROVED) == 1
