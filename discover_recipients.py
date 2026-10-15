"""Reviewed recipient discovery for stored jobs.

scan     reads stored postings (offline) and, only with --fetch-pages, public
         company pages, and stores proposed contact candidates.
review   lists stored candidates with provenance and review status.
approve  marks candidates reviewed-good; reject marks them out.
export   writes ONLY approved candidates as the --recipients JSON that
         run_pipeline.py consumes. Nothing reaches the pipeline unreviewed.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from config import get_settings, prepare_database_url, resolve_path
from security import private_write


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="Override the configured database URL/path")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Discover candidates from stored jobs")
    scan.add_argument("--fetch-pages", action="store_true",
                      help="Also fetch public company pages live (offline by default)")
    scan.add_argument("--job-limit", type=int, default=100)
    scan.add_argument("--output", help="Optional private JSON report path")

    review = sub.add_parser("review", help="List stored candidates")
    review.add_argument("--status", choices=["proposed", "approved", "rejected"],
                        default="proposed")

    for name in ("approve", "reject"):
        cmd = sub.add_parser(name, help=f"Mark a candidate {name}d")
        cmd.add_argument("--job", required=True, action="append", help="Job dedup_key")
        cmd.add_argument("--email", required=True, action="append",
                         help="Candidate email (pairs with --job in order)")

    export = sub.add_parser("export", help="Write approved contacts as --recipients JSON")
    export.add_argument("--output", default="private/recipients.json")
    return parser


async def _open(args):
    from agents.job_fetcher.storage import make_engine, make_session_factory, init_db
    from agents.recipient_discovery.storage import init_contact_db
    settings = get_settings()
    engine = make_engine(prepare_database_url(args.database or settings.DATABASE_URL))
    await init_db(engine)
    await init_contact_db(engine)
    return engine, make_session_factory(engine)


async def cmd_scan(args) -> int:
    from agents.job_fetcher.storage import JobRepository
    from agents.recipient_discovery.service import RecipientDiscoveryService
    from agents.recipient_discovery.storage import ContactRepository
    engine, sessions = await _open(args)
    try:
        fetcher = None
        if args.fetch_pages:
            from agents.recipient_discovery.scout import HttpxPageFetcher
            fetcher = HttpxPageFetcher()
        async with sessions() as session:
            service = RecipientDiscoveryService(
                ContactRepository(session), JobRepository(session), fetcher=fetcher)
            if fetcher is not None:
                async with fetcher:
                    report = await service.scan(args.job_limit)
            else:
                report = await service.scan(args.job_limit)
    finally:
        await engine.dispose()
    job_failures = 0
    for result in report.results:
        label = f"{result.company} - {result.title}" if result.company else result.job_dedup_key[:12]
        found = ", ".join(str(c.email) for c in result.candidates) or "no addresses found"
        print(f"{label}\n  {found}")
        if result.leads:
            print(f"  leads for manual lookup: {len(result.leads)}")
        for error in result.errors:
            job_failures += 1
            print(f"  ERROR: {error}")
    print(f"\n{report.new_candidates} new candidates stored as proposed "
          f"({report.candidate_count} found this scan). Review them before use.")
    if args.output:
        private_write(args.output, report.model_dump_json(indent=2))
        print(f"Report written to {args.output} (owner-only).")
    return 1 if (job_failures or report.errors) else 0


async def cmd_review(args) -> int:
    from agents.recipient_discovery.models import ContactStatus
    from agents.recipient_discovery.storage import ContactRepository
    engine, sessions = await _open(args)
    try:
        async with sessions() as session:
            rows = await ContactRepository(session).list_candidates(
                ContactStatus(args.status))
    finally:
        await engine.dispose()
    if not rows:
        print(f"No {args.status} candidates.")
        return 0
    for row in rows:
        print(f"[{row.status}] {row.email}  job={row.job_dedup_key[:12]}...")
        print(f"    source: {row.source} from {row.provenance}")
        if row.context:
            print(f"    quoted: {row.context[:120]}")
    return 0


async def cmd_mark(args, status) -> int:
    from agents.recipient_discovery.storage import ContactRepository
    if len(args.job) != len(args.email):
        print("--job and --email must pair up in order", file=sys.stderr)
        return 1
    engine, sessions = await _open(args)
    missing = []
    try:
        async with sessions() as session:
            repo = ContactRepository(session)
            for job_key, email in zip(args.job, args.email):
                if not await repo.set_status(job_key, email, status):
                    missing.append(f"{email} (job {job_key[:12]}...)")
            await session.commit()
    finally:
        await engine.dispose()
    if missing:
        print("Unknown candidates: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(f"Marked {len(args.job)} candidate(s) {status.value}.")
    return 0


async def cmd_export(args) -> int:
    from agents.recipient_discovery.storage import ContactRepository
    engine, sessions = await _open(args)
    try:
        async with sessions() as session:
            mapping = await ContactRepository(session).approved_map()
    finally:
        await engine.dispose()
    if not mapping:
        print("No approved candidates yet - nothing exported. "
              "Review and approve first.", file=sys.stderr)
        return 1
    private_write(args.output, json.dumps(mapping, indent=2))
    print(f"Exported {len(mapping)} approved contact(s) to {args.output} (owner-only).")
    print(f"Use with: python run_pipeline.py --recipients {args.output} ...")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    from agents.recipient_discovery.models import ContactStatus
    if args.command == "scan":
        return asyncio.run(cmd_scan(args))
    if args.command == "review":
        return asyncio.run(cmd_review(args))
    if args.command in ("approve", "reject"):
        status = ContactStatus.APPROVED if args.command == "approve" else ContactStatus.REJECTED
        return asyncio.run(cmd_mark(args, status))
    return asyncio.run(cmd_export(args))


if __name__ == "__main__":
    sys.exit(main())
