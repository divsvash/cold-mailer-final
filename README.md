# Cold Mailer

A local pipeline that turns stored job postings into reviewed cold-email
drafts for Gmail. It never sends email. Gmail draft creation happens only on
an explicit opt-in flag, and every recipient passes human review first.

## How the pieces fit

1. **Job fetching** (`agents/job_fetcher`): Greenhouse, Lever and YC scrapers
   normalize postings into a deduplicated private SQLite store. Run the
   discovery service separately to populate storage.
2. **Recipient discovery** (`agents/recipient_discovery`,
   `discover_recipients.py`): finds candidate hiring contacts quoted from real
   text (the posting itself or public company pages), stores them as
   `proposed`, and exports only the ones you approve. No model calls, no
   guessed addresses. See `docs/recipient-discovery.md`.
3. **Candidate + job analysis** (`agents/candidate_analyzer`,
   `agents/job_analyzer`, `agents/email_generator`): builds the candidate
   profile, extracts job requirements, and generates grounded email variants.
   The grounding guard rejects claims (proper nouns, numbers with units) that
   are not in your source material; it is lexical, not truth detection. See
   `docs/grounding-limits.md`.
4. **Orchestrator** (`orchestrator.py`, `run_pipeline.py`): stored jobs -> JD
   analysis -> deterministic fit scoring -> shortlist -> email variants ->
   preview report. Gmail drafts only with `--create-drafts`, guarded against
   duplicates by a committed reservation table. See `docs/orchestrator.md`.

`recruiter_simulator` scores candidate-job fit heuristically; its numbers are
estimates, not forecasts.

## Setup

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt   # hash-pinned; requirements.txt is the loose set
cp .env.example .env                    # fill in ANTHROPIC_API_KEY for model calls
python setup_check.py                   # verifies imports, files, credentials
```

Configuration precedence is CLI args > environment > `.env` > defaults.
See `docs/configuration.md`.

## Daily flow

```sh
# 1. populate job storage (library service; see agents/job_fetcher/service.py)

# 2. find candidate recipients (offline) or also fetch public pages
python discover_recipients.py scan
python discover_recipients.py scan --fetch-pages

# 3. review what it found, approve the good ones
python discover_recipients.py review
python discover_recipients.py approve --job <dedup_key> --email <address>
python discover_recipients.py export            # writes private/recipients.json

# 4. preview the outreach (no Gmail auth happens)
python run_pipeline.py --profile private/profile.json \
  --recipients private/recipients.json --output private/preview.json

# 5. only after reviewing the preview: create Gmail drafts
python run_pipeline.py --profile private/profile.json \
  --recipients private/recipients.json --create-drafts --output private/drafts.json
```

`send_emails.py` is the older manual script; the pipeline above does not
deduplicate drafts it created.

## Honest limits

- Tests run fully offline with injected fakes. Live model quality, Gmail
  OAuth/draft creation, and real scraper parsing are not exercised by the
  suite.
- The OAuth compose scope technically allows sending; draft-only behavior is
  a code restriction, not a Google-side one.
- Fit scores and reply-rate estimates are heuristics. Grounding checks are
  lexical. An email quoted from a page is not proof it is the right or a
  deliverable recipient. Human review remains the gate at every step.
- Reports, exports, the database, and OAuth tokens contain private data.
  Writes are owner-only and `private/`, `reports/`, `outputs/` are
  gitignored. See `docs/security.md`.

## Tests

```sh
python -m pytest tests
```
