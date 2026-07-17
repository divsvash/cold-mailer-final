"""Draft service — create drafts and query metadata. Never sends."""
from __future__ import annotations
from datetime import datetime
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession
from database.gmail_client import GmailDraftClient
from database.draft_models import DraftMetadata, DraftRequest, DraftStatus
from database.draft_storage import DraftMetadataRepository, DraftMetadataRow

BODY_PREVIEW_LENGTH = 500


class DraftCreationFailedError(Exception):
    def __init__(self, request: DraftRequest, original: Exception, retry_count: int) -> None:
        self.request     = request
        self.original    = original
        self.retry_count = retry_count
        super().__init__(f"Failed to create draft for {request.to} after {retry_count} attempt(s): {original}")


class DraftService:
    """Public API: create_draft, get_draft, list_drafts_for_company, list_drafts_by_status."""

    def __init__(self, gmail_client: GmailDraftClient, session: AsyncSession) -> None:
        self._gmail  = gmail_client
        self._session= session
        self._repo   = DraftMetadataRepository(session)

    async def create_draft(self, request: DraftRequest) -> DraftMetadataRow:
        try:
            response, attempt_count = self._gmail.create_draft(request.to, request.subject, request.body)
        except HttpError as exc:
            raise DraftCreationFailedError(request, exc, retry_count=getattr(exc, "retry_attempts", 1)) from exc
        except Exception as exc:
            raise DraftCreationFailedError(request, exc, retry_count=1) from exc

        message  = response.get("message", {})
        metadata = DraftMetadata(
            gmail_draft_id=response["id"],
            gmail_message_id=message.get("id"),
            thread_id=message.get("threadId"),
            to=request.to, subject=request.subject,
            body_preview=request.body[:BODY_PREVIEW_LENGTH],
            candidate_name=request.candidate_name,
            company_name=request.company_name,
            variant_type=request.variant_type,
            expected_reply_rate=request.expected_reply_rate,
            status=DraftStatus.CREATED,
            created_at=datetime.utcnow(),
            retry_count=attempt_count - 1,
        )
        return await self._repo.insert(metadata)

    async def get_draft(self, gmail_draft_id: str) -> DraftMetadataRow | None:
        return await self._repo.get_by_gmail_draft_id(gmail_draft_id)

    async def list_drafts_for_company(self, company_name: str) -> list[DraftMetadataRow]:
        return await self._repo.list_by_company(company_name)

    async def list_drafts_by_status(self, status: DraftStatus) -> list[DraftMetadataRow]:
        return await self._repo.list_by_status(status)
