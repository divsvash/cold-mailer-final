"""Shared settings. Environment overrides .env; explicit call arguments win.

Relative paths (including SQLite file paths) are relative to this repository,
not to the caller's working directory. Reading settings never creates files.
"""
from __future__ import annotations
import pathlib
import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ROOT_DIR = pathlib.Path(__file__).resolve().parent
MEMORY_DIR = ROOT_DIR / "memory"
PROMPTS_DIR = ROOT_DIR / "prompts"
JOBS_DIR = ROOT_DIR / "jobs"
DATABASE_DIR = ROOT_DIR / "database"
PROFILE_JSON = MEMORY_DIR / "profile.json"
RESUME_PDF = MEMORY_DIR / "resume.pdf"
PERSONALITY_MD = PROMPTS_DIR / "personality.md"
STYLE_EXAMPLES_DIR = MEMORY_DIR / "style_examples"
JOBS_RAW_DIR = JOBS_DIR / "raw"
JOBS_NORMALIZED_DIR = JOBS_DIR / "normalized"


def resolve_path(value: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(value).expanduser()
    return path if path.is_absolute() else ROOT_DIR / path


def resolve_database_url(value: str) -> str:
    url = make_url(value)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return value
    url = url.set(database=str(resolve_path(url.database)))
    return url.render_as_string(hide_password=False)


def prepare_database_url(value: str) -> str:
    """Create a SQLite parent only when opening a database, not on import."""
    value = resolve_database_url(value)
    url = make_url(value)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        from security import private_directory, restrict_private_file
        path = pathlib.Path(url.database)
        private_directory(path.parent)
        restrict_private_file(path)
        # Precreate SQLite privately before the driver opens it.
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")
    ANTHROPIC_API_KEY: str = Field(default="", repr=False)
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///database/career_agent.db", repr=False)
    GMAIL_CREDENTIALS_PATH: pathlib.Path = ROOT_DIR / "credentials.json"
    GMAIL_TOKEN_PATH: pathlib.Path = ROOT_DIR / "token.json"
    PROFILE_PATH: pathlib.Path = ROOT_DIR / "private" / "profile.json"
    RESUME_PATH: pathlib.Path = RESUME_PDF
    PROJECTS_PATH: pathlib.Path = MEMORY_DIR / "projects.md"
    ACHIEVEMENTS_PATH: pathlib.Path = MEMORY_DIR / "achievements.md"
    PERSONALITY_PATH: pathlib.Path = PERSONALITY_MD
    GREENHOUSE_COMPANIES: list[str] = Field(default_factory=list)
    LEVER_COMPANIES: list[str] = Field(default_factory=list)
    INCLUDE_YC_JOBS: bool = True
    MAX_CONCURRENT_SCRAPERS: int = Field(default=3, ge=1)
    EMAIL_MAX_WORDS: int = Field(default=150, ge=1)

    @field_validator("GMAIL_CREDENTIALS_PATH", "GMAIL_TOKEN_PATH", "PROFILE_PATH", "RESUME_PATH", "PROJECTS_PATH", "ACHIEVEMENTS_PATH", "PERSONALITY_PATH", mode="after")
    @classmethod
    def repository_paths(cls, value: pathlib.Path) -> pathlib.Path:
        return resolve_path(value)

    @field_validator("DATABASE_URL")
    @classmethod
    def database_path(cls, value: str) -> str:
        return resolve_database_url(value)


def get_settings() -> Settings:
    """Load at the operation boundary so callers/tests can change environment."""
    return Settings()


class ModelSetupError(ValueError):
    """A local configuration problem, safe to show without secret values."""


def require_model_key() -> str:
    key = get_settings().ANTHROPIC_API_KEY.strip()
    if not key or key == "your_anthropic_api_key_here":
        raise ModelSetupError("Model API key missing. Set ANTHROPIC_API_KEY in the repository .env or environment.")
    return key
