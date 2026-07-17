"""Shared configuration for all career-agent components."""
from __future__ import annotations
import pathlib
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR            = pathlib.Path(__file__).parent
MEMORY_DIR          = ROOT_DIR / "memory"
PROMPTS_DIR         = ROOT_DIR / "prompts"
JOBS_DIR            = ROOT_DIR / "jobs"
DATABASE_DIR        = ROOT_DIR / "database"
PROFILE_JSON        = MEMORY_DIR / "profile.json"
RESUME_PDF          = MEMORY_DIR / "resume.pdf"
PERSONALITY_MD      = PROMPTS_DIR / "personality.md"
STYLE_EXAMPLES_DIR  = MEMORY_DIR / "style_examples"
JOBS_RAW_DIR        = JOBS_DIR / "raw"
JOBS_NORMALIZED_DIR = JOBS_DIR / "normalized"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    ANTHROPIC_API_KEY:       str       = ""
    LLM_MODEL:               str       = "claude-sonnet-4-20250514"
    DATABASE_URL:            str       = f"sqlite+aiosqlite:///{DATABASE_DIR}/career_agent.db"
    GMAIL_CREDENTIALS_PATH:  str       = str(ROOT_DIR / "credentials.json")
    GMAIL_TOKEN_PATH:        str       = str(ROOT_DIR / "token.json")
    GREENHOUSE_COMPANIES:    list[str] = []
    LEVER_COMPANIES:         list[str] = []
    INCLUDE_YC_JOBS:         bool      = True
    MAX_CONCURRENT_SCRAPERS: int       = 3
    EMAIL_MAX_WORDS:         int       = 150


settings = Settings()
