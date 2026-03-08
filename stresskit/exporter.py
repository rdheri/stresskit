"""Export logic for StressKit reports.

Supports exporting to:
- JSON: Full structured report with all metrics and metadata
- CSV: One row per request with timestamp, latency, status code, success
- Auto-save to ~/.stresskit/history/ with timestamp-based filenames
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from stresskit.models import RunReport

HISTORY_DIR = Path.home() / ".stresskit" / "history"


def ensure_history_dir() -> Path:
    """Create the history directory if it doesn't exist.

    Returns:
        Path to the history directory.
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def export_json(report: RunReport, path: Path | str) -> Path:
    """Export a report as a JSON file.

    Excludes raw_results from the JSON export to keep file size manageable.

    Args:
        report: The run report to export.
        path: Destination file path.

    Returns:
        The path to the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = report.model_dump(exclude={"raw_results"})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    return path


def export_csv(report: RunReport, path: Path | str) -> Path:
    """Export individual request results as a CSV file.

    Each row contains: timestamp, latency_ms, status_code, success, error.

    Args:
        report: The run report to export.
        path: Destination file path.

    Returns:
        The path to the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "latency_ms", "status_code", "success", "error"])
        for r in report.raw_results:
            writer.writerow([r.timestamp, r.latency_ms, r.status_code, r.success, r.error or ""])

    return path


def auto_save_report(report: RunReport) -> Path:
    """Auto-save report to the history directory with a timestamp filename.

    Args:
        report: The run report to save.

    Returns:
        Path to the saved JSON file.
    """
    ensure_history_dir()
    safe_ts = report.timestamp.replace(":", "-").replace("+", "_")
    filename = f"run_{safe_ts}_{report.run_id}.json"
    return export_json(report, HISTORY_DIR / filename)


def load_report_json(path: Path | str) -> RunReport:
    """Load a RunReport from a JSON file.

    Args:
        path: Path to the JSON report file.

    Returns:
        The deserialized RunReport.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return RunReport(**data)
