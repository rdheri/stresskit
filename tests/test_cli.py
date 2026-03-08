"""Integration tests for StressKit CLI commands.

Tests the Typer CLI interface including version flag, help output,
history command, compare command, and header parsing. Uses
typer.testing.CliRunner for isolated CLI invocation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from stresskit import __version__
from stresskit.cli import _parse_headers, app
from stresskit.models import ErrorBreakdown, LatencyStats, RunConfig, RunReport

runner = CliRunner()


class TestVersionFlag:
    """Tests for the --version flag."""

    def test_version_output(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestHelpOutput:
    """Tests for help text rendering."""

    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "load testing" in result.stdout.lower() or "stresskit" in result.stdout.lower()

    def test_run_help(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "url" in result.stdout.lower()

    def test_compare_help(self) -> None:
        result = runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0

    def test_history_help(self) -> None:
        result = runner.invoke(app, ["history", "--help"])
        assert result.exit_code == 0


class TestParseHeaders:
    """Tests for the _parse_headers helper."""

    def test_valid_header(self) -> None:
        result = _parse_headers(["Authorization: Bearer token123"])
        assert result == {"Authorization": "Bearer token123"}

    def test_multiple_headers(self) -> None:
        result = _parse_headers([
            "Authorization: Bearer token123",
            "Content-Type: application/json",
        ])
        assert len(result) == 2
        assert result["Content-Type"] == "application/json"

    def test_header_with_colon_in_value(self) -> None:
        result = _parse_headers(["X-Custom: value:with:colons"])
        assert result["X-Custom"] == "value:with:colons"

    def test_empty_list(self) -> None:
        result = _parse_headers([])
        assert result == {}

    def test_invalid_header_raises(self) -> None:
        import typer

        with pytest.raises(typer.BadParameter):
            _parse_headers(["no-colon-here"])


class TestCompareCommand:
    """Tests for the `stresskit compare` command."""

    def _make_report_file(self, tmpdir: str, name: str, rps: float = 100.0) -> Path:
        """Write a minimal report JSON file for testing."""
        report = RunReport(
            run_id="test123",
            timestamp="2025-01-01T00:00:00Z",
            stresskit_version="1.0.0",
            config=RunConfig(url="https://example.com", concurrency=10, total_requests=100),
            total_requests=100,
            successful_requests=100,
            failed_requests=0,
            total_elapsed_s=1.0,
            requests_per_second=rps,
            successful_rps=rps,
            latency=LatencyStats(
                min_ms=10.0, max_ms=200.0, mean_ms=50.0, median_ms=50.0,
                p50_ms=50.0, p75_ms=60.0, p90_ms=80.0, p95_ms=90.0,
                p99_ms=120.0, stddev_ms=15.0,
            ),
            errors=ErrorBreakdown(),
        )
        path = Path(tmpdir) / name
        path.write_text(report.model_dump_json(indent=2))
        return path

    def test_compare_two_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = self._make_report_file(tmpdir, "run1.json", rps=100.0)
            f2 = self._make_report_file(tmpdir, "run2.json", rps=150.0)
            result = runner.invoke(app, ["compare", str(f1), str(f2)])
            assert result.exit_code == 0
            assert "Delta" in result.stdout or "delta" in result.stdout.lower()

    def test_compare_missing_file(self) -> None:
        result = runner.invoke(app, ["compare", "/nonexistent1.json", "/nonexistent2.json"])
        assert result.exit_code == 1


class TestHistoryCommand:
    """Tests for the `stresskit history` command."""

    def test_history_no_runs(self) -> None:
        """History should handle empty database gracefully."""
        result = runner.invoke(app, ["history"])
        # Should not crash, may show "No run history" or a table
        assert result.exit_code == 0
