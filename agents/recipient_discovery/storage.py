"""SQLAlchemy storage for reviewed contact candidates."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, Index, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from agents.recipient_discovery.models import ContactCandidate, ContactStatus


class Base(DeclarativeBase):
    pass


class ContactCandidateRow(Base):
    __tablename__ = "contact_candidates"
    job_dedup_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    email:         Mapped[str] = mapped_column(String(320), primary_key=True)
    name:          Mapped[str | None] = mapped_column(String(256), nullable=True)
    role:          Mapped[str | None] = mapped_column(String(256), nullable=True)
    source:        Mapped[str] = mapped_column(String(32), nullable=False)
    provenance:    Mapped[str] = mapped_column(String(2048), nullable=False)
    context:       Mapped[str] = mapped_column(Text, nullable=False, default="")
    status:        Mapped[str] = mapped_column(String(16), nullable=False,
                                               default=ContactStatus.PROPOSED.value)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                    default=datetime.utcnow)
    reviewed_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_contact_candidates_status", "status"),)


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_candidates(self, candidates: list[ContactCandidate]) -> int:
        """Store new proposals; an existing job+email pair is left untouched."""
        added = 0
        for candidate in candidates:
            existing = await self._session.get(
                ContactCandidateRow, (candidate.job_dedup_key, str(candidate.email)))
            if existing is not None:
                continue
            self._session.add(ContactCandidateRow(
                job_dedup_key=candidate.job_dedup_key, email=str(candidate.email),
                name=candidate.name, role=candidate.role,
                source=candidate.source.value, provenance=candidate.provenance,
                context=candidate.context, status=candidate.status.value,
                discovered_at=candidate.discovered_at,
            ))
            added += 1
        return added

    async def list_candidates(self, status: ContactStatus | None = None) -> list[ContactCandidateRow]:
        stmt = select(ContactCandidateRow).order_by(
            ContactCandidateRow.job_dedup_key, ContactCandidateRow.email)
        if status is not None:
            stmt = stmt.where(ContactCandidateRow.status == status.value)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_status(self, job_dedup_key: str, email: str,
                         status: ContactStatus) -> bool:
        row = await self._session.get(ContactCandidateRow, (job_dedup_key, email.lower()))
        if row is None:
            return False
        row.status = status.value
        row.reviewed_at = datetime.utcnow()
        return True

    async def approved_map(self) -> dict[str, dict[str, str]]:
        """Exactly the run_pipeline --recipients schema, approved contacts only."""
        rows = await self.list_candidates(ContactStatus.APPROVED)
        mapping: dict[str, dict[str, str]] = {}
        for row in rows:
            entry: dict[str, str] = {"email": row.email}
            if row.name:
                entry["name"] = row.name
            if row.role:
                entry["role"] = row.role
            mapping[row.job_dedup_key] = entry
        return mapping


async def init_contact_db(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
