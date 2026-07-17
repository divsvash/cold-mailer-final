"""Unit tests for GmailDraftClient — retry logic, never-send guarantee."""
from __future__ import annotations
import base64
from email import message_from_bytes
from unittest.mock import MagicMock
import pytest
from googleapiclient.errors import HttpError
from database.gmail_client import (
    GmailDraftClient, _is_retryable, build_mime_message,
)
from tests.gmail_integration.fixtures import (
    AUTH_ERROR, BAD_REQUEST_ERROR, FORBIDDEN_ERROR, GMAIL_SUCCESS_RESPONSE,
    NOT_FOUND_ERROR, RATE_LIMIT_ERROR, SERVER_ERROR_500, SERVER_ERROR_503,
)


def _make_service(side_effects=None, return_value=None):
    mock_execute = MagicMock()
    if side_effects is not None:
        mock_execute.side_effect = side_effects
    else:
        mock_execute.return_value = return_value
    mock_create = MagicMock()
    mock_create.return_value.execute = mock_execute
    mock_drafts = MagicMock()
    mock_drafts.create = mock_create
    mock_users = MagicMock()
    mock_users.drafts.return_value = mock_drafts
    mock_service = MagicMock()
    mock_service.users.return_value = mock_users
    return mock_service, mock_create


class TestBuildMimeMessage:
    def test_returns_base64url(self):
        raw = build_mime_message("test@example.com", "Subject", "Body")
        decoded = base64.urlsafe_b64decode(raw)
        assert b"Body" in decoded

    def test_includes_to_header(self):
        raw = build_mime_message("test@example.com", "Subject", "Body")
        msg = message_from_bytes(base64.urlsafe_b64decode(raw))
        assert msg["to"] == "test@example.com"

    def test_includes_subject(self):
        raw = build_mime_message("test@example.com", "Hello World", "Body")
        msg = message_from_bytes(base64.urlsafe_b64decode(raw))
        assert msg["subject"] == "Hello World"

    def test_includes_body(self):
        raw = build_mime_message("test@example.com", "S", "Specific body content here")
        msg = message_from_bytes(base64.urlsafe_b64decode(raw))
        assert "Specific body content here" in msg.get_payload(decode=True).decode()


class TestIsRetryable:
    def test_429_retryable(self):   assert _is_retryable(RATE_LIMIT_ERROR) is True
    def test_500_retryable(self):   assert _is_retryable(SERVER_ERROR_500)  is True
    def test_503_retryable(self):   assert _is_retryable(SERVER_ERROR_503)  is True
    def test_400_not_retryable(self): assert _is_retryable(BAD_REQUEST_ERROR) is False
    def test_401_not_retryable(self): assert _is_retryable(AUTH_ERROR)        is False
    def test_403_not_retryable(self): assert _is_retryable(FORBIDDEN_ERROR)   is False
    def test_404_not_retryable(self): assert _is_retryable(NOT_FOUND_ERROR)   is False
    def test_non_http_not_retryable(self): assert _is_retryable(ValueError("x")) is False


class TestCreateDraftHappyPath:
    def test_returns_response_and_attempt_count(self):
        service, _ = _make_service(return_value=GMAIL_SUCCESS_RESPONSE)
        response, attempts = GmailDraftClient(service, wait_min=0, wait_max=0).create_draft(
            "test@example.com", "Subject", "Body"
        )
        assert response == GMAIL_SUCCESS_RESPONSE and attempts == 1

    def test_calls_drafts_create_not_send(self):
        service, mock_create = _make_service(return_value=GMAIL_SUCCESS_RESPONSE)
        GmailDraftClient(service, wait_min=0, wait_max=0).create_draft("t@e.com", "S", "B")
        mock_create.assert_called_once()
        assert not service.users.return_value.drafts.return_value.send.called

    def test_userid_is_me(self):
        service, mock_create = _make_service(return_value=GMAIL_SUCCESS_RESPONSE)
        GmailDraftClient(service, wait_min=0, wait_max=0).create_draft("t@e.com", "S", "B")
        assert mock_create.call_args.kwargs["userId"] == "me"

    def test_body_contains_raw_message(self):
        service, mock_create = _make_service(return_value=GMAIL_SUCCESS_RESPONSE)
        GmailDraftClient(service, wait_min=0, wait_max=0).create_draft("t@e.com", "S", "Hello body")
        raw = mock_create.call_args.kwargs["body"]["message"]["raw"]
        decoded = base64.urlsafe_b64decode(raw)
        assert b"Hello body" in decoded


