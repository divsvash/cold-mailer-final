# Configuration

Copy `.env.example` to `.env` in the repository root. Do not commit secrets or OAuth tokens.

Precedence is an explicit function/CLI argument, then a process environment variable,
then the root `.env`, then the default. Settings are loaded when an operation starts.
Relative file paths and SQLite URLs are resolved from the repository root, including
when a command is invoked from another directory. Parent directories for SQLite
files are created when a database engine is opened, not when settings are read.

- `ANTHROPIC_API_KEY`, `LLM_MODEL`: used by candidate extraction, JD analysis and
  email generation. Providing a mock client avoids constructing a real API client.
- `EMAIL_MAX_WORDS`: generation prompt, validation and the variant limit property.
- `DATABASE_URL`: draft metadata and job storage share this default database.
  An explicit in-memory SQLite URL remains in memory.
- `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`: OAuth files used by the draft script
  and Gmail helper. The helper only starts OAuth if no valid token is available.
- `PROFILE_PATH`, `RESUME_PATH`, `PROJECTS_PATH`, `ACHIEVEMENTS_PATH`,
  `PERSONALITY_PATH`: defaults for the corresponding source and CLI inputs.
- `GREENHOUSE_COMPANIES`, `LEVER_COMPANIES`: JSON arrays, for example `["acme"]`.
- `INCLUDE_YC_JOBS`, `MAX_CONCURRENT_SCRAPERS`: discovery defaults.

`send_emails.py --dry-run` still calls the configured model but does not create a
Gmail draft. Offline tests mock model and OAuth clients; they do not authenticate
or spend API credits. Never use the bundled profile as verified personal data.

The Gmail `gmail.compose` scope permits sending as well as draft management.
Draft-only behavior is an application restriction, not an OAuth guarantee.

This change wires configuration only. It does not add the discovery-to-draft
orchestrator, contact discovery, or a full pipeline test.
