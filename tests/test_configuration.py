"""Offline regression tests for configuration consumers. No OAuth/model calls."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import asyncio
import json
import pytest
import config
from config import ROOT_DIR, Settings


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("External network access is forbidden in config tests")
    monkeypatch.setattr(socket.socket, "connect", denied)


def test_environment_beats_dotenv_and_relative_paths_use_repo(tmp_path, monkeypatch):
    env = tmp_path / "test.env"
    env.write_text('LLM_MODEL=file-model\nPROFILE_PATH=inputs/profile.json\nDATABASE_URL=sqlite+aiosqlite:///state/jobs.db\nGREENHOUSE_COMPANIES=["acme"]\n')
    monkeypatch.setenv("LLM_MODEL", "environment-model")
    monkeypatch.chdir(tmp_path)
    s = Settings(_env_file=env)
    assert s.LLM_MODEL == "environment-model"
    assert s.PROFILE_PATH == ROOT_DIR / "inputs/profile.json"
    assert s.DATABASE_URL == f"sqlite+aiosqlite:///{ROOT_DIR}/state/jobs.db"
    assert s.GREENHOUSE_COMPANIES == ["acme"]


@pytest.mark.parametrize("values", [{"MAX_CONCURRENT_SCRAPERS": 0}, {"EMAIL_MAX_WORDS": 0}])
def test_invalid_positive_settings_fail(values):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values)


def test_secret_not_in_settings_repr():
    assert "test-secret" not in repr(Settings(_env_file=None, ANTHROPIC_API_KEY="test-secret"))


def test_explicit_models_override_config_and_clients_receive_key(monkeypatch):
    from agents.job_analyzer.engine import JobUnderstandingEngine
    from agents.email_generator.engine import EmailGenerationEngine
    monkeypatch.setenv("LLM_MODEL", "configured-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-test-key")
    with patch("anthropic.Anthropic") as client:
        assert JobUnderstandingEngine()._model == "configured-model"
        assert EmailGenerationEngine()._model == "configured-model"
        assert JobUnderstandingEngine(model="explicit")._model == "explicit"
        assert EmailGenerationEngine(model="explicit")._model == "explicit"
        assert client.call_args.kwargs["api_key"] == "offline-test-key"


def test_configured_word_limit(monkeypatch):
    from agents.email_generator.engine import EmailGenerationEngine
    from agents.email_generator.schemas import EmailVariant, VariantType
    monkeypatch.setenv("EMAIL_MAX_WORDS", "2")
    v = EmailVariant(variant_type=VariantType.CONCISE, subject="Subject", body="one two three", word_count=3)
    assert not v.within_word_limit
    with pytest.raises(ValueError, match="2-word"):
        EmailGenerationEngine(client=MagicMock())._check_word_limits([v])


def test_discovery_defaults_and_explicit_override(monkeypatch):
    from agents.job_fetcher.service import DiscoveryConfig
    monkeypatch.setenv("GREENHOUSE_COMPANIES", '["alpha"]')
    monkeypatch.setenv("LEVER_COMPANIES", '["beta"]')
    monkeypatch.setenv("INCLUDE_YC_JOBS", "false")
    monkeypatch.setenv("MAX_CONCURRENT_SCRAPERS", "7")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    s = DiscoveryConfig()
    assert (s.greenhouse_companies, s.lever_companies, s.include_yc, s.concurrency, s.db_url) == (["alpha"], ["beta"], False, 7, "sqlite+aiosqlite:///:memory:")
    assert DiscoveryConfig(greenhouse_companies=[], include_yc=True, concurrency=2).greenhouse_companies == []
    s.greenhouse_companies.append("other")
    assert DiscoveryConfig().greenhouse_companies == ["alpha"]


def test_database_factories_honor_config_and_create_parents(tmp_path, monkeypatch):
    from database.draft_storage import make_engine as draft_engine
    from agents.job_fetcher.storage import make_engine as jobs_engine
    path = tmp_path / "nested" / "state.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    for factory in (draft_engine, jobs_engine):
        engine = factory()
        assert engine.url.database == str(path)
        assert path.parent.is_dir()
        asyncio.run(engine.dispose())
        memory = factory("sqlite+aiosqlite:///:memory:")
        assert memory.url.database == ":memory:"
        asyncio.run(memory.dispose())


def test_non_sqlite_url_unchanged():
    url = "postgresql+asyncpg://user:secret@localhost/app"
    assert config.resolve_database_url(url) == url


def test_gmail_configured_paths_with_valid_mock_token(tmp_path, monkeypatch):
    from database.gmail_auth import get_gmail_service
    token = tmp_path / "saved-token.json"
    token.write_text("{}")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token))
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", str(tmp_path / "oauth.json"))
    credential = MagicMock(valid=True)
    with patch("database.gmail_auth.Credentials.from_authorized_user_file", return_value=credential) as load, patch("database.gmail_auth.build", return_value="mock-service"), patch("database.gmail_auth.InstalledAppFlow") as oauth:
        assert get_gmail_service() == "mock-service"
        assert load.call_args.args[0] == str(token)
        oauth.assert_not_called()


def test_candidate_extractor_uses_configured_inputs_and_model(tmp_path, monkeypatch):
    from agents.candidate_analyzer.extractor import extract_profile
    for key, name in [("RESUME_PATH", "resume.pdf"), ("PROJECTS_PATH", "projects.md"), ("ACHIEVEMENTS_PATH", "achievements.md")]:
        monkeypatch.setenv(key, str(tmp_path / name))
    monkeypatch.setenv("LLM_MODEL", "configured-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-test-key")
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text=json.dumps({"full_name": "Test Candidate"}))])
    with patch("agents.candidate_analyzer.extractor.read_pdf", return_value="resume") as pdf, patch("agents.candidate_analyzer.extractor.read_md", return_value="notes") as md, patch("anthropic.Anthropic", return_value=client):
        assert extract_profile().full_name == "Test Candidate"
        assert pdf.call_args.args[0] == tmp_path / "resume.pdf"
        assert md.call_args.args[0] == tmp_path / "achievements.md"
        assert client.messages.create.call_args.kwargs["model"] == "configured-model"


def test_settings_no_import_side_effect_and_dotenv_key(tmp_path):
    env = tmp_path / "test.env"
    directory = tmp_path / "not-created"
    env.write_text(f"ANTHROPIC_API_KEY=offline-key\nDATABASE_URL=sqlite+aiosqlite:///{directory}/state.db\n")
    s = Settings(_env_file=env)
    assert s.ANTHROPIC_API_KEY == "offline-key"
    assert not directory.exists()


def test_send_cli_dry_run_uses_config_without_gmail(tmp_path, monkeypatch):
    import send_emails
    from agents.email_generator.schemas import VariantType
    profile = tmp_path / "profile.json"
    profile.write_text('{"full_name":"Test Candidate"}')
    personality = tmp_path / "voice.md"
    personality.write_text("Write plainly.")
    monkeypatch.setenv("PROFILE_PATH", str(profile))
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-key")
    monkeypatch.setattr("sys.argv", ["send_emails.py", "--to", "test@example.com", "--company", "Example", "--role", "Intern", "--dry-run"])
    variant = SimpleNamespace(variant_type=VariantType.CONCISE, subject="Subject", body="Body", word_count=1)
    result = SimpleNamespace(best_variant=variant, best_expected_reply_rate=0.1, rankings=[])
    with patch("agents.email_generator.engine.EmailGenerationEngine") as engine, patch("database.gmail_auth.get_gmail_service") as gmail:
        engine.return_value.generate.return_value = result
        asyncio.run(send_emails.main())
        assert engine.return_value.generate.call_args.args[0].full_name == "Test Candidate"
        assert engine.return_value.generate.call_args.args[3] == "Write plainly."
        gmail.assert_not_called()


def test_oauth_explicit_paths_override_config_without_live_auth(tmp_path, monkeypatch):
    from database.gmail_auth import get_gmail_service
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "ignored.json"))
    token = tmp_path / "nested" / "explicit.json"
    credential = MagicMock()
    credential.to_json.return_value = "{}"
    flow = MagicMock()
    flow.run_local_server.return_value = credential
    with patch("database.gmail_auth.InstalledAppFlow.from_client_secrets_file", return_value=flow) as load, patch("database.gmail_auth.build", return_value="service"):
        assert get_gmail_service(tmp_path / "explicit-credentials.json", token) == "service"
        assert load.call_args.args[0] == str(tmp_path / "explicit-credentials.json")
        assert token.read_text() == "{}"
