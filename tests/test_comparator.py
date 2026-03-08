"""Unit tests for the report comparison module.

Tests delta computation, direction detection (improved/regressed),
percentage change calculation, and file loading for comparison.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from stresskit.comparator import compare_files, compute_deltas
from stresskit.models import (
    ErrorBreakdown,
    LatencyStats,
    RunConfig,
    RunReport,
)


def _make_report(
    rps: float = 100.0,
    mean_ms: float = 50.0,
    p90_ms: float = 80.0,
    p95_ms: float = 90.0,
    p99_ms: float = 120.0,
    failed: int = 0,
) -> RunReport:
    """Create a minimal RunReport for testing."""
    return RunReport(
        run_id="test123",
        timestamp="2025-01-01T00:00:00Z",
        stresskit_version="1.0.0",
        config=RunConfig(url="https://example.com", concurrency=10, total_requests=100),
        total_requests=100,
        successful_requests=100 - failed,
        failed_requests=failed,
        total_elapsed_s=1.0,
        requests_per_second=rps,
        successful_rps=rps - failed,
        latency=LatencyStats(
            min_ms=10.0,
            max_ms=200.0,
            mean_ms=mean_ms,
            median_ms=mean_ms,
            p50_ms=mean_ms,
            p75_ms=mean_ms + 10,
            p90_ms=p90_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            stddev_ms=15.0,
        ),
        errors=ErrorBreakdown(),
    )


class TestComputeDeltas:
    """Tests for compute_deltas()."""

    def test_identical_reports(self) -> None:
        """Identical reports should have zero deltas."""
        r = _make_report()
        deltas = compute_deltas(r, r)
        for d in deltas:
            assert d.delta == 0.0
            assert d.pct_change == 0.0

    def test_improved_latency(self) -> None:
        """Lower latency in run2 should be marked as improved."""
        r1 = _make_report(mean_ms=100.0)
        r2 = _make_report(mean_ms=50.0)
        deltas = compute_deltas(r1, r2)

        mean_delta = next(d for d in deltas if d.name == "Mean Latency (ms)")
        assert mean_delta.delta == -50.0
        assert mean_delta.improved is True
        assert mean_delta.lower_is_better is True

    def test_regressed_latency(self) -> None:
        """Higher latency in run2 should be marked as regressed."""
        r1 = _make_report(mean_ms=50.0)
        r2 = _make_report(mean_ms=100.0)
        deltas = compute_deltas(r1, r2)

        mean_delta = next(d for d in deltas if d.name == "Mean Latency (ms)")
        assert mean_delta.delta == 50.0
        assert mean_delta.improved is False

    def test_improved_throughput(self) -> None:
        """Higher RPS in run2 should be marked as improved."""
        r1 = _make_report(rps=100.0)
        r2 = _make_report(rps=150.0)
        deltas = compute_deltas(r1, r2)

        rps_delta = next(d for d in deltas if d.name == "Requests/sec")
        assert rps_delta.delta == 50.0
        assert rps_delta.improved is True
        assert rps_delta.lower_is_better is False

    def test_percentage_change(self) -> None:
        """Verify percentage change is computed correctly."""
        r1 = _make_report(rps=100.0)
        r2 = _make_report(rps=125.0)
        deltas = compute_deltas(r1, r2)

        rps_delta = next(d for d in deltas if d.name == "Requests/sec")
        assert rps_delta.pct_change == 25.0

    def test_zero_baseline_no_division_error(self) -> None:
        """Zero baseline should result in 0% change, not division error."""
        r1 = _make_report(failed=0)
        r2 = _make_report(failed=5)
        deltas = compute_deltas(r1, r2)

        failed_delta = next(d for d in deltas if d.name == "Failed Requests")
        assert failed_delta.delta == 5.0
        # pct_change should be 0 when baseline is 0
        assert failed_delta.pct_change == 0.0

    def test_all_metrics_present(self) -> None:
        """Ensure all expected metrics appear in deltas."""
        r = _make_report()
        deltas = compute_deltas(r, r)
        names = {d.name for d in deltas}
        expected = {
            "Requests/sec",
            "Success/sec",
            "Mean Latency (ms)",
            "Median Latency (ms)",
            "p90 Latency (ms)",
            "p95 Latency (ms)",
            "p99 Latency (ms)",
            "Min Latency (ms)",
            "Max Latency (ms)",
            "Failed Requests",
            "Total Elapsed (s)",
        }
        assert expected == names


class TestCompareFiles:
    """Tests for compare_files()."""

    def test_load_and_compare(self) -> None:
        """Verify that files can be loaded and compared end-to-end."""
        r1 = _make_report(rps=100.0, mean_ms=50.0)
        r2 = _make_report(rps=150.0, mean_ms=40.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "run1.json"
            p2 = Path(tmpdir) / "run2.json"

            p1.write_text(r1.model_dump_json(indent=2))
            p2.write_text(r2.model_dump_json(indent=2))

            loaded_r1, loaded_r2, deltas = compare_files(p1, p2)

        assert loaded_r1.requests_per_second == 100.0
        assert loaded_r2.requests_per_second == 150.0
        assert len(deltas) > 0

    def test_missing_file_raises(self) -> None:
        """Verify FileNotFoundError when a file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            compare_files("/nonexistent/path.json", "/also/nonexistent.json")
