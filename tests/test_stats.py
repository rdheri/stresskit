"""Unit tests for the statistics computation module.

Tests latency percentile calculations, histogram generation,
timeline bucketing, error breakdown, and full report building,
including edge cases with empty data and single-element datasets.
"""

from __future__ import annotations

import pytest

from stresskit.models import RequestResult, RunConfig
from stresskit.stats import (
    build_report,
    compute_error_breakdown,
    compute_histogram,
    compute_latency_stats,
    compute_timeline,
    percentile,
)

# ── percentile() ──


class TestPercentile:
    """Tests for the percentile() function."""

    def test_single_value(self) -> None:
        assert percentile([42.0], 50) == 42.0
        assert percentile([42.0], 0) == 42.0
        assert percentile([42.0], 100) == 42.0

    def test_two_values_median(self) -> None:
        result = percentile([10.0, 20.0], 50)
        assert result == 15.0

    def test_known_percentiles(self) -> None:
        data = sorted([float(i) for i in range(1, 101)])  # 1..100
        assert percentile(data, 0) == 1.0
        assert percentile(data, 100) == 100.0
        assert percentile(data, 50) == 50.5

    def test_p99_large_dataset(self) -> None:
        data = sorted([float(i) for i in range(1, 1001)])
        p99 = percentile(data, 99)
        assert 989 < p99 < 1000

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            percentile([], 50)

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="0-100"):
            percentile([1.0], 101)
        with pytest.raises(ValueError, match="0-100"):
            percentile([1.0], -1)


# ── compute_latency_stats() ──


class TestComputeLatencyStats:
    """Tests for compute_latency_stats()."""

    def test_basic_stats(self) -> None:
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = compute_latency_stats(latencies)
        assert stats.min_ms == 10.0
        assert stats.max_ms == 50.0
        assert stats.mean_ms == 30.0
        assert stats.median_ms == 30.0
        assert stats.p50_ms == stats.median_ms

    def test_single_latency(self) -> None:
        stats = compute_latency_stats([100.0])
        assert stats.min_ms == 100.0
        assert stats.max_ms == 100.0
        assert stats.mean_ms == 100.0
        assert stats.stddev_ms == 0.0

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_latency_stats([])

    def test_ordering_of_percentiles(self) -> None:
        latencies = [float(i) for i in range(1, 201)]
        stats = compute_latency_stats(latencies)
        assert stats.p50_ms <= stats.p75_ms
        assert stats.p75_ms <= stats.p90_ms
        assert stats.p90_ms <= stats.p95_ms
        assert stats.p95_ms <= stats.p99_ms

    def test_stddev_positive(self) -> None:
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = compute_latency_stats(latencies)
        assert stats.stddev_ms > 0


# ── compute_error_breakdown() ──


class TestComputeErrorBreakdown:
    """Tests for compute_error_breakdown()."""

    def test_all_successful(self) -> None:
        results = [
            RequestResult(timestamp=0.0, latency_ms=10.0, status_code=200, success=True)
            for _ in range(5)
        ]
        breakdown = compute_error_breakdown(results)
        assert breakdown.status_codes == {"200": 5}
        assert breakdown.timeout_count == 0
        assert breakdown.connection_error_count == 0

    def test_mixed_errors(self) -> None:
        results = [
            RequestResult(timestamp=0.0, latency_ms=10.0, status_code=200, success=True),
            RequestResult(timestamp=0.0, latency_ms=10.0, status_code=500, success=False),
            RequestResult(timestamp=0.0, latency_ms=10.0, success=False, error="timeout"),
            RequestResult(
                timestamp=0.0, latency_ms=10.0, success=False,
                error="connection_error: refused",
            ),
            RequestResult(
                timestamp=0.0, latency_ms=10.0, success=False,
                error="unexpected: ValueError: bad",
            ),
        ]
        breakdown = compute_error_breakdown(results)
        assert breakdown.status_codes == {"200": 1, "500": 1}
        assert breakdown.timeout_count == 1
        assert breakdown.connection_error_count == 1
        assert breakdown.other_error_count == 1

    def test_empty_results(self) -> None:
        breakdown = compute_error_breakdown([])
        assert breakdown.status_codes == {}
        assert breakdown.timeout_count == 0


