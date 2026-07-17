"""In-memory deduplication for job listings."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from agents.job_fetcher.models import NormalizedJob, ScrapeResult

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationReport:
    total_seen:  int = 0
    new_jobs:    int = 0
    duplicates:  int = 0
    seen_keys:   set[str] = field(default_factory=set)


def deduplicate_in_memory(jobs: list[NormalizedJob]) -> tuple[list[NormalizedJob], DeduplicationReport]:
    report = DeduplicationReport(total_seen=len(jobs))
    seen: dict[str, NormalizedJob] = {}
    for job in jobs:
        if job.dedup_key not in seen:
            seen[job.dedup_key] = job
            report.new_jobs += 1
        else:
            report.duplicates += 1
    report.seen_keys = set(seen.keys())
    return list(seen.values()), report


def merge_results(*results: ScrapeResult) -> tuple[list[NormalizedJob], DeduplicationReport]:
    all_jobs: list[NormalizedJob] = []
    for r in results:
        all_jobs.extend(r.jobs)
    return deduplicate_in_memory(all_jobs)
