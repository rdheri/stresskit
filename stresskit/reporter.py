"""Rich terminal output rendering for StressKit reports.

Renders beautiful, color-coded terminal output including:
- Summary metrics table with latency color-coding
- Latency histogram as horizontal bar chart
- Status code distribution table
- Per-second throughput timeline (sparkline)
- Comparison delta table with directional arrows
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from stresskit.models import LatencyThresholds, RunReport

console = Console()

SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"


def _latency_color(value_ms: float, thresholds: LatencyThresholds) -> str:
    """Return a Rich color name based on latency thresholds.

    Args:
        value_ms: Latency value in milliseconds.
        thresholds: Color-coding thresholds.

    Returns:
        Rich color string: 'green', 'yellow', or 'red'.
    """
    if value_ms < thresholds.good_ms:
        return "green"
    elif value_ms < thresholds.warn_ms:
        return "yellow"
    return "red"


def _format_ms(value: float, thresholds: LatencyThresholds | None = None) -> Text:
    """Format a millisecond value with optional color-coding.

    Args:
        value: Latency in milliseconds.
        thresholds: Optional thresholds for color-coding.

    Returns:
        Rich Text object with formatted value.
    """
    text = f"{value:.2f} ms"
    if thresholds:
        color = _latency_color(value, thresholds)
        return Text(text, style=color)
    return Text(text)


def _sparkline(values: list[int]) -> str:
    """Render a list of integers as a Unicode sparkline string.

    Args:
        values: List of non-negative integers.

    Returns:
        Sparkline string using block characters.
    """
    if not values:
        return ""
    max_val = max(values) if max(values) > 0 else 1
    return "".join(
        SPARKLINE_CHARS[
            min(int(v / max_val * (len(SPARKLINE_CHARS) - 1)), len(SPARKLINE_CHARS) - 1)
        ]
        for v in values
    )


def render_report(
    report: RunReport,
    thresholds: LatencyThresholds | None = None,
) -> None:
    """Render a complete load test report to the terminal.

    Args:
        report: The RunReport to display.
        thresholds: Latency color thresholds (defaults applied if None).
    """
    if thresholds is None:
        thresholds = LatencyThresholds()

    console.print()

    # ── Header ──
    header = Text()
    header.append("StressKit Report", style="bold cyan")
    header.append(f"  •  {report.timestamp}", style="dim")
    console.print(Panel(header, border_style="cyan"))

    # ── Overview Table ──
    overview = Table(title="Overview", show_header=False, border_style="dim", pad_edge=False)
    overview.add_column("Metric", style="bold")
    overview.add_column("Value", justify="right")

    overview.add_row("URL", report.config.url)
    overview.add_row("Method", report.config.method.value)
    overview.add_row("Concurrency", str(report.config.concurrency))
    overview.add_row("Total Requests", str(report.total_requests))
    overview.add_row(
        "Successful",
        Text(str(report.successful_requests), style="green"),
    )
    overview.add_row(
        "Failed",
        Text(str(report.failed_requests), style="red" if report.failed_requests > 0 else "green"),
    )
    overview.add_row("Elapsed Time", f"{report.total_elapsed_s:.2f}s")
    overview.add_row("Throughput (total)", f"{report.requests_per_second:.1f} req/s")
    overview.add_row("Throughput (success)", f"{report.successful_rps:.1f} req/s")
    if report.total_bytes > 0:
        size_kb = report.total_bytes / 1024
        overview.add_row("Data Received", f"{size_kb:.1f} KB")

    console.print(overview)
    console.print()

    # ── Latency Table ──
    lat_table = Table(title="Latency", border_style="dim")
    lat_table.add_column("Metric", style="bold")
    lat_table.add_column("Value", justify="right")

    lat = report.latency
    for label, val in [
        ("Min", lat.min_ms),
        ("Max", lat.max_ms),
        ("Mean", lat.mean_ms),
        ("Median (p50)", lat.p50_ms),
        ("p75", lat.p75_ms),
        ("p90", lat.p90_ms),
        ("p95", lat.p95_ms),
        ("p99", lat.p99_ms),
        ("Std Dev", lat.stddev_ms),
    ]:
        lat_table.add_row(label, _format_ms(val, thresholds))

    console.print(lat_table)
    console.print()

    # ── Latency Histogram ──
    _render_histogram(report)

    # ── Status Code Distribution ──
    if report.errors.status_codes:
        _render_status_codes(report)

    # ── Error Summary ──
    if report.failed_requests > 0:
        _render_error_summary(report)

    # ── Timeline Sparkline ──
    if report.timeline:
        _render_timeline(report)

    console.print()


def _render_histogram(report: RunReport) -> None:
    """Render latency histogram as horizontal bar chart.

    Args:
        report: Report containing histogram data.
    """
    if not report.histogram_buckets or not report.histogram_counts:
        return

    max_count = max(report.histogram_counts) if report.histogram_counts else 1
    bar_width = 40

    console.print(Text("Latency Distribution", style="bold"))

    edges = report.histogram_buckets
    counts = report.histogram_counts

    for i, count in enumerate(counts):
        if count == 0:
            continue
        lo = edges[i]
        hi = edges[i + 1] if i + 1 < len(edges) else edges[-1]
        label = f"{lo:>8.1f} - {hi:<8.1f} ms"
        bar_len = int((count / max_count) * bar_width) if max_count > 0 else 0
        bar = "█" * bar_len

        # Color the bar
        midpoint = (lo + hi) / 2
        if midpoint < 200:
            color = "green"
        elif midpoint < 500:
            color = "yellow"
        else:
            color = "red"

        line = Text()
        line.append(label, style="dim")
        line.append(" │ ", style="dim")
        line.append(bar, style=color)
        line.append(f" {count}", style="dim")
        console.print(line)

    console.print()


def _render_status_codes(report: RunReport) -> None:
    """Render HTTP status code distribution table.

    Args:
        report: Report containing error breakdown.
    """
    sc_table = Table(title="Status Codes", border_style="dim")
    sc_table.add_column("Code", style="bold", justify="center")
    sc_table.add_column("Count", justify="right")
    sc_table.add_column("", justify="left")

    for code, count in sorted(report.errors.status_codes.items()):
        code_int = int(code)
        if 200 <= code_int < 300:
            style = "green"
            marker = "✓"
        elif 300 <= code_int < 400:
            style = "yellow"
            marker = "→"
        elif 400 <= code_int < 500:
            style = "red"
            marker = "✗"
        else:
            style = "bright_red"
            marker = "✗"
        sc_table.add_row(Text(code, style=style), str(count), Text(marker, style=style))

    console.print(sc_table)
    console.print()


def _render_error_summary(report: RunReport) -> None:
    """Render error category summary.

    Args:
        report: Report containing error breakdown.
    """
    err = report.errors
    err_table = Table(title="Errors", border_style="red", show_header=False)
    err_table.add_column("Type", style="bold red")
    err_table.add_column("Count", justify="right")

    if err.timeout_count > 0:
        err_table.add_row("Timeouts", str(err.timeout_count))
    if err.connection_error_count > 0:
        err_table.add_row("Connection Errors", str(err.connection_error_count))
    if err.other_error_count > 0:
        err_table.add_row("Other Errors", str(err.other_error_count))

    console.print(err_table)
    console.print()


def _render_timeline(report: RunReport) -> None:
    """Render per-second throughput timeline as sparkline.

    Args:
        report: Report containing timeline data.
    """
    counts = [b.request_count for b in report.timeline]
    spark = _sparkline(counts)

    console.print(Text("Throughput Timeline (req/s per second)", style="bold"))
    line = Text()
    line.append("  ")
    line.append(spark, style="cyan")
    line.append(f"  (peak: {max(counts)} req/s)", style="dim")
    console.print(line)
    console.print()


def render_comparison(
    report1: RunReport,
    report2: RunReport,
    label1: str = "Run 1",
    label2: str = "Run 2",
) -> None:
    """Render a side-by-side comparison of two reports with delta and percentage change.

    Improvements are shown in green, regressions in red.

    Args:
        report1: Baseline report.
        report2: Comparison report.
        label1: Display label for the first report.
        label2: Display label for the second report.
    """
    console.print()
    console.print(Panel(Text("StressKit Comparison", style="bold cyan"), border_style="cyan"))

    table = Table(title="Performance Delta", border_style="dim")
    table.add_column("Metric", style="bold")
    table.add_column(label1, justify="right")
    table.add_column(label2, justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("% Change", justify="right")

    # Define metrics: (name, value1, value2, lower_is_better)
    metrics: list[tuple[str, float, float, bool]] = [
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

    for name, v1, v2, lower_better in metrics:
        delta = v2 - v1
        pct = ((delta / v1) * 100) if v1 != 0 else 0.0

        # Determine if this change is an improvement
        improved = (delta < 0) if lower_better else (delta > 0)
        color = "green" if improved else ("red" if delta != 0 else "dim")
        arrow = "▼" if delta < 0 else ("▲" if delta > 0 else "─")

        delta_text = Text(f"{arrow} {abs(delta):.2f}", style=color)
        pct_text = Text(f"{arrow} {abs(pct):.1f}%", style=color)

        table.add_row(name, f"{v1:.2f}", f"{v2:.2f}", delta_text, pct_text)

    console.print(table)
    console.print()
