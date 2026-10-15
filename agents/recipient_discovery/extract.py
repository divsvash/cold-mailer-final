"""Deterministic contact extraction from quoted text. No model calls."""
from __future__ import annotations
import re
from pydantic import ValidationError
from agents.recipient_discovery.models import ContactCandidate, ContactSource, NameLead

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,24}")

# Addresses that are never a person worth emailing, and placeholder junk.
_IGNORED_LOCAL_EXACT = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon",
    "postmaster", "webmaster", "user", "username", "email", "name",
    "someone", "yourname", "example", "test",
}
_IGNORED_LOCAL_PREFIXES = ("noreply", "no-reply", "donotreply", "do-not-reply")
_IGNORED_DOMAINS = {
    "example.com", "example.org", "example.net", "domain.com", "company.com",
    "test.com", "email.com", "sentry.io", "w3.org", "schema.org",
    "github.com", "localhost",
}
# Regex can catch asset filenames such as image@2x.png; these TLDs are not mail.
_IGNORED_TLDS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "css", "js", "ico"}

HIRING_KEYWORDS = (
    "recruiter", "talent acquisition", "hiring manager", "head of talent",
    "people ops", "people operations", "careers team", "talent partner",
)

MAX_EMAILS_PER_TEXT = 10
MAX_LEADS_PER_TEXT = 5
SNIPPET_RADIUS = 80


def _snippet(text: str, start: int, end: int) -> str:
    raw = text[max(0, start - SNIPPET_RADIUS): end + SNIPPET_RADIUS]
    return re.sub(r"\s+", " ", raw).strip()[: 2 * SNIPPET_RADIUS]


def _acceptable(address: str) -> bool:
    local, _, domain = address.rpartition("@")
    local = local.lower()
    domain = domain.lower()
    tld = domain.rsplit(".", 1)[-1]
    if local in _IGNORED_LOCAL_EXACT:
        return False
    if any(local.startswith(prefix) for prefix in _IGNORED_LOCAL_PREFIXES):
        return False
    if domain in _IGNORED_DOMAINS or tld in _IGNORED_TLDS:
        return False
    if domain.endswith(".example.com") or domain.endswith(".test"):
        return False
    return True


def extract_emails(text: str, *, job_dedup_key: str, source: ContactSource,
                   provenance: str, limit: int = MAX_EMAILS_PER_TEXT) -> list[ContactCandidate]:
    """Quote real addresses found in text, with provenance. Never invents one."""
    found: list[ContactCandidate] = []
    seen: set[str] = set()
    for match in EMAIL_RE.finditer(text or ""):
        address = match.group(0).lower().rstrip(".;,")
        if address in seen or not _acceptable(address):
            continue
        seen.add(address)
        try:
            found.append(ContactCandidate(
                job_dedup_key=job_dedup_key, email=address, source=source,
                provenance=provenance, context=_snippet(text, match.start(), match.end()),
            ))
        except ValidationError:
            continue
        if len(found) >= limit:
            break
    return found


def find_hiring_leads(text: str, *, job_dedup_key: str, provenance: str,
                      limit: int = MAX_LEADS_PER_TEXT) -> list[NameLead]:
    """Record hiring-role mentions (recruiter, talent, ...) for manual lookup."""
    leads: list[NameLead] = []
    lowered = (text or "").lower()
    for keyword in HIRING_KEYWORDS:
        index = lowered.find(keyword)
        if index < 0:
            continue
        snippet = _snippet(text, index, index + len(keyword))
        leads.append(NameLead(
            job_dedup_key=job_dedup_key, provenance=provenance,
            description=f"mentions '{keyword}': {snippet}",
        ))
        if len(leads) >= limit:
            break
    return leads
