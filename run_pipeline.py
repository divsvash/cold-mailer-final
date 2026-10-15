#!/usr/bin/env python3
"""Run stored-job outreach. Defaults to previews; never sends email."""
from __future__ import annotations
from security import private_write

import argparse
import asyncio
import json

from config import ModelSetupError, get_settings, resolve_path


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    # Explicit input prevents silently treating the bundled example profile as real.
    parser.add_argument("--profile", required=True, help="Reviewed candidate JSON, not bundled example data")
    parser.add_argument("--recipients", required=True, help="JSON object: exact job dedup_key -> {email, name?, role?}")
    parser.add_argument("--personality", default=str(settings.PERSONALITY_PATH))
    parser.add_argument("--database", default=settings.DATABASE_URL)
    parser.add_argument("--min-fit", type=float, default=0.6)
    parser.add_argument("--max-selected", type=int, default=5)
    parser.add_argument("--job-limit", type=int, default=100)
    parser.add_argument("--create-drafts", action="store_true", help="Explicitly create Gmail drafts. Never sends.")
    parser.add_argument("--output", help="Local JSON report (contains email text and recipients)")
    return parser


async def run(args):
    from agents.email_generator.engine import EmailGenerationEngine
    from agents.email_generator.schemas import CandidateProfile
    from agents.job_analyzer.engine import JobUnderstandingEngine
    from agents.job_fetcher.storage import init_db, make_engine, make_session_factory
    from database.draft_storage import init_db as init_drafts
    from orchestrator import Orchestrator, PipelineOptions, Recipient, init_pipeline_db

    options = PipelineOptions(args.min_fit, args.max_selected, args.job_limit, args.create_drafts)
    candidate = CandidateProfile.model_validate_json(resolve_path(args.profile).read_text())
    raw = json.loads(resolve_path(args.recipients).read_text())
    if not isinstance(raw, dict):
        raise ValueError("Recipients must be a JSON object keyed by job dedup_key")
    recipients = {key: Recipient.model_validate(value) for key, value in raw.items()}
    personality = resolve_path(args.personality).read_text()
    engine = make_engine(args.database)
    try:
        await init_db(engine)
        await init_drafts(engine)
        await init_pipeline_db(engine)
        sessions = make_session_factory(engine)
        gmail_client = None

        async def write_draft(request):
            # Lazy: preview, empty shortlist and previously attempted jobs never authenticate.
            nonlocal gmail_client
            from database.gmail_auth import get_gmail_service
            from database.gmail_client import GmailDraftClient
            from database.gmail_service import DraftService
            if gmail_client is None:
                settings = get_settings()
                gmail_client = GmailDraftClient(get_gmail_service(
                    settings.GMAIL_CREDENTIALS_PATH, settings.GMAIL_TOKEN_PATH), max_attempts=1)
            async with sessions.begin() as session:
                row = await DraftService(gmail_client, session).create_draft(request)
                return row.gmail_draft_id

        pipeline = Orchestrator(sessions, JobUnderstandingEngine(), EmailGenerationEngine(),
                                write_draft if options.create_drafts else None)
        report = await pipeline.run(candidate, personality, recipients, options)
        text = json.dumps(report.to_dict(), indent=2)
        if args.output:
            output = resolve_path(args.output)
            private_write(output, text + "\n")
        else:
            print(text)
        return report
    finally:
        await engine.dispose()


def main():
    args = build_parser().parse_args()
    try:
        report = asyncio.run(run(args))
    except ModelSetupError as exc:
        raise SystemExit(str(exc)) from None
    except Exception as exc:
        # Do not print raw upstream exception text, which may contain private inputs.
        raise SystemExit(f"Pipeline stopped: {type(exc).__name__}") from None
    if any(j.status in {"analysis_failed", "generation_failed", "needs_reconciliation"} for j in report.jobs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
