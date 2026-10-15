"""Regression cases reproduced in the functional audit. No live service calls."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from config import Settings, ModelSetupError
from agents.email_generator.engine import check_grounding
from agents.recruiter_simulator.schemas import CandidateProfile, JobRequirements
from agents.recruiter_simulator.scoring import assess


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('network forbidden'))


@pytest.mark.parametrize('claim', ['I increased revenue by 900 percent.', 'We reduced latency by 45%.',
    'Processed 900 records.', 'Handled $5 million.', 'Reduced latency to 9ms.'])
def test_unsupported_numeric_claims(claim):
    assert any('numeric' in item for item in check_grounding(claim, 'Candidate uses Python.'))


@pytest.mark.parametrize('claim,facts', [('900 percent', '900%'), ('1,000 records', '1000 records'),
    ('$5 million', '$5000000'), ('9 milliseconds', '9ms'), ('3 years', '3 year')])
def test_supported_equivalent_numbers(claim, facts):
    assert check_grounding(claim, facts) == []


def test_same_number_different_unit_is_not_support():
    assert check_grounding('Improved conversion 90%', 'Processed 90 records')


def test_grounding_still_checks_names():
    assert 'Sequoia' in check_grounding('Sequoia invested.', 'Python skills')


def test_no_requirements_is_zero_with_explicit_concern():
    result = assess(CandidateProfile(full_name='Example'), JobRequirements())
    assert result.fit_score == result.callback_probability == result.interview_probability == 0
    assert any(c.title == 'Insufficient job requirements' for c in result.concerns)


def test_project_names_not_truncated():
    candidate = CandidateProfile(full_name='Example', projects=[
        {'name': f'Ingestion worker {i}', 'description': 'Sample project', 'metrics': ['10 records']}
        for i in range(4)])
    result = assess(candidate, JobRequirements())
    detail = next(s.detail for s in result.strengths if s.title == 'Track record of quantified impact')
    assert 'Ingestion worker 0' in detail and 'Ingestion worker 2' in detail
    assert 'Ingestion worker 3' not in detail


@pytest.mark.parametrize('key', ['', '  ', 'your_anthropic_api_key_here'])
@pytest.mark.parametrize('module', ['agents.job_analyzer.engine', 'agents.email_generator.engine'])
def test_missing_key_fails_before_sdk(module, key, monkeypatch):
    import importlib
    monkeypatch.setenv('ANTHROPIC_API_KEY', key)
    sdk = MagicMock()
    monkeypatch.setattr('anthropic.Anthropic', sdk)
    cls = getattr(importlib.import_module(module), 'JobUnderstandingEngine' if 'job_analyzer' in module else 'EmailGenerationEngine')
    with pytest.raises(ModelSetupError, match='Set ANTHROPIC_API_KEY'):
        cls()
    sdk.assert_not_called()
    cls(client=MagicMock())  # Injected offline adapters need no credential.
    sdk.assert_not_called()


def test_extractor_clear_key_error(monkeypatch):
    from agents.candidate_analyzer.extractor import extract_profile
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    monkeypatch.setattr('agents.candidate_analyzer.extractor.read_pdf', lambda *a: 'resume')
    monkeypatch.setattr('agents.candidate_analyzer.extractor.read_md', lambda *a: 'notes')
    with pytest.raises(ModelSetupError, match='Set ANTHROPIC_API_KEY'):
        extract_profile()


def test_pipeline_cli_clear_setup_error(monkeypatch, capsys):
    import run_pipeline
    monkeypatch.setattr('sys.argv', ['run_pipeline', '--profile', 'profile.json', '--recipients', 'contacts.json'])
    async def fail(args):
        raise ModelSetupError('Model API key missing. Set ANTHROPIC_API_KEY in .env or environment.')
    monkeypatch.setattr(run_pipeline, 'run', fail)
    with pytest.raises(SystemExit, match='Set ANTHROPIC_API_KEY'):
        run_pipeline.main()


@pytest.mark.parametrize('missing', ['none', 'resume', 'projects', 'achievements', 'personality', 'credentials', 'token'])
def test_setup_check_real_imports_and_failures(tmp_path, monkeypatch, capsys, missing):
    import setup_check
    paths = {}
    for name in ['profile', 'resume', 'projects', 'achievements', 'personality', 'credentials', 'token']:
        path = tmp_path / name
        if name != missing:
            path.write_text(json.dumps({'full_name': 'Example'}) if name == 'profile' else 'fixture')
        paths[name] = path
    settings = Settings(_env_file=None, ANTHROPIC_API_KEY='offline-placeholder',
        PROFILE_PATH=paths['profile'], RESUME_PATH=paths['resume'], PROJECTS_PATH=paths['projects'],
        ACHIEVEMENTS_PATH=paths['achievements'], PERSONALITY_PATH=paths['personality'],
        GMAIL_CREDENTIALS_PATH=paths['credentials'], GMAIL_TOKEN_PATH=paths['token'])
    monkeypatch.setattr('config.get_settings', lambda: settings)
    status = setup_check.main()
    output = capsys.readouterr().out
    assert '✅  bs4' in output  # Actual bs4 import, not a mocked module alias.
    assert status == (0 if missing == 'none' else 1)
    assert ('Everything looks good' in output) == (missing == 'none')


def test_unsupported_subject_metric_blocks_generation():
    from agents.email_generator.engine import EmailGenerationEngine
    from agents.email_generator.schemas import EmailVariant
    engine = EmailGenerationEngine(client=MagicMock())
    variant = EmailVariant(variant_type='concise', subject='900% revenue growth',
                           body='Hi there', word_count=2)
    with pytest.raises(ValueError, match='numeric'):
        engine._check_all_grounding([variant], 'Candidate uses Python.')


def test_setup_script_failure_exit_code(tmp_path):
    import subprocess, sys, os
    env = dict(os.environ, ANTHROPIC_API_KEY='', PROFILE_PATH=str(tmp_path / 'missing-profile'))
    result = subprocess.run([sys.executable, 'setup_check.py'], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'Everything looks good' not in result.stdout
    assert '✅  bs4' in result.stdout
