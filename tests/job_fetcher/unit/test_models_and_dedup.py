"""Unit tests: NormalizedJob, deduplication."""
from __future__ import annotations
import hashlib
import pytest
from agents.job_fetcher.deduplicator import deduplicate_in_memory, merge_results
from agents.job_fetcher.models import JobSource, NormalizedJob, RawJob, ScrapeResult


def make_job(title="Engineer", company="Acme", url="https://example.com/1",
             source=JobSource.GREENHOUSE, source_id="acme:1") -> NormalizedJob:
    return NormalizedJob(title=title, company=company, url=url, description="A great job.",
                        source=source, source_id=source_id)


class TestNormalizedJob:
    def test_dedup_key_computed(self):
        job = make_job(title="SWE", company="Acme", url="https://example.com/1")
        expected = hashlib.sha256("swe|acme|https://example.com/1".encode()).hexdigest()
        assert job.dedup_key == expected

    def test_dedup_key_case_insensitive(self):
        j1 = make_job(title="SWE", company="Acme", url="https://example.com/1")
        j2 = make_job(title="swe", company="ACME", url="https://EXAMPLE.COM/1")
        assert j1.dedup_key == j2.dedup_key

    def test_trailing_slash_stripped(self):
        j1 = make_job(url="https://example.com/1")
        j2 = make_job(url="https://example.com/1/")
        assert j1.dedup_key == j2.dedup_key

    def test_different_urls_different_keys(self):
        j1 = make_job(url="https://example.com/1")
        j2 = make_job(url="https://example.com/2")
        assert j1.dedup_key != j2.dedup_key

    def test_dedup_key_is_sha256(self):
        job = make_job()
        assert len(job.dedup_key) == 64
        assert all(c in "0123456789abcdef" for c in job.dedup_key)


class TestScrapeResult:
    def test_success_true_when_jobs_present(self):
        result = ScrapeResult(source=JobSource.GREENHOUSE, jobs=[make_job()])
        assert result.success is True

    def test_success_false_when_empty(self):
        assert ScrapeResult(source=JobSource.GREENHOUSE).success is False

    def test_error_count(self):
        result = ScrapeResult(source=JobSource.LEVER, errors=["e1", "e2"])
        assert result.error_count == 2


class TestDeduplicateInMemory:
    def test_empty(self):
        result, report = deduplicate_in_memory([])
        assert result == [] and report.total_seen == 0

    def test_single_passes_through(self):
        _, report = deduplicate_in_memory([make_job()])
        assert report.new_jobs == 1 and report.duplicates == 0

    def test_identical_jobs_deduplicated(self):
        job = make_job()
        result, report = deduplicate_in_memory([job, job])
        assert len(result) == 1 and report.duplicates == 1

    def test_first_occurrence_wins(self):
        j1 = make_job(source_id="src:1")
        j2 = make_job(source_id="src:2")
        result, _ = deduplicate_in_memory([j1, j2])
        assert result[0].source_id == "src:1"

    def test_different_jobs_all_kept(self):
        jobs = [make_job(url=f"https://example.com/{i}", source_id=f"s:{i}") for i in range(3)]
        result, report = deduplicate_in_memory(jobs)
        assert len(result) == 3 and report.duplicates == 0

    def test_mixed_input_counts(self):
        jobs = [
            make_job(url="https://example.com/1", source_id="s:1"),
            make_job(url="https://example.com/2", source_id="s:2"),
            make_job(url="https://example.com/1", source_id="s:1"),
            make_job(url="https://example.com/3", source_id="s:3"),
            make_job(url="https://example.com/2", source_id="s:2"),
        ]
        result, report = deduplicate_in_memory(jobs)
        assert report.total_seen == 5 and report.new_jobs == 3 and report.duplicates == 2


class TestMergeResults:
    def test_merges_across_sources(self):
        gh = ScrapeResult(source=JobSource.GREENHOUSE, jobs=[make_job(url="https://gh.com/1", source_id="gh:1")])
        lv = ScrapeResult(source=JobSource.LEVER,      jobs=[make_job(url="https://lv.com/1", source_id="lv:1")])
        merged, report = merge_results(gh, lv)
        assert len(merged) == 2 and report.duplicates == 0

    def test_cross_source_duplicates_removed(self):
        j1 = NormalizedJob(title="SWE", company="Acme", url="https://acme.com/1",
                           description="d", source=JobSource.GREENHOUSE, source_id="gh:1")
        j2 = NormalizedJob(title="SWE", company="Acme", url="https://acme.com/1",
                           description="d", source=JobSource.LEVER, source_id="lv:1")
        merged, report = merge_results(
            ScrapeResult(source=JobSource.GREENHOUSE, jobs=[j1]),
            ScrapeResult(source=JobSource.LEVER, jobs=[j2]),
        )
        assert len(merged) == 1 and report.duplicates == 1
