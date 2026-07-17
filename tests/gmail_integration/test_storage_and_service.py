"""Integration tests: DraftMetadataRepository + DraftService with in-memory SQLite."""
from __future__ import annotations
from datetime import datetime
from unittest.mock import MagicMock
import pytest
import pytest_asyncio
from googleapiclient.errors import HttpError
from database.draft_models import DraftMetadata, DraftRequest, DraftStatus
from database.draft_storage import (
    DraftMetadataRepository, init_db, make_engine, make_session_factory,
)
from database.gmail_client import GmailDraftClient
from database.gmail_service import DraftCreationFailedError, DraftService
from tests.gmail_integration.fixtures import (
    BAD_REQUEST_ERROR, DRAFT_REQUEST_BASIC, DRAFT_REQUEST_LONG_BODY,
    DRAFT_REQUEST_WITH_METADATA, GMAIL_MINIMAL_RESPONSE,
    GMAIL_SUCCESS_RESPONSE, GMAIL_SUCCESS_RESPONSE_2, RATE_LIMIT_ERROR,
)

IN_MEMORY = "sqlite+aiosqlite:///:memory:"


def _make_gmail_service(side_effects=None, return_value=None):
    mock_execute = MagicMock()
    if side_effects is not None:
        mock_execute.side_effect = side_effects
    else:
        mock_execute.return_value = return_value
    mock_create = MagicMock()
    mock_create.return_value.execute = mock_execute
    mock_drafts = MagicMock()
    mock_drafts.create = mock_create
    mock_users = MagicMock()
    mock_users.drafts.return_value = mock_drafts
    mock_service = MagicMock()
    mock_service.users.return_value = mock_users
    return mock_service


def _make_metadata(gmail_draft_id="r-1", to="test@example.com") -> DraftMetadata:
    return DraftMetadata(
        gmail_draft_id=gmail_draft_id,
        gmail_message_id=f"msg-{gmail_draft_id}",
        thread_id=f"thread-{gmail_draft_id}",
        to=to, subject="Subject", body_preview="Preview",
        created_at=datetime.utcnow(),
    )


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
    return DraftMetadataRepository(session)