# ── compute_histogram() ──


class TestComputeHistogram:
    """Tests for compute_histogram()."""

    def test_basic_histogram(self) -> None:
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        edges, counts = compute_histogram(latencies, num_buckets=5)
        assert len(edges) == 6
        assert len(counts) == 5
        assert sum(counts) == len(latencies)

    def test_empty_returns_empty(self) -> None:
        edges, counts = compute_histogram([])
        assert edges == []
        assert counts == []

    def test_single_value(self) -> None:
        edges, counts = compute_histogram([42.0])
        assert len(counts) == 1
        assert counts[0] == 1

    def test_all_same_value(self) -> None:
        edges, counts = compute_histogram([10.0] * 100)
        assert sum(counts) == 100

    def test_total_preserved(self) -> None:
        latencies = [float(i) for i in range(500)]
        _, counts = compute_histogram(latencies, num_buckets=10)
        assert sum(counts) == 500


# ── compute_timeline() ──


class TestComputeTimeline:
    """Tests for compute_timeline()."""

    def test_single_second(self) -> None:
        results = [
            RequestResult(timestamp=1000.0, latency_ms=50.0, status_code=200, success=True),
            RequestResult(timestamp=1000.5, latency_ms=100.0, status_code=200, success=True),
        ]
        timeline = compute_timeline(results)
        assert len(timeline) == 1
        assert timeline[0].request_count == 2
        assert timeline[0].success_count == 2

    def test_multiple_seconds(self) -> None:
        results = [
            RequestResult(timestamp=1000.0, latency_ms=50.0, status_code=200, success=True),
            RequestResult(timestamp=1001.0, latency_ms=100.0, status_code=200, success=True),
            RequestResult(timestamp=1002.0, latency_ms=150.0, status_code=500, success=False),
        ]
        timeline = compute_timeline(results)
        assert len(timeline) == 3
        assert timeline[2].success_count == 0

    def test_empty(self) -> None:
        assert compute_timeline([]) == []

    def test_gap_seconds_filled(self) -> None:
        results = [
            RequestResult(timestamp=1000.0, latency_ms=50.0, status_code=200, success=True),
            RequestResult(timestamp=1003.0, latency_ms=50.0, status_code=200, success=True),
        ]
        timeline = compute_timeline(results)
        assert len(timeline) == 4  # seconds 0, 1, 2, 3
        assert timeline[1].request_count == 0
        assert timeline[2].request_count == 0


# ── build_report() ──


class TestBuildReport:
    """Tests for build_report()."""

    def test_basic_report(self) -> None:
        config = RunConfig(url="https://example.com", concurrency=5, total_requests=10)
        results = [
            RequestResult(
                timestamp=1000.0 + i * 0.1,
                latency_ms=50.0 + i,
                status_code=200,
                success=True,
                bytes_received=1024,
            )
            for i in range(10)
        ]
        report = build_report(config, results, total_elapsed_s=1.0)

        assert report.total_requests == 10
        assert report.successful_requests == 10
        assert report.failed_requests == 0
        assert report.requests_per_second == 10.0
        assert report.total_bytes == 10240
        assert report.latency.min_ms == 50.0
        assert report.latency.max_ms == 59.0

    def test_all_failures(self) -> None:
        config = RunConfig(url="https://example.com")
        results = [
            RequestResult(timestamp=1000.0, latency_ms=30000.0, success=False, error="timeout")
            for _ in range(5)
        ]
        report = build_report(config, results, total_elapsed_s=30.0)

        assert report.successful_requests == 0
        assert report.failed_requests == 5
        assert report.errors.timeout_count == 5

    def test_report_has_run_id(self) -> None:
        config = RunConfig(url="https://example.com", total_requests=1)
        results = [RequestResult(timestamp=0.0, latency_ms=10.0, status_code=200, success=True)]
        report = build_report(config, results, 0.1)
        assert len(report.run_id) == 12
