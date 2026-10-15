# Cold Mailer

A Python tool for internship cold outreach. It finds job postings, matches them against your profile, and writes emails around the work you've actually done. You review the contacts and emails before anything goes into Gmail.

It creates drafts, not sent emails.

## What it does

- Fetches jobs from Greenhouse, Lever and YC, with duplicates removed in a local SQLite database.
- Builds a candidate profile from your resume, projects and achievements.
- Reads job descriptions, scores the fit and shortlists relevant roles.
- Finds email addresses in postings and public company pages. It keeps the source for each address and only uses contacts you approve. No guessed addresses.
- Generates technical, founder-focused and concise email variants using Claude, with checks against your source material.
- Previews the results locally, then optionally creates Gmail drafts with duplicate protection.

## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` in `.env`. You can also change the model, database path, company lists and email word limit there. Settings use CLI arguments first, then environment variables, then `.env`, then defaults.

Add your own resume, projects and achievements at the paths in `.env`, then build your profile:

```sh
python -m agents.candidate_analyzer.main --output private/profile.json
python setup_check.py
```

Check the generated profile before using it. The bundled profile is sample data, not something to send as your own. Edit `prompts/personality.md` to set the writing style.

## Run it

### Fetch jobs

Set `GREENHOUSE_COMPANIES` and `LEVER_COMPANIES` in `.env` as JSON arrays of company slugs. YC fetching is controlled by `INCLUDE_YC_JOBS`.

Job fetching currently runs through the Python service rather than a CLI:

```sh
python - <<'PY'
import asyncio
from agents.job_fetcher.service import DiscoveryConfig, JobDiscoveryService

report = asyncio.run(JobDiscoveryService(DiscoveryConfig()).run())
print(f"Stored {report.new_jobs} new jobs")
for error in report.errors:
    print(error)
PY
```

### Review contacts

Scan stored postings for addresses, then review the results:

```sh
python discover_recipients.py scan
python discover_recipients.py review
```

Use `scan --fetch-pages` to also check public pages linked from the postings. Approve a contact using the job key and address shown in the review, then export:

```sh
python discover_recipients.py approve --job <dedup_key> --email <address>
python discover_recipients.py export
```

The export goes to `private/recipients.json`. Finding an address doesn't verify who owns it or whether it's deliverable, so check the source before approving.

### Preview emails

```sh
python run_pipeline.py --profile private/profile.json \
  --recipients private/recipients.json --output private/preview.json
```

This analyzes stored jobs and generates email variants without Gmail authentication. It still makes paid model calls. By default, it considers the latest 100 jobs and selects up to 5 with a fit score of at least 0.6. Change these with `--job-limit`, `--max-selected` and `--min-fit`.

### Create Gmail drafts

For Gmail access, put your OAuth client credentials at `GMAIL_CREDENTIALS_PATH` (default: `credentials.json`). The first draft run opens a browser for authorization.

After reviewing the preview:

```sh
python run_pipeline.py --profile private/profile.json \
  --recipients private/recipients.json --create-drafts --output private/drafts.json
```

Repeat runs skip previously attempted drafts. If a report says `needs_reconciliation`, check Gmail before trying again. Drafts made by the older `send_emails.py` script aren't covered by this duplicate check.

Fit scores are estimates and the source checks aren't fact-checking. Read the emails before sending them yourself. Keep profiles, reports, tokens and contact exports out of git.

## Tests

```sh
python -m pytest tests
```

The tests use offline fakes, not live Claude, Gmail or scraper calls.

More detail: [configuration](docs/configuration.md), [pipeline](docs/orchestrator.md), [recipient discovery](docs/recipient-discovery.md), [source checks](docs/grounding-limits.md), [security](docs/security.md).
