# Stored-job pipeline (piece 2)

`run_pipeline.py` connects stored normalized jobs to JD analysis, deterministic
recruiter scoring, a score-filtered shortlist, three email variants, and optionally
Gmail draft creation. It never sends email. It does not scrape new jobs or discover
contacts. Run the existing discovery service separately to populate storage.

The default is preview mode. Both preview and draft mode make paid model calls
when using real adapters. Tests inject fakes and forbid network/authentication.
No live model or Gmail execution has been used to validate this change.

## Explicit inputs

Supply reviewed candidate JSON and a contact map. Do not use the bundled profile
as verified personal data. The profile schema is the existing email-generator
CandidateProfile schema. Job keys are `normalized_jobs.dedup_key` from storage.
Contacts are bound to exact jobs, not guessed from a company name or email domain.

Example contact map using a deliberately fake key/address:

```json
{
  "exact-dedup-key-from-your-stored-job": {
    "email": "hiring@example.com",
    "name": "Reviewed recipient name",
    "role": "Reviewed recipient role"
  }
}
```

```sh
python run_pipeline.py --profile reviewed-profile.json --recipients reviewed-contacts.json --output preview.json
```

Configured model, database, Gmail file paths and personality guide come from the
shared settings. CLI `--database` and `--personality` override their defaults.
`--min-fit` defaults to 0.6, `--max-selected` to 5, and `--job-limit` to 100.
Only the most recently stored jobs up to that limit are considered. Jobs without
contacts are reported and skipped. Jobs with no extracted skills are not assigned
a misleading perfect score. Eligible jobs sort by fit descending, then dedup key
for stable tie-breaking. Only the selected jobs incur email-generation calls.
A failure in one job does not abort the other jobs. Reports include status, score,
variants, selected recipient/text, and draft ID when available. Reports are local
JSON and contain private email text and contacts: do not commit or share them.
Scores and reply-rate estimates are heuristics/model estimates, not forecasts.

## Draft mode and reruns

After reviewing the preview and recipient map, the user can explicitly opt in:

```sh
python run_pipeline.py --profile reviewed-profile.json --recipients reviewed-contacts.json --create-drafts --output drafts-report.json
```

Gmail authentication is lazy: preview mode never authenticates, nor do runs with
no new selected jobs. The CLI uses the existing DraftService and stores its draft
metadata. It only calls drafts.create, never send. The OAuth compose scope still
allows sending; draft-only behavior is a code restriction.

Before a Gmail call, a separate committed row in `pipeline_draft_attempts` reserves
candidate name + exact job key + recipient. A repeat run skips completed attempts.
Reservations survive failures, including a Gmail success followed by metadata
failure, and uncertain attempts report `needs_reconciliation` instead of retrying.
This protects against duplicates but means an interrupted attempt may block even
when no Gmail draft was actually created. Inspect Gmail and the attempt's stored
request before deciding what to do. This piece intentionally has no automatic
reset/retry command. A changed candidate name, recipient, job key or database is a
new identity, so review those changes before rerunning. It does not deduplicate
old drafts made through the separate manual `send_emails.py` script.

The CLI disables the Gmail client's automatic HTTP retries (`max_attempts=1`)
because a timed-out draft creation can have succeeded remotely. Library callers
should do the same in their writer. Gmail creation and local metadata are not one
atomic transaction.
Treat reconciliation statuses seriously. If a Gmail ID is known but saving status
fails, the report retains that ID for investigation.

Library use injects `analyzer`, `generator`, and an async draft writer returning
the Gmail draft ID. Call `init_pipeline_db(engine)` plus the existing job/draft
schema initializers before use. The default `PipelineOptions` never writes drafts.
The CLI exits nonzero on analysis/generation/reconciliation failures while still
writing the per-job report. Missing contacts, filtering and empty storage are
normal reported outcomes, not implicit completion of outreach.

Offline regression suite:

```sh
python -m pytest tests/test_orchestrator.py
```
