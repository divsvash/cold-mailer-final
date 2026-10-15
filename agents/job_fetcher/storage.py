"""SQLAlchemy storage for raw and normalized job records."""
from __future__ import annotations
import json
from config import get_settings, prepare_database_url
from datetime import datetime
from sqlalchemy import Column, DateTime, Index, String, Text, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from agents.job_fetcher.models import JobSource, NormalizedJob, RawJob


class Base(DeclarativeBase):
    pass


class RawJobRow(Base):
    __tablename__ = "raw_jobs"
    source:      Mapped[str] = mapped_column(String(32),  primary_key=True)
    source_id:   Mapped[str] = mapped_column(String(256), primary_key=True)
    raw_html:    Mapped[str] = mapped_column(Text,        nullable=False)
    fetched_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_meta: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (Index("ix_raw_jobs_source", "source"),)


class NormalizedJobRow(Base):
    __tablename__ = "normalized_jobs"
    dedup_key:   Mapped[str] = mapped_column(String(64),   primary_key=True)
    title:       Mapped[str] = mapped_column(String(512),  nullable=False, index=True)
    company:     Mapped[str] = mapped_column(String(256),  nullable=False, index=True)
    location:    Mapped[str | None] = mapped_column(String(256), nullable=True)
    url:         Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str] = mapped_column(Text,         nullable=False)
    posted_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source:      Mapped[str] = mapped_column(String(32),   nullable=False, index=True)
    source_id:   Mapped[str] = mapped_column(String(256),  nullable=False)
    first_seen:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen:   Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_normalized_jobs_posted_at", "posted_at"),)


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_raw(self, raw: RawJob) -> bool:
        existing = await self._session.get(RawJobRow, (raw.source.value, raw.source_id))
        if existing is not None:
            return False
        row = RawJobRow(
            source=raw.source.value, source_id=raw.source_id, raw_html=raw.raw_html,
            fetched_at=raw.fetched_at, source_meta=json.dumps(raw.source_metadata),
        )
        self._session.add(row)
        return True

    async def upsert_normalized(self, job: NormalizedJob) -> bool:
        existing = await self._session.get(NormalizedJobRow, job.dedup_key)
        now = datetime.utcnow()
        if existing is not None:
            existing.last_seen = now
            return False
        row = NormalizedJobRow(
            dedup_key=job.dedup_key, title=job.title, company=job.company,
            location=job.location, url=job.url, description=job.description,
            posted_at=job.posted_at, source=job.source.value, source_id=job.source_id,
            first_seen=now, last_seen=now,
        )
        self._session.add(row)
        return True

    async def list_normalized(self, limit: int = 100) -> list[NormalizedJobRow]:
        stmt = select(NormalizedJobRow).limit(limit).order_by(NormalizedJobRow.first_seen.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_normalized(self) -> int:
        result = await self._session.execute(select(NormalizedJobRow))
        return len(result.scalars().all())


def make_engine(url: str | None = None):
    return create_async_engine(prepare_database_url(url if url is not None else get_settings().DATABASE_URL), echo=False)

async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
