#!/usr/bin/env python3
"""
send_emails.py — run this to generate + draft outreach emails.

Usage (simplest):
    python send_emails.py --to "priya@company.com" --company "Lumina AI" --role "Backend Engineer"

Usage (with full context for better emails):
    python send_emails.py \
        --to "alex@company.com" \
        --company "Vectorly" \
        --role "Staff ML Engineer" \
        --one-liner "Vectorly builds embedding-based developer search tools" \
        --recent-news "Vectorly launched an open-source code search API last month" \
        --recipient-name "Alex" \
        --recipient-role "CTO" \
        --job-description path/to/jd.txt

What this does:
  1. Loads your profile from memory/profile.json
  2. Loads your voice from prompts/personality.md
  3. Generates 3 email variants (technical / founder / concise) via Claude
  4. Ranks them by expected reply rate
  5. Creates the best one as a Gmail DRAFT (never sends automatically)
  6. Prints the draft so you can review before opening Gmail

You review it in Gmail Drafts → edit if needed → send manually.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import textwrap

# ── Make sure we can import from career-agent root ────────────────────────────
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))


from config import get_settings, resolve_path


def _check_env(settings, profile_path, personality_path) -> None:
    errors = []
    if not settings.ANTHROPIC_API_KEY.strip() or settings.ANTHROPIC_API_KEY.strip() == "your_anthropic_api_key_here":
        errors.append("Model API key missing. Set ANTHROPIC_API_KEY in .env or the environment.")
    for path, label in [(profile_path, "Profile"), (personality_path, "Personality guide")]:
        if not path.is_file():
            errors.append(f"{label} not found: {path}")
    if errors:
        print("Setup incomplete:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(1)


async def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Generate outreach email → create Gmail draft",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          # Minimal (just company name and your email to them)
          python send_emails.py --to hiring@stripe.com --company Stripe --role "Backend Engineer"

          # Full context (generates much better emails)
          python send_emails.py \\
            --to priya@luminaai.com \\
            --company "Lumina AI" \\
            --role "Backend Engineer" \\
            --one-liner "Lumina AI builds developer tools for fine-tuning open-source LLMs" \\
            --recent-news "Just launched an open-source fine-tuning framework" \\
            --recipient-name Priya \\
            --recipient-role "Engineering Manager" \\
            --job-description jobs/lumina_jd.txt \\
            --dry-run
        """),
    )
    parser.add_argument("--to",               required=True, help="Recipient email address")
    parser.add_argument("--company",          required=True, help="Company name")
    parser.add_argument("--role",             required=True, help="Role title you're applying to")
    parser.add_argument("--one-liner",        default=None,  help="One sentence: what the company does")
    parser.add_argument("--recent-news",      default=None,  help="A specific recent fact about the company")
    parser.add_argument("--recipient-name",   default=None,  help="Name of the person you're emailing")
    parser.add_argument("--recipient-role",   default=None,  help="Their role, e.g. 'Engineering Manager'")
    parser.add_argument("--job-description",  default=None,  help="Path to job description text file")
    parser.add_argument("--profile",          default=str(settings.PROFILE_PATH))
    parser.add_argument("--personality",      default=str(settings.PERSONALITY_PATH))
    parser.add_argument("--dry-run",          action="store_true",
                        help="Print the email but don't create a Gmail draft (no credentials needed)")
    parser.add_argument("--all-variants",     action="store_true",
                        help="Show all 3 variants, not just the best one")
    args = parser.parse_args()

    profile_path = resolve_path(args.profile)
    personality_path = resolve_path(args.personality)
    _check_env(settings, profile_path, personality_path)

    # Imports stay here so --help needs no external service setup.
    from agents.email_generator.engine import EmailGenerationEngine
    from agents.email_generator.schemas import CandidateProfile, CompanyInfo, JobAnalysis

    # ── Load candidate profile ─────────────────────────────────────────────────
    profile_path = resolve_path(args.profile)
    if not profile_path.exists():
        print(f"❌ Profile not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    candidate = CandidateProfile.model_validate(json.loads(profile_path.read_text()))
    personality = personality_path.read_text()

    # ── Build company info ─────────────────────────────────────────────────────
    company = CompanyInfo(
        name=args.company,
        one_liner=args.one_liner,
        recent_news=args.recent_news,
        role_title=args.role,
        recipient_name=args.recipient_name,
        recipient_role=args.recipient_role,
    )

    # ── Build job analysis from JD file (or minimal stub) ─────────────────────
    if args.job_description:
        jd_path = resolve_path(args.job_description)
        if not jd_path.exists():
            print(f"❌ Job description file not found: {jd_path}", file=sys.stderr)
            sys.exit(1)
        jd_text = jd_path.read_text()
        print(f"📋 Analyzing job description ({len(jd_text)} chars)...")
        from agents.job_analyzer.engine import JobUnderstandingEngine
        from agents.job_analyzer.schemas import JobUnderstanding
        try:
            understanding = JobUnderstandingEngine().analyze(jd_text)
            job = JobAnalysis(
                must_have_skills=[{"name": s.name, "category": s.category}
                                  for s in understanding.result.must_have_skills],
                preferred_skills=[{"name": s.name, "category": s.category}
                                  for s in understanding.result.preferred_skills],
                domain=understanding.result.domain.value,
                seniority=understanding.result.seniority.value,
                business_problems=[{"description": bp.description, "priority": bp.priority}
                                    for bp in understanding.result.business_problems],
                culture=[c.value for c in understanding.result.culture],
            )
        except Exception as exc:
            print(f"⚠️  Could not parse JD ({type(exc).__name__}), using minimal job context.")
            job = JobAnalysis()
    else:
        job = JobAnalysis()

    # ── Generate email variants ────────────────────────────────────────────────
    print(f"\n✉️  Generating emails for {args.company} ({args.to})...")
    engine = EmailGenerationEngine()
    try:
        result = engine.generate(candidate, job, company, personality)
    except Exception as exc:
        print(f"❌ Email generation failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)

    # ── Display ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)

    if args.all_variants:
        for v in result.variants:
            rate = next((r.expected_reply_rate for r in result.rankings if r.variant_type == v.variant_type), 0)
            reasoning = next((r.reasoning for r in result.rankings if r.variant_type == v.variant_type), "")
            is_best = v.variant_type == result.best_variant.variant_type
            tag = " ← BEST" if is_best else ""
            print(f"\n[{v.variant_type.upper()}]{tag}  |  reply rate: {rate:.0%}  |  {v.word_count} words")
            print(f"Subject: {v.subject}")
            print(f"Reasoning: {reasoning}")
            print("─" * 60)
            print(v.body)
            print("═" * 60)
    else:
        v = result.best_variant
        rate = result.best_expected_reply_rate
        reasoning = next((r.reasoning for r in result.rankings if r.variant_type == v.variant_type), "")
        print(f"\n📧 BEST VARIANT: {v.variant_type.upper()}")
        print(f"   Reply rate estimate: {rate:.0%}  |  {v.word_count} words")
        print(f"   Why: {reasoning}")
        print("─" * 60)
        print(f"To: {args.to}")
        print(f"Subject: {v.subject}")
        print()
        print(v.body)
        print("═" * 60)

    if args.dry_run:
        print("\n✅ Dry run — no draft created. Remove --dry-run to create a Gmail draft.")
        return

    # ── Create Gmail draft ─────────────────────────────────────────────────────
    print("\n📬 Creating Gmail draft...")

    try:
        from database.gmail_auth import get_gmail_service
        from database.gmail_client import GmailDraftClient
        from database.gmail_service import DraftService
        from database.draft_models import DraftRequest
        from database.draft_storage import init_db, make_engine, make_session_factory
    except ImportError as exc:
        print(f"❌ Gmail integration not available: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)

    try:
        gmail_service = get_gmail_service(
            settings.GMAIL_CREDENTIALS_PATH,
            settings.GMAIL_TOKEN_PATH,
        )
    except FileNotFoundError:
        print(f"❌ OAuth credentials not found: {settings.GMAIL_CREDENTIALS_PATH}")
        print("   Download it from Google Cloud Console (Gmail API → OAuth2 credentials)")
        print("   and place it in the career-agent/ root directory.")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Gmail auth failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)

    gmail_client = GmailDraftClient(gmail_service)

    engine_db = make_engine(settings.DATABASE_URL)
    await init_db(engine_db)
    factory = make_session_factory(engine_db)

    best = result.best_variant
    request = DraftRequest(
        to=args.to,
        subject=best.subject,
        body=best.body,
        candidate_name=candidate.full_name,
        company_name=args.company,
        variant_type=best.variant_type.value,
        expected_reply_rate=result.best_expected_reply_rate,
    )

    try:
        async with factory() as session:
            async with session.begin():
                service = DraftService(gmail_client, session)
                row = await service.create_draft(request)
    except Exception as exc:
        print(f"❌ Failed to create draft: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine_db.dispose()

    print(f"\n✅ Draft created successfully!")
    print(f"   Gmail draft ID: {row.gmail_draft_id}")
    print(f"   To:             {row.to}")
    print(f"   Subject:        {row.subject}")
    print(f"\n👉 Open Gmail → Drafts → review → send manually when ready.")


if __name__ == "__main__":
    asyncio.run(main())
