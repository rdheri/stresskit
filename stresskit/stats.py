"""Statistics computation for load test results.

Computes latency percentiles, throughput metrics, error breakdowns,
histogram distributions, and per-second timeline data from raw request results.
"""

from __future__ import annotations

import math
import statistics
import uuid
from datetime import datetime, timezone

from stresskit import __version__
from stresskit.models import (
    ErrorBreakdown,
    LatencyStats,
    RequestResult,
    RunConfig,
    RunReport,
    TimeBucket,
)


def percentile(sorted_data: list[float], pct: float) -> float:
    """Compute the given percentile from pre-sorted data.

    Uses linear interpolation between data points.

    Args:
        sorted_data: Sorted list of numeric values.
        pct: Percentile to compute (0-100).

    Returns:
        The interpolated percentile value.

    Raises:
        ValueError: If data is empty or pct is out of range.
    """
    if not sorted_data:
        raise ValueError("Cannot compute percentile of empty dataset")
    if not 0 <= pct <= 100:
        raise ValueError(f"Percentile must be 0-100, got {pct}")

    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]

    rank = (pct / 100.0) * (n - 1)
    lower = int(math.floor(rank))
    upper = min(lower + 1, n - 1)
    fraction = rank - lower

    return sorted_data[lower] + fraction * (sorted_data[upper] - sorted_data[lower])


def compute_latency_stats(latencies_ms: list[float]) -> LatencyStats:
    """Compute comprehensive latency statistics from a list of latencies.

    Args:
        latencies_ms: List of latency values in milliseconds.

    Returns:
        LatencyStats with min, max, mean, median, percentiles, and stddev.

    Raises:
        ValueError: If latencies list is empty.
    """
    if not latencies_ms:
        raise ValueError("Cannot compute stats from empty latency list")

    sorted_lat = sorted(latencies_ms)
    mean = statistics.mean(sorted_lat)
    stddev = statistics.stdev(sorted_lat) if len(sorted_lat) > 1 else 0.0

    return LatencyStats(
        min_ms=round(sorted_lat[0], 3),
        max_ms=round(sorted_lat[-1], 3),
        mean_ms=round(mean, 3),
        median_ms=round(percentile(sorted_lat, 50), 3),
        p50_ms=round(percentile(sorted_lat, 50), 3),
        p75_ms=round(percentile(sorted_lat, 75), 3),
        p90_ms=round(percentile(sorted_lat, 90), 3),
        p95_ms=round(percentile(sorted_lat, 95), 3),
        p99_ms=round(percentile(sorted_lat, 99), 3),
        stddev_ms=round(stddev, 3),
    )


def compute_error_breakdown(results: list[RequestResult]) -> ErrorBreakdown:
    """Categorize errors from request results.

    Args:
        results: List of individual request results.

    Returns:
        ErrorBreakdown with status code distribution and error counts.
    """
    status_codes: dict[str, int] = {}
    timeout_count = 0
    connection_error_count = 0
    other_error_count = 0

    for r in results:
        if r.status_code is not None:
            key = str(r.status_code)
            status_codes[key] = status_codes.get(key, 0) + 1

        if r.error:
            if r.error == "timeout":
                timeout_count += 1
            elif r.error.startswith("connection_error"):
                connection_error_count += 1
            else:
                other_error_count += 1

    return ErrorBreakdown(
        status_codes=status_codes,
        timeout_count=timeout_count,
        connection_error_count=connection_error_count,
        other_error_count=other_error_count,
    )


def compute_histogram(
    latencies_ms: list[float], num_buckets: int = 20
) -> tuple[list[float], list[int]]:
    """Compute a histogram of latency values.

    Args:
        latencies_ms: List of latency values in milliseconds.
        num_buckets: Number of histogram buckets to create.

    Returns:
        Tuple of (bucket_edges, counts). bucket_edges has len = num_buckets + 1,
        counts has len = num_buckets.
    """
    if not latencies_ms:
        return [], []

    min_val = min(latencies_ms)
    max_val = max(latencies_ms)

    if min_val == max_val:
        return [min_val, max_val + 1], [len(latencies_ms)]

    bucket_width = (max_val - min_val) / num_buckets
    edges = [round(min_val + i * bucket_width, 3) for i in range(num_buckets + 1)]
    counts = [0] * num_buckets

    for val in latencies_ms:
        idx = int((val - min_val) / bucket_width)
        idx = min(idx, num_buckets - 1)  # Clamp last value into final bucket
        counts[idx] += 1

    return edges, counts


def compute_timeline(results: list[RequestResult]) -> list[TimeBucket]:
    """Group results into 1-second time buckets for timeline display.

    Args:
        results: List of individual request results, each with a timestamp.

    Returns:
        List of TimeBucket objects, one per second of the test run.
    """
    if not results:
        return []

    timestamps = [r.timestamp for r in results]
    start_time = min(timestamps)

    buckets: dict[int, list[RequestResult]] = {}
    for r in results:
        second = int(r.timestamp - start_time)
        buckets.setdefault(second, []).append(r)

    max_second = max(buckets.keys()) if buckets else 0
    timeline: list[TimeBucket] = []

    for sec in range(max_second + 1):
        bucket_results = buckets.get(sec, [])
        request_count = len(bucket_results)
        success_count = sum(1 for r in bucket_results if r.success)
        avg_latency = (
            round(statistics.mean(r.latency_ms for r in bucket_results), 3)
            if bucket_results
            else 0.0
        )
        timeline.append(
            TimeBucket(
                second=sec,
                request_count=request_count,
                success_count=success_count,
                avg_latency_ms=avg_latency,
            )
        )

    return timeline


def build_report(
    config: RunConfig,
    results: list[RequestResult],
    total_elapsed_s: float,
) -> RunReport:
    """Build a complete RunReport from raw results and configuration.

    Computes all derived statistics, histograms, and timeline data.

    Args:
        config: The run configuration used.
        results: List of individual request results.
        total_elapsed_s: Total wall-clock time of the run in seconds.

    Returns:
        A fully populated RunReport.
    """
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    latencies = [r.latency_ms for r in results]

    latency_stats = compute_latency_stats(latencies) if latencies else LatencyStats(
        min_ms=0, max_ms=0, mean_ms=0, median_ms=0,
        p50_ms=0, p75_ms=0, p90_ms=0, p95_ms=0, p99_ms=0, stddev_ms=0,
    )

    errors = compute_error_breakdown(results)
    histogram_edges, histogram_counts = compute_histogram(latencies)
    timeline = compute_timeline(results)

    rps = len(results) / total_elapsed_s if total_elapsed_s > 0 else 0.0
    success_rps = len(successful) / total_elapsed_s if total_elapsed_s > 0 else 0.0
    total_bytes = sum(r.bytes_received for r in results)

    return RunReport(
        run_id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(timezone.utc).isoformat(),
        stresskit_version=__version__,
        config=config,
        total_requests=len(results),
        successful_requests=len(successful),
        failed_requests=len(failed),
        total_elapsed_s=round(total_elapsed_s, 4),
        requests_per_second=round(rps, 2),
        successful_rps=round(success_rps, 2),
        total_bytes=total_bytes,
        latency=latency_stats,
        errors=errors,
        timeline=timeline,
        histogram_buckets=histogram_edges,
        histogram_counts=histogram_counts,
        raw_results=results,
    )
