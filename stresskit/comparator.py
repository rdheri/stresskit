"""Report comparison logic for StressKit.

Loads two JSON reports and computes deltas for all key metrics.
Used by both the --compare flag on `stresskit run` and the
standalone `stresskit compare` command.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stresskit.exporter import load_report_json
from stresskit.models import RunReport


@dataclass
class MetricDelta:
    """Computed delta for a single metric between two runs.

    Attributes:
        name: Human-readable metric name.
        value1: Value from the first (baseline) run.
        value2: Value from the second (comparison) run.
        delta: Absolute difference (value2 - value1).
        pct_change: Percentage change from value1 to value2.
        lower_is_better: Whether a decrease in value is an improvement.
        improved: Whether the change represents an improvement.
    """

    name: str
    value1: float
    value2: float
    delta: float
    pct_change: float
    lower_is_better: bool
    improved: bool


def compute_deltas(report1: RunReport, report2: RunReport) -> list[MetricDelta]:
    """Compute deltas for all key metrics between two reports.

    Args:
        report1: Baseline report.
        report2: Comparison report.

    Returns:
        List of MetricDelta objects for each tracked metric.
    """
    raw_metrics: list[tuple[str, float, float, bool]] = [
        ("Requests/sec", report1.requests_per_second, report2.requests_per_second, False),
        ("Success/sec", report1.successful_rps, report2.successful_rps, False),
        ("Mean Latency (ms)", report1.latency.mean_ms, report2.latency.mean_ms, True),
        ("Median Latency (ms)", report1.latency.median_ms, report2.latency.median_ms, True),
        ("p90 Latency (ms)", report1.latency.p90_ms, report2.latency.p90_ms, True),
        ("p95 Latency (ms)", report1.latency.p95_ms, report2.latency.p95_ms, True),
        ("p99 Latency (ms)", report1.latency.p99_ms, report2.latency.p99_ms, True),
        ("Min Latency (ms)", report1.latency.min_ms, report2.latency.min_ms, True),
        ("Max Latency (ms)", report1.latency.max_ms, report2.latency.max_ms, True),
        ("Failed Requests", float(report1.failed_requests), float(report2.failed_requests), True),
        ("Total Elapsed (s)", report1.total_elapsed_s, report2.total_elapsed_s, True),
    ]

    deltas: list[MetricDelta] = []
    for name, v1, v2, lower_better in raw_metrics:
        delta = v2 - v1
        pct = ((delta / v1) * 100) if v1 != 0 else 0.0
        improved = (delta < 0) if lower_better else (delta > 0)

        deltas.append(
            MetricDelta(
                name=name,
                value1=v1,
                value2=v2,
                delta=round(delta, 3),
                pct_change=round(pct, 2),
                lower_is_better=lower_better,
                improved=improved,
            )
        )

    return deltas


def compare_files(
    path1: str | Path, path2: str | Path,
) -> tuple[RunReport, RunReport, list[MetricDelta]]:
    """Load two report files and compute their deltas.

    Args:
        path1: Path to the baseline JSON report.
        path2: Path to the comparison JSON report.

    Returns:
        Tuple of (report1, report2, list of MetricDelta).

    Raises:
        FileNotFoundError: If either file doesn't exist.
    """
    r1 = load_report_json(path1)
    r2 = load_report_json(path2)
    deltas = compute_deltas(r1, r2)
    return r1, r2, deltas
