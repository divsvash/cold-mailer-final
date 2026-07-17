"""Unit tests for job_analyzer engine with mocked Anthropic client."""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from agents.job_analyzer.engine import TOOL_NAME, JobUnderstandingEngine
from agents.job_analyzer.schemas import Domain, JobUnderstanding, SeniorityLevel
from tests.job_analyzer.fixtures import INVALID_DOMAIN_INPUT, MISSING_SENIORITY_INPUT, SENIOR_BACKEND_JD, VALID_JU_INPUT


def _make_client(tool_input: dict, tool_name: str = TOOL_NAME) -> MagicMock:
    block   = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id="t1")
    message = SimpleNamespace(content=[block], stop_reason="tool_use")
    client  = MagicMock()
    client.messages.create.return_value = message
    return client


def _make_text_client(text: str = "Sorry.") -> MagicMock:
    block   = SimpleNamespace(type="text", text=text)
    message = SimpleNamespace(content=[block], stop_reason="end_turn")
    client  = MagicMock()
    client.messages.create.return_value = message
    return client


class TestEngineHappyPath:
    def test_returns_valid_response(self):
        client = _make_client(VALID_JU_INPUT)
        result = JobUnderstandingEngine(client=client).analyze(SENIOR_BACKEND_JD)
        assert result.result.domain == Domain.FINTECH
        assert result.result.seniority == SeniorityLevel.SENIOR

    def test_model_name_propagated(self):
        client = _make_client(VALID_JU_INPUT)
        result = JobUnderstandingEngine(model="claude-opus-4-6", client=client).analyze(SENIOR_BACKEND_JD)
        assert result.model == "claude-opus-4-6"
        assert client.messages.create.call_args.kwargs["model"] == "claude-opus-4-6"

    def test_tool_choice_forced(self):
        client = _make_client(VALID_JU_INPUT)
        JobUnderstandingEngine(client=client).analyze(SENIOR_BACKEND_JD)
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["tool_choice"] == {"type": "tool", "name": TOOL_NAME}

    def test_jd_passed_in_message(self):
        client = _make_client(VALID_JU_INPUT)
        JobUnderstandingEngine(client=client).analyze(SENIOR_BACKEND_JD)
        content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "Senior Backend Engineer" in content


class TestEngineErrorPaths:
    def test_no_tool_use_block_raises(self):
        with pytest.raises(ValueError, match="did not return a tool_use block"):
            JobUnderstandingEngine(client=_make_text_client()).analyze(SENIOR_BACKEND_JD)

    def test_wrong_tool_name_raises(self):
        client = _make_client(VALID_JU_INPUT, tool_name="wrong_tool")
        with pytest.raises(ValueError, match="unexpected tool"):
            JobUnderstandingEngine(client=client).analyze(SENIOR_BACKEND_JD)

    def test_invalid_domain_raises(self):
        client = _make_client(INVALID_DOMAIN_INPUT)
        with pytest.raises(ValueError, match="validation"):
            JobUnderstandingEngine(client=client).analyze(SENIOR_BACKEND_JD)

    def test_missing_field_raises(self):
        client = _make_client(MISSING_SENIORITY_INPUT)
        with pytest.raises(ValueError, match="validation"):
            JobUnderstandingEngine(client=client).analyze(SENIOR_BACKEND_JD)

    def test_too_short_jd_rejected_before_api_call(self):
        client = _make_client(VALID_JU_INPUT)
        with pytest.raises(Exception):
            JobUnderstandingEngine(client=client).analyze("too short")
        client.messages.create.assert_not_called()
