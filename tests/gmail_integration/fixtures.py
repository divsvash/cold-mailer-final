"""Fixtures for gmail_integration tests."""
import httplib2
from googleapiclient.errors import HttpError

DRAFT_REQUEST_BASIC: dict = {
    "to": "priya@luminaai.com",
    "subject": "Backend Engineer @ Lumina AI",
    "body": "Hi Priya,\n\nSaw Lumina AI's open-source fine-tuning framework launch.\n\nBest,\nDivyansh",
}

DRAFT_REQUEST_WITH_METADATA: dict = {
    **DRAFT_REQUEST_BASIC,
    "candidate_name": "Divyansh Sharma",
    "company_name": "Lumina AI",
    "variant_type": "technical",
    "expected_reply_rate": 0.41,
}

DRAFT_REQUEST_LONG_BODY: dict = {
    "to": "hiring@acme.com",
    "subject": "Application",
    "body": "word " * 200,
    "company_name": "Acme",
}

GMAIL_SUCCESS_RESPONSE: dict = {
    "id": "r-1234567890",
    "message": {
        "id": "msg-abcdef123456",
        "threadId": "thread-abcdef123456",
        "labelIds": ["DRAFT"],
    },
}

GMAIL_SUCCESS_RESPONSE_2: dict = {
    "id": "r-9999999999",
    "message": {"id": "msg-999999", "threadId": "thread-999999", "labelIds": ["DRAFT"]},
}

GMAIL_MINIMAL_RESPONSE: dict = {
    "id": "r-minimal",
    "message": {"id": "msg-minimal"},
}


def make_http_error(status: int, reason: str = "error") -> HttpError:
    resp = httplib2.Response({"status": str(status)})
    resp.reason = reason
    content = f'{{"error": {{"code": {status}, "message": "{reason}"}}}}'.encode()
    return HttpError(resp, content)


RATE_LIMIT_ERROR  = make_http_error(429, "Rate Limit Exceeded")
SERVER_ERROR_500  = make_http_error(500, "Internal Server Error")
SERVER_ERROR_503  = make_http_error(503, "Service Unavailable")
BAD_REQUEST_ERROR = make_http_error(400, "Bad Request")
AUTH_ERROR        = make_http_error(401, "Unauthorized")
FORBIDDEN_ERROR   = make_http_error(403, "Forbidden")
NOT_FOUND_ERROR   = make_http_error(404, "Not Found")