# ═══════════════════════════════════════════════════════════════════════════════
# DraftMetadataRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TestDraftMetadataRepository:
    @pytest.mark.asyncio
    async def test_insert_returns_row_with_id(self, repo, session):
        row = await repo.insert(_make_metadata())
        await session.commit()
        assert row.id is not None and row.gmail_draft_id == "r-1"

    @pytest.mark.asyncio
    async def test_get_by_draft_id(self, repo, session):
        await repo.insert(_make_metadata(gmail_draft_id="r-find"))
        await session.commit()
        row = await repo.get_by_gmail_draft_id("r-find")
        assert row is not None and row.gmail_draft_id == "r-find"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, repo):
        assert await repo.get_by_gmail_draft_id("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, session):
        inserted = await repo.insert(_make_metadata())
        await session.commit()
        row = await repo.get_by_id(inserted.id)
        assert row is not None and row.id == inserted.id

    @pytest.mark.asyncio
    async def test_list_by_status(self, repo, session):
        await repo.insert(_make_metadata("r-1"))
        await repo.insert(_make_metadata("r-2"))
        await session.commit()
        rows = await repo.list_by_status(DraftStatus.CREATED)
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_list_by_company(self, repo, session):
        m1 = _make_metadata("r-1"); m1.company_name = "Lumina AI"
        m2 = _make_metadata("r-2"); m2.company_name = "Acme Corp"
        await repo.insert(m1); await repo.insert(m2)
        await session.commit()
        rows = await repo.list_by_company("Lumina AI")
        assert len(rows) == 1 and rows[0].gmail_draft_id == "r-1"

    @pytest.mark.asyncio
    async def test_count(self, repo, session):
        for i in range(5):
            await repo.insert(_make_metadata(f"r-{i}"))
        await session.commit()
        assert await repo.count() == 5

    @pytest.mark.asyncio
    async def test_update_status(self, repo, session):
        await repo.insert(_make_metadata("r-update"))
        await session.commit()
        assert await repo.update_status("r-update", DraftStatus.SENT) is True
        await session.commit()
        row = await repo.get_by_gmail_draft_id("r-update")
        assert row.status == DraftStatus.SENT.value

    @pytest.mark.asyncio
    async def test_update_status_false_for_missing(self, repo):
        assert await repo.update_status("none", DraftStatus.SENT) is False

    @pytest.mark.asyncio
    async def test_duplicate_draft_id_rejected(self, repo, session):
        await repo.insert(_make_metadata("r-dup"))
        await session.commit()
        with pytest.raises(Exception):
            await repo.insert(_make_metadata("r-dup"))
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# DraftService
# ═══════════════════════════════════════════════════════════════════════════════

class TestDraftServiceHappyPath:
    @pytest.mark.asyncio
    async def test_creates_and_persists_draft(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_WITH_METADATA))
        await session.commit()
        assert row.gmail_draft_id == "r-1234567890"
        assert row.status == DraftStatus.CREATED.value

    @pytest.mark.asyncio
    async def test_stores_metadata_fields(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_WITH_METADATA))
        await session.commit()
        assert row.candidate_name == "Divyansh Sharma"
        assert row.company_name   == "Lumina AI"
        assert row.variant_type   == "technical"
        assert row.expected_reply_rate == 0.41

    @pytest.mark.asyncio
    async def test_truncates_body_preview(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_LONG_BODY))
        await session.commit()
        assert len(row.body_preview) <= 500

    @pytest.mark.asyncio
    async def test_minimal_gmail_response_ok(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_MINIMAL_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        await session.commit()
        assert row.gmail_draft_id == "r-minimal"
        assert row.thread_id is None

    @pytest.mark.asyncio
    async def test_retry_count_zero_on_first_try(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        await session.commit()
        assert row.retry_count == 0

    @pytest.mark.asyncio
    async def test_retry_count_reflects_retries(self, session):
        gmail = _make_gmail_service(side_effects=[RATE_LIMIT_ERROR, GMAIL_SUCCESS_RESPONSE])
        service = DraftService(GmailDraftClient(gmail, max_attempts=3, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        await session.commit()
        assert row.retry_count == 1

    @pytest.mark.asyncio
    async def test_multiple_drafts_independent(self, session):
        gmail = _make_gmail_service(
            side_effects=[GMAIL_SUCCESS_RESPONSE, GMAIL_SUCCESS_RESPONSE_2]
        )
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        r1 = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        r2 = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_WITH_METADATA))
        await session.commit()
        assert r1.gmail_draft_id != r2.gmail_draft_id


class TestDraftServiceFailures:
    @pytest.mark.asyncio
    async def test_permanent_error_raises(self, session):
        gmail = _make_gmail_service(side_effects=[BAD_REQUEST_ERROR])
        service = DraftService(GmailDraftClient(gmail, max_attempts=3, wait_min=0, wait_max=0), session)
        with pytest.raises(DraftCreationFailedError) as exc_info:
            await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        assert isinstance(exc_info.value.original, HttpError)

    @pytest.mark.asyncio
    async def test_failed_draft_not_persisted(self, session, repo):
        gmail = _make_gmail_service(side_effects=[BAD_REQUEST_ERROR])
        service = DraftService(GmailDraftClient(gmail, max_attempts=3, wait_min=0, wait_max=0), session)
        with pytest.raises(DraftCreationFailedError):
            await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        assert await repo.count() == 0


class TestNeverSendGuarantee:
    @pytest.mark.asyncio
    async def test_service_has_no_send_method(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        public = [m for m in dir(service) if not m.startswith("_")]
        for m in public:
            assert "send" not in m.lower()

    @pytest.mark.asyncio
    async def test_client_has_no_send_method(self):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        client = GmailDraftClient(gmail, wait_min=0, wait_max=0)
        public = [m for m in dir(client) if not m.startswith("_")]
        for m in public:
            assert "send" not in m.lower()

    @pytest.mark.asyncio
    async def test_created_status_never_sent(self, session):
        gmail = _make_gmail_service(return_value=GMAIL_SUCCESS_RESPONSE)
        service = DraftService(GmailDraftClient(gmail, wait_min=0, wait_max=0), session)
        row = await service.create_draft(DraftRequest.model_validate(DRAFT_REQUEST_BASIC))
        await session.commit()
        assert row.status == DraftStatus.CREATED.value
        assert row.status != DraftStatus.SENT.value
