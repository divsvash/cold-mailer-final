"""Gmail OAuth2 helper — gmail.compose scope only (cannot send)."""
from __future__ import annotations
import pathlib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.compose: create/edit/delete drafts. Does NOT include gmail.send.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def get_gmail_service(credentials_path: str = "credentials.json", token_path: str = "token.json"):
    """Build authenticated Gmail service. Opens browser on first run."""
    creds: Credentials | None = None
    token_file = pathlib.Path(token_path)

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)
