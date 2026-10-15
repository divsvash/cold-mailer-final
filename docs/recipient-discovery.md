# Reviewed recipient discovery (piece 3)

`discover_recipients.py` finds candidate hiring contacts for jobs already in
storage and keeps them in a private local `contact_candidates` table until a
person reviews them. It makes no model calls and never invents an address.
Every stored email is quoted from real text, with its provenance recorded.

## Where contacts come from

- **posting** - addresses found in the stored job posting text itself.
- **company_page** - addresses and hiring-role mentions found on the job's
  public posting page and, one hop deeper, careers/team/about pages linked
  from it. Live fetching only happens when you pass `--fetch-pages`; the
  default scan is fully offline over stored text. Owned clients never follow
  redirects, cap page size, and strip script/style before parsing.

There is deliberately no pattern guessing (`first.last@domain`). The pipeline
contract says contacts are never guessed from a name or domain. Names or role
mentions found without an address are stored as leads for manual lookup, not
as candidates. Addresses that are never a person (`noreply@`, placeholder
domains, asset filenames) are filtered out.

## Review is the gate

Candidates start as `proposed`. Only `approved` candidates export:

```sh
python discover_recipients.py scan                 # offline, from postings
python discover_recipients.py scan --fetch-pages   # also fetch public pages
python discover_recipients.py review               # list proposed candidates
python discover_recipients.py approve --job <dedup_key> --email <address>
python discover_recipients.py reject  --job <dedup_key> --email <address>
python discover_recipients.py export --output private/recipients.json
```

The export is exactly the `--recipients` JSON `run_pipeline.py` validates,
written owner-only. Re-running `scan` never duplicates or resets a reviewed
candidate: an existing job+email pair is left untouched.

## Honest limits

- An address quoted from a page is not proof it belongs to the hiring team,
  that it is current, or that mail to it will be delivered. Review the quoted
  context (`review` shows it) before approving.
- Discovery does not verify deliverability and does not use paid lookup APIs.
- Company pages change; provenance records where and when each find came
  from, not a guarantee it is still there.
- Candidates and reports contain personal addresses. The database is
  owner-only, exports are owner-only, and `private/` is gitignored. Do not
  commit or share them.
- Fetching public pages is ordinary browsing of pages the postings link to;
  it is not a guarantee a site permits automated access. Run it sparingly.

Offline regression suite:

```sh
python -m pytest tests/test_recipient_discovery.py
```
