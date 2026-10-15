# Grounding checks and setup diagnostics

Email generation now checks both subject and body for unsupported proper nouns
and numeric expressions. A number and its unit/currency must appear in the fact
sheet. Common forms normalize: `1,000` / `1000`, `%` / `percent`,
`$5 million` / `$5000000`, plural units, and `milliseconds` / `ms`.
Unsupported expressions stop generation before draft creation.

This remains a conservative lexical guard, NOT proof that an email is true.
A fact sheet with "90 users" does not support "90%", but two unrelated claims
with the same numeric value/unit can still pass. Number words ("nine hundred"),
negation, attribution, semantic meaning, and unsupported nonnumeric claims are
not reliably verified. It can reject harmless new numbers as well. Review the
candidate's sources, recipient and final text before creating or sending drafts.
Do not describe output as hallucination-free. The model prompt is a second
instruction layer, not a factual guarantee.

Empty standalone job requirements now produce fit score 0 with an explicit
"Insufficient job requirements" concern. That means insufficient evidence, not
proof of a poor candidate. The pipeline continues to skip this case.

`setup_check.py` imports Beautiful Soup as `bs4`, includes source/personality and
Gmail file failures in its result, and exits 1 on failed required checks. Its
checks are local file/import checks only: file presence does not prove valid
OAuth credentials, usable tokens, actual model access, or a truthful profile.
A missing .env is advisory when settings are supplied through environment values.
Real adapters now reject missing/blank/placeholder model keys with an actionable
ANTHROPIC_API_KEY setup message before constructing the SDK. Injected offline
clients still require no key. No secret values are printed in these messages.
