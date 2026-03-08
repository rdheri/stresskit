"""Pydantic models for StressKit configuration, results, and reports.

Defines the core data structures used throughout the application:
- RunConfig: load test configuration parameters
- RequestResult: individual request outcome
- LatencyStats: computed latency percentiles and distribution
- ErrorBreakdown: categorized error counts
- TimeBucket: per-second throughput data
- RunReport: complete test run report with all metrics
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class HttpMethod(str, Enum):
    """Supported HTTP methods for load testing."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RunConfig(BaseModel):
    """Configuration for a single load test run."""

    url: str = Field(description="Target API endpoint URL")
    method: HttpMethod = Field(default=HttpMethod.GET, description="HTTP method")
    concurrency: int = Field(default=10, ge=1, description="Number of concurrent workers")
    total_requests: int | None = Field(default=100, ge=1, description="Total requests to send")
    duration: float | None = Field(
        default=None, ge=0.1, description="Run duration in seconds (overrides total_requests)"
    )
    headers: dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")
    body: str | None = Field(default=None, description="JSON request body")
    timeout: float = Field(default=30.0, ge=1.0, description="Request timeout in seconds")


class RequestResult(BaseModel):
    """Result of a single HTTP request."""

    timestamp: float = Field(description="Unix timestamp when request started")
    latency_ms: float = Field(description="Response latency in milliseconds")
    status_code: int | None = Field(default=None, description="HTTP status code (None if failed)")
    success: bool = Field(description="Whether the request completed successfully (2xx)")
    error: str | None = Field(default=None, description="Error message if request failed")
    bytes_received: int = Field(default=0, description="Response body size in bytes")


class LatencyStats(BaseModel):
    """Computed latency statistics from a set of request results."""

    min_ms: float = Field(description="Minimum latency in ms")
    max_ms: float = Field(description="Maximum latency in ms")
    mean_ms: float = Field(description="Mean latency in ms")
    median_ms: float = Field(description="Median (p50) latency in ms")
    p50_ms: float = Field(description="50th percentile latency")
    p75_ms: float = Field(description="75th percentile latency")
    p90_ms: float = Field(description="90th percentile latency")
    p95_ms: float = Field(description="95th percentile latency")
    p99_ms: float = Field(description="99th percentile latency")
    stddev_ms: float = Field(description="Standard deviation of latency")


class ErrorBreakdown(BaseModel):
    """Breakdown of errors by category."""

    status_codes: dict[str, int] = Field(
        default_factory=dict, description="Count of responses per HTTP status code"
    )
    timeout_count: int = Field(default=0, description="Number of timeout errors")
    connection_error_count: int = Field(default=0, description="Number of connection errors")
    other_error_count: int = Field(default=0, description="Number of other errors")


class TimeBucket(BaseModel):
    """Throughput data for a 1-second time bucket."""

    second: int = Field(description="Second offset from test start")
    request_count: int = Field(description="Requests completed in this bucket")
    success_count: int = Field(description="Successful requests in this bucket")
    avg_latency_ms: float = Field(description="Average latency in this bucket")


class RunReport(BaseModel):
    """Complete report for a load test run."""

    # Metadata
    run_id: str = Field(description="Unique identifier for this run")
    timestamp: str = Field(description="ISO 8601 timestamp of the run")
    stresskit_version: str = Field(description="StressKit version used")

    # Configuration
    config: RunConfig = Field(description="Run configuration")

    # Results summary
    total_requests: int = Field(description="Total requests sent")
    successful_requests: int = Field(description="Number of successful (2xx) requests")
    failed_requests: int = Field(description="Number of failed requests")
    total_elapsed_s: float = Field(description="Total wall-clock time in seconds")

    # Throughput
    requests_per_second: float = Field(description="Total requests / elapsed time")
    successful_rps: float = Field(description="Successful requests / elapsed time")
    total_bytes: int = Field(default=0, description="Total bytes received")

    # Latency
    latency: LatencyStats = Field(description="Latency statistics")

    # Errors
    errors: ErrorBreakdown = Field(description="Error breakdown")

    # Timeline
    timeline: list[TimeBucket] = Field(default_factory=list, description="Per-second throughput")

    # Histogram data (bucket edges and counts for rendering)
    histogram_buckets: list[float] = Field(
        default_factory=list, description="Histogram bucket edges in ms"
    )
    histogram_counts: list[int] = Field(
        default_factory=list, description="Count per histogram bucket"
    )

    # Raw results (excluded from JSON export by default for size)
    raw_results: list[RequestResult] = Field(
        default_factory=list, description="Individual request results"
    )


class LatencyThresholds(BaseModel):
    """Configurable thresholds for color-coding latency values."""

    good_ms: float = Field(default=200.0, description="Below this = green")
    warn_ms: float = Field(default=500.0, description="Below this = yellow, above = red")
