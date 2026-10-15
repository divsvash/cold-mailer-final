# Security pass and limits

This is a local single-user CLI, not a hardened hosted service. A passing scan
and tests do not establish that the entire codebase is secure. Do not expose it
to arbitrary remote users. No live Gmail, model or OAuth run was performed.

## Fixed in this pass

- High: OAuth token writes previously inherited permissive umasks. Tokens and
  credential files are now restricted to owner-only access; token replacements
  are atomic 0600 files. No secret text is added to logs.
- High: generated reports/profiles and SQLite can contain candidate data,
  contacts, full email text and draft request bodies. New report/profile output
  files are atomic 0600 writes, new private directories use 0700, and SQLite is
  created 0600 before opening. Private-write destinations reject symlinks and
  symlink ancestors. Database URLs hide their password in settings repr.
- Medium: runtime reports/contacts/local env variants/SQLite variants were not
  ignored. Standard output folders and common filenames are now ignored. The
  default profile is private/profile.json. Writes to the tracked historical
  memory/profile.json sample are rejected, preventing accidental replacement
  with actual personal data. .gitignore does not remove data already committed,
  and arbitrary user-chosen filenames are not automatically safe. Review staged
  diffs and use private/, reports/ or outputs/ for personal data.
- High residual, mitigated: untrusted JD/company/personality content could be
  promoted into model system instructions. Generation now keeps fact sheets and
  personality text in JSON-encoded user data; analysis/extraction/ranking mark
  untrusted inputs explicitly and forbid following embedded action requests.
  Input length bounds prevent excessive text submission. Model calls only have
  schema-recording tools, not file, browser, network or Gmail action tools.
  Recipients remain supplied locally, not chosen by models. Prompt injection
  cannot be solved by prompt wording or JSON encoding. Output manipulation and
  false claims remain possible: require human review of sources and text.
- Medium: MIME header injection is rejected at the final Gmail adapter boundary.
  Recipients must also pass email-address validation. Model subjects cannot add
  CC/BCC/new headers through CR/LF/NUL injection.
- Medium: company slugs are restricted before constructing fixed-host scraper
  URLs. Owned HTTP clients no longer follow redirects to unexpected hosts.
  Script/style/template text is stripped from normalized HTML. This does not
  make web text trusted; injected custom HTTP clients retain caller responsibility.
- Medium: profile extraction, job validation and draft errors could echo private
  response/exception text. Public exception strings and manual CLI diagnostics
  omit raw upstream content. Explicit preview stdout still contains email text,
  as requested by preview mode: do not pipe it to public logs.
- Low: PDF/markdown source sizes are bounded before parsing. This is not a parser
  sandbox; untrusted PDFs still need isolation and current dependencies.

## Reviewed boundaries and remaining work

No production shell execution/subprocess, eval/exec, pickle or YAML loading was
found. JSON uses schema validation; SQLAlchemy uses bound/ORM expressions, not
SQL assembled from user strings. File paths are local operator inputs, not remote
request parameters, and absolute paths are intentionally supported. Do not reuse
these CLI paths as a multi-user web API without a separate filesystem sandbox.
Symlink checks are defense-in-depth, not protection from a malicious process
running as the same OS user or racing directory replacements.

SQLite, reports, .env and OAuth tokens are NOT encrypted at rest. Filesystem
permissions do not protect against malware, backups, root or another process
under the same account. Old files, DB sidecar files, exported logs, existing
backups and repository history need their own review and retention/deletion.
The tracked profile is stale example content, not verified user material; the
new default no longer reads it. No history rewrite or user-data deletion is done.
Gmail credentials and model keys must come from a secure local configuration,
never checked-in files. Keep .env owner-only and secrets out of terminal history.

Gmail compose scope permits drafts AND sending. It is the draft-capable scope
used here, not a draft-only OAuth permission. Code uses drafts.create and never
send, but a stolen token could send. Scope string/file presence does not verify
account identity, token validity or provider controls. Pipeline attempts prevent
blind retry across runs; Gmail/local metadata are not atomic. Reconcile uncertain
results manually. Do not automatically widen scopes.

Dependency audit of the fresh installed requirements reported no known
vulnerabilities at this pass. Bandit reported no findings in production modules.
These detect known patterns/advisories only, not all flaws. requirements.lock.txt
records the application/test dependency resolution with hashes; re-audit when
updating. Install with `pip install --require-hashes -r requirements.lock.txt`.
No real provider account data was sent to scanners.

Future verification: real provider authentication, selected-account checks,
provider-side draft confirmation, live scraper behavior, stronger output/source
provenance, resource limits for web responses/PDF CPU, and OS-level isolation.
