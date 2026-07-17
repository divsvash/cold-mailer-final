"""Pydantic models for Gmail draft metadata."""
from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DraftStatus(StrEnum):
    CREATED = "created"
    FAILED  = "failed"
    SENT    = "sent"     # set only by external sync, never by this service
    DELETED = "deleted"  # set only by external sync


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to:      EmailStr
    subject: str   = Field(..., min_length=1, max_length=200)
    body:    str   = Field(..., min_length=1)
    candidate_name:      str | None = None
    company_name:        str | None = None
    variant_type:        str | None = None
    expected_reply_rate: float | None = Field(None, ge=0.0, le=1.0)


class DraftMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id:               int | None = None
    gmail_draft_id:   str
    gmail_message_id: str | None = None
    thread_id:        str | None = None
    to:           str
    subject:      str
    body_preview: str = Field(..., max_length=500)
    candidate_name:      str | None = None
    company_name:        str | None = None
    variant_type:        str | None = None
    expected_reply_rate: float | None = None
    status:      DraftStatus = DraftStatus.CREATED
    created_at:  datetime
    retry_count: int = Field(0, ge=0)


class DraftCreationError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to:            str
    subject:       str
    error_message: str
    retry_count:   int = Field(..., ge=0)
    occurred_at:   datetime
