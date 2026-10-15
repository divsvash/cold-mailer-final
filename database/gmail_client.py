"""Gmail API client — drafts.create only, with exponential backoff retry."""
from __future__ import annotations
import base64
from email.mime.text import MIMEText
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if not isinstance(exc, HttpError):
        return False
    return getattr(exc.resp, "status", None) in RETRYABLE_STATUS_CODES


def build_mime_message(to: str, subject: str, body: str) -> str:
    if any(c in to + subject for c in ("\r", "\n", "\x00")):
        raise ValueError("Email header contains prohibited control characters")
    from pydantic import TypeAdapter, EmailStr
    to = str(TypeAdapter(EmailStr).validate_python(to))
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


class GmailDraftClient:
    """Wraps users.drafts.create — never calls send."""

    def __init__(self, service, max_attempts: int = 3, wait_min: float = 1.0, wait_max: float = 10.0) -> None:
        self._service      = service
        self._max_attempts = max_attempts
        self._wait_min     = wait_min
        self._wait_max     = wait_max

    def create_draft(self, to: str, subject: str, body: str) -> tuple[dict, int]:
        """Returns (api_response_dict, attempt_count). Never sends."""
        raw_message = build_mime_message(to, subject, body)

        @retry(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=1, min=self._wait_min, max=self._wait_max),
            reraise=True,
        )
        def _do_create() -> dict:
            return (
                self._service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw_message}})
                .execute()
            )

        try:
            response = _do_create()
        except HttpError as exc:
            exc.retry_attempts = _do_create.statistics.get("attempt_number", 1)
            raise

        attempt_count = _do_create.statistics.get("attempt_number", 1)
        return response, attempt_count
