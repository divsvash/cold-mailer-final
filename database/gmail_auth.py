"""Gmail OAuth helper. compose permits sending; callers use draft creation only."""
from __future__ import annotations
import pathlib
from config import get_settings, resolve_path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.compose permits draft management AND sending. Draft-only is a code policy.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def get_gmail_service(credentials_path: str | pathlib.Path | None = None, token_path: str | pathlib.Path | None = None):
    """Build authenticated Gmail service. Opens browser on first run."""
    settings = get_settings()
    credentials_path = resolve_path(credentials_path) if credentials_path is not None else settings.GMAIL_CREDENTIALS_PATH
    token_file = resolve_path(token_path) if token_path is not None else settings.GMAIL_TOKEN_PATH
    creds: Credentials | None = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)
