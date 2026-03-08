"""Typer CLI definitions and commands for StressKit.

Defines three main commands:
- `stresskit run <URL>`: Execute a load test against an API endpoint
- `stresskit compare <file1> <file2>`: Compare two saved JSON reports
- `stresskit history`: Display past runs from the local SQLite log
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from stresskit import __version__
from stresskit.comparator import compare_files
from stresskit.engine import run_load_test
from stresskit.exporter import auto_save_report, export_csv, export_json, load_report_json
from stresskit.history import get_history, log_run
from stresskit.models import HttpMethod, LatencyThresholds, RunConfig, RunReport
from stresskit.reporter import render_comparison, render_report
from stresskit.stats import build_report

app = typer.Typer(
    name="stresskit",
    help="Developer-friendly API load testing and performance profiling CLI.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def _parse_headers(raw_headers: list[str]) -> dict[str, str]:
    """Parse a list of 'Key: Value' header strings into a dictionary.

    Args:
        raw_headers: List of header strings in 'Key: Value' format.

    Returns:
        Dictionary of parsed headers.

    Raises:
        typer.BadParameter: If a header string is malformed.
    """
    headers: dict[str, str] = {}
    for h in raw_headers:
        if ":" not in h:
            raise typer.BadParameter(f"Invalid header format (expected 'Key: Value'): {h}")
        key, _, value = h.partition(":")
        headers[key.strip()] = value.strip()
    return headers


def _version_callback(value: bool) -> None:
    """Print version and exit when --version is passed."""
    if value:
        console.print(f"StressKit v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version", "-v", help="Show version and exit.",
            callback=_version_callback, is_eager=True,
        ),
    ] = None,
) -> None:
    """StressKit — Developer-friendly API load testing and performance profiling CLI."""


@app.command()
def run(
    url: Annotated[str, typer.Argument(help="Target API endpoint URL to load test.")],
    method: Annotated[
        HttpMethod, typer.Option("--method", "-m", help="HTTP method.")
    ] = HttpMethod.GET,
    concurrency: Annotated[
        int, typer.Option("--concurrency", "-c", help="Number of concurrent workers.", min=1)
    ] = 10,
    requests: Annotated[
        int, typer.Option("--requests", "-n", help="Total number of requests to send.", min=1)
    ] = 100,
    duration: Annotated[
        float | None,
        typer.Option(
            "--duration", "-d", min=0.1,
            help="Run for N seconds instead of fixed request count.",
        ),
    ] = None,
    headers: Annotated[
        list[str] | None,
        typer.Option("--header", "-H", help="Custom header (repeatable). Format: 'Key: Value'"),
    ] = None,
    body: Annotated[
        str | None,
        typer.Option("--body", "-b", help="JSON request body for POST/PUT/PATCH."),
    ] = None,
    timeout: Annotated[
        float, typer.Option("--timeout", "-t", help="Request timeout in seconds.", min=1.0)
    ] = 30.0,
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Export report to JSON or CSV file."),
    ] = None,
    compare: Annotated[
        str | None,
        typer.Option("--compare", help="Path to a previous JSON report for comparison."),
    ] = None,
    threshold_good: Annotated[
        float,
        typer.Option("--threshold-good", help="Latency threshold for green (ms)."),
    ] = 200.0,
    threshold_warn: Annotated[
        float,
        typer.Option("--threshold-warn", help="Latency threshold for yellow/red boundary (ms)."),
    ] = 500.0,
) -> None:
    """Run a load test against an API endpoint.

    Sends concurrent HTTP requests to the given URL and generates a
    performance report with latency statistics, throughput metrics,
    error breakdown, and optional comparison against a previous run.
    """
    parsed_headers = _parse_headers(headers or [])

    config = RunConfig(
        url=url,
        method=method,
        concurrency=concurrency,
        total_requests=None if duration else requests,
        duration=duration,
        headers=parsed_headers,
        body=body,
        timeout=timeout,
    )

    thresholds = LatencyThresholds(good_ms=threshold_good, warn_ms=threshold_warn)

    # Display test configuration
    console.print()
    console.print(Text("⚡ StressKit", style="bold cyan"), Text(f"v{__version__}", style="dim"))
    console.print(f"  Target:      {url}")
    console.print(f"  Method:      {method.value}")
    console.print(f"  Concurrency: {concurrency}")
    if duration:
        console.print(f"  Duration:    {duration}s")
    else:
        console.print(f"  Requests:    {requests}")
    console.print()

    # Run the load test with progress bar
    try:
        results, elapsed = _run_with_progress(config, duration, requests)
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user.[/yellow]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"\n[red]Error during load test: {exc}[/red]")
        raise typer.Exit(1)

    if not results:
        console.print("[red]No results collected. Check the URL and try again.[/red]")
        raise typer.Exit(1)

    # Build and render report
    report = build_report(config, results, elapsed)
    render_report(report, thresholds)

    # Auto-save and log to history
    try:
        saved_path = auto_save_report(report)
        log_run(report)
        console.print(f"[dim]Report saved to {saved_path}[/dim]")
    except Exception as exc:
        console.print(f"[yellow]Warning: Could not save report: {exc}[/yellow]")

    # Export if requested
    if output:
        _handle_export(report, output)

    # Compare if requested
    if compare:
        _handle_compare(report, compare)


def _run_with_progress(
    config: RunConfig, duration: float | None, requests: int
) -> tuple[list, float]:
    """Execute the load test with a Rich progress bar.

    Args:
        config: Run configuration.
        duration: Duration in seconds (if duration-based mode).
        requests: Total request count (if count-based mode).

    Returns:
        Tuple of (results list, elapsed seconds).
    """
    results_ref: list = []
    elapsed_ref: list[float] = []

    if duration:
        desc = f"Running for {duration}s"
        total = None
    else:
        desc = f"Sending {requests} requests"
        total = requests

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(desc, total=total)

        def on_progress(count: int) -> None:
            if total:
                progress.update(task_id, completed=count)
            else:
                progress.update(task_id, description=f"{desc} ({count} done)")

        loop = asyncio.new_event_loop()
        try:
            r, e = loop.run_until_complete(run_load_test(config, on_progress))
            results_ref.extend(r)
            elapsed_ref.append(e)
        finally:
            loop.close()

        if total:
            progress.update(task_id, completed=total)

    return results_ref, elapsed_ref[0]


def _handle_export(report: RunReport, output: str) -> None:
    """Export a report to the specified file.

    Args:
        report: Report to export.
        output: File path. Extension determines format (.csv or .json).
    """
    out_path = Path(output)
    if out_path.suffix.lower() == ".csv":
        export_csv(report, out_path)
        console.print(f"[green]CSV exported to {out_path}[/green]")
    else:
        if not out_path.suffix:
            out_path = out_path.with_suffix(".json")
        export_json(report, out_path)
        console.print(f"[green]JSON exported to {out_path}[/green]")


def _handle_compare(report: RunReport, compare_path: str) -> None:
    """Compare the current report against a previous one.

    Args:
        report: Current run report.
        compare_path: Path to a previous JSON report.
    """
    try:
        previous = load_report_json(compare_path)
        render_comparison(previous, report, label1="Previous", label2="Current")
    except FileNotFoundError:
        console.print(f"[red]Comparison file not found: {compare_path}[/red]")
    except Exception as exc:
        console.print(f"[red]Error loading comparison report: {exc}[/red]")


@app.command()
def compare(
    file1: Annotated[str, typer.Argument(help="Path to baseline JSON report.")],
    file2: Annotated[str, typer.Argument(help="Path to comparison JSON report.")],
) -> None:
    """Compare two saved StressKit JSON reports side by side.

    Shows a delta table with metric name, values from both runs,
    absolute delta, and percentage change. Improvements are shown
    in green, regressions in red.
    """
    try:
        r1, r2, deltas = compare_files(file1, file2)
        render_comparison(r1, r2, label1=Path(file1).name, label2=Path(file2).name)
    except FileNotFoundError as exc:
        console.print(f"[red]File not found: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Error comparing reports: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def history(
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Number of runs to show.", min=1)
    ] = 20,
) -> None:
    """Show past runs from the local SQLite history log.

    Displays a table with key metrics from each saved run,
    ordered by most recent first.
    """
    runs = get_history(limit=limit)

    if not runs:
        console.print("[dim]No run history found. Run a load test first![/dim]")
        return

    table = Table(title=f"Run History (last {limit})", border_style="dim")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Timestamp", style="dim")
    table.add_column("URL", max_width=40, overflow="ellipsis")
    table.add_column("Method", justify="center")
    table.add_column("Reqs", justify="right")
    table.add_column("OK", justify="right", style="green")
    table.add_column("Fail", justify="right", style="red")
    table.add_column("RPS", justify="right")
    table.add_column("Mean (ms)", justify="right")
    table.add_column("p95 (ms)", justify="right")

    for r in runs:
        table.add_row(
            str(r["id"]),
            str(r["timestamp"])[:19],
            str(r["url"]),
            str(r["method"]),
            str(r["total_requests"]),
            str(r["successful_requests"]),
            str(r["failed_requests"]),
            f"{r['rps']:.1f}",
            f"{r['mean_latency_ms']:.1f}",
            f"{r['p95_latency_ms']:.1f}",
        )

    console.print(table)