class TestRetryLogic:
    def test_retries_on_429_then_succeeds(self):
        service, mock_create = _make_service(
            side_effects=[RATE_LIMIT_ERROR, GMAIL_SUCCESS_RESPONSE]
        )
        response, attempts = GmailDraftClient(service, max_attempts=3, wait_min=0, wait_max=0).create_draft(
            "t@e.com", "S", "B"
        )
        assert response == GMAIL_SUCCESS_RESPONSE and attempts == 2

    def test_retries_on_503_then_succeeds(self):
        service, mock_create = _make_service(
            side_effects=[SERVER_ERROR_503, GMAIL_SUCCESS_RESPONSE]
        )
        response, attempts = GmailDraftClient(service, max_attempts=3, wait_min=0, wait_max=0).create_draft(
            "t@e.com", "S", "B"
        )
        assert attempts == 2

    def test_gives_up_after_max_attempts(self):
        service, mock_create = _make_service(
            side_effects=[RATE_LIMIT_ERROR, RATE_LIMIT_ERROR, RATE_LIMIT_ERROR]
        )
        with pytest.raises(HttpError) as exc_info:
            GmailDraftClient(service, max_attempts=3, wait_min=0, wait_max=0).create_draft(
                "t@e.com", "S", "B"
            )
        assert exc_info.value.resp.status == 429
        assert mock_create.return_value.execute.call_count == 3

    def test_exhausted_retries_sets_retry_attempts(self):
        service, _ = _make_service(
            side_effects=[RATE_LIMIT_ERROR, RATE_LIMIT_ERROR, RATE_LIMIT_ERROR]
        )
        with pytest.raises(HttpError) as exc_info:
            GmailDraftClient(service, max_attempts=3, wait_min=0, wait_max=0).create_draft(
                "t@e.com", "S", "B"
            )
        assert exc_info.value.retry_attempts == 3


class TestNonRetryableErrors:
    def test_400_no_retry(self):
        service, mock_create = _make_service(side_effects=[BAD_REQUEST_ERROR])
        with pytest.raises(HttpError):
            GmailDraftClient(service, max_attempts=3, wait_min=0, wait_max=0).create_draft(
                "t@e.com", "S", "B"
            )
        assert mock_create.return_value.execute.call_count == 1

    def test_401_no_retry(self):
        service, mock_create = _make_service(side_effects=[AUTH_ERROR])
        with pytest.raises(HttpError):
            GmailDraftClient(service, max_attempts=3, wait_min=0, wait_max=0).create_draft(
                "t@e.com", "S", "B"
            )
        assert mock_create.return_value.execute.call_count == 1

    def test_max_attempts_1_means_no_retry(self):
        service, mock_create = _make_service(
            side_effects=[RATE_LIMIT_ERROR, GMAIL_SUCCESS_RESPONSE]
        )
        with pytest.raises(HttpError):
            GmailDraftClient(service, max_attempts=1, wait_min=0, wait_max=0).create_draft(
                "t@e.com", "S", "B"
            )
        assert mock_create.return_value.execute.call_count == 1


class TestConfigurableMaxAttempts:
    def test_default_is_3(self):
        assert GmailDraftClient(MagicMock())._max_attempts == 3

    def test_custom_max_respected(self):
        service, mock_create = _make_service(
            side_effects=[RATE_LIMIT_ERROR] * 5
        )
        with pytest.raises(HttpError):
            GmailDraftClient(service, max_attempts=5, wait_min=0, wait_max=0).create_draft(
                "t@e.com", "S", "B"
            )
        assert mock_create.return_value.execute.call_count == 5
