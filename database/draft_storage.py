"""SQLAlchemy storage for Gmail draft metadata."""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import DateTime, Float, Index, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from database.draft_models import DraftMetadata, DraftStatus


class Base(DeclarativeBase):
    pass


class DraftMetadataRow(Base):
    __tablename__ = "draft_metadata"
    id:               Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    gmail_draft_id:   Mapped[str]       = mapped_column(String(128), unique=True, nullable=False, index=True)
    gmail_message_id: Mapped[str | None]= mapped_column(String(128), nullable=True)
    thread_id:        Mapped[str | None]= mapped_column(String(128), nullable=True)
    to:               Mapped[str]       = mapped_column(String(320), nullable=False, index=True)
    subject:          Mapped[str]       = mapped_column(String(200), nullable=False)
    body_preview:     Mapped[str]       = mapped_column(String(500), nullable=False)
    candidate_name:   Mapped[str | None]= mapped_column(String(255), nullable=True)
    company_name:     Mapped[str | None]= mapped_column(String(255), nullable=True, index=True)
    variant_type:     Mapped[str | None]= mapped_column(String(50),  nullable=True)
    expected_reply_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    status:           Mapped[str]       = mapped_column(String(20),  nullable=False, default="created")
    created_at:       Mapped[datetime]  = mapped_column(DateTime,    nullable=False)
    retry_count:      Mapped[int]       = mapped_column(Integer,     nullable=False, default=0)
    __table_args__ = (Index("ix_draft_status", "status"), Index("ix_draft_created_at", "created_at"),)


class DraftMetadataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, draft: DraftMetadata) -> DraftMetadataRow:
        row = DraftMetadataRow(
            gmail_draft_id=draft.gmail_draft_id, gmail_message_id=draft.gmail_message_id,
            thread_id=draft.thread_id, to=draft.to, subject=draft.subject,
            body_preview=draft.body_preview, candidate_name=draft.candidate_name,
            company_name=draft.company_name, variant_type=draft.variant_type,
            expected_reply_rate=draft.expected_reply_rate,
            status=draft.status.value, created_at=draft.created_at, retry_count=draft.retry_count,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_by_gmail_draft_id(self, gmail_draft_id: str) -> DraftMetadataRow | None:
        stmt = select(DraftMetadataRow).where(DraftMetadataRow.gmail_draft_id == gmail_draft_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, id: int) -> DraftMetadataRow | None:
        return await self._session.get(DraftMetadataRow, id)

    async def list_by_status(self, status: DraftStatus, limit: int = 100) -> list[DraftMetadataRow]:
        stmt = select(DraftMetadataRow).where(DraftMetadataRow.status == status.value).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_by_company(self, company_name: str, limit: int = 100) -> list[DraftMetadataRow]:
        stmt = select(DraftMetadataRow).where(DraftMetadataRow.company_name == company_name).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count(self) -> int:
        return len((await self._session.execute(select(DraftMetadataRow))).scalars().all())

    async def update_status(self, gmail_draft_id: str, status: DraftStatus) -> bool:
        row = await self.get_by_gmail_draft_id(gmail_draft_id)
        if row is None:
            return False
        row.status = status.value
        await self._session.flush()
        return True


def make_engine(url: str = "sqlite+aiosqlite:///database/career_agent.db"):
    return create_async_engine(url, echo=False)

async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
