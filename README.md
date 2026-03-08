# ⚡ StressKit

**Developer-friendly API load testing and performance profiling CLI.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/stresskit.svg)](https://pypi.org/project/stresskit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/rdheri/stresskit/actions/workflows/ci.yml/badge.svg)](https://github.com/rdheri/stresskit/actions)

StressKit takes an API endpoint, hammers it with configurable concurrent requests, and generates a clean, professional performance report — all from your terminal.

[![StressKit Demo](https://asciinema.org/a/Aeh8BHoBuIaB4Vau.svg)](https://asciinema.org/a/Aeh8BHoBuIaB4Vau)

---

## Why StressKit?

- **Better UX than `wrk` or `hey`** — color-coded terminal output, latency histograms, throughput sparklines, and exportable reports out of the box.
- **Built for developer workflows** — auto-saves every run to local history, supports JSON/CSV export, and lets you compare runs with `stresskit compare` to catch regressions before deploying.
- **Truly async** — uses `asyncio` + `aiohttp` with proper connection pooling for accurate, high-concurrency load generation. Not threads. Not forks.

---

## Installation

```bash
pip install stresskit
```

Or install from source:

```bash
git clone https://github.com/rdheri/stresskit.git
cd stresskit
pip install -e ".[dev]"
```

---

## Quick Start

### Basic GET test (100 requests, 10 concurrent workers)

```bash
stresskit run https://httpbin.org/get
```

### POST with custom headers and body

```bash
stresskit run https://httpbin.org/post \
  -m POST \
  -H "Authorization: Bearer token123" \
  -H "Content-Type: application/json" \
  -b '{"user": "test", "action": "create"}' \
  -c 20 -n 500
```

### Duration-based test (run for 30 seconds)

```bash
stresskit run https://api.example.com/health -d 30 -c 50
```

### Export results

```bash
stresskit run https://httpbin.org/get -o report.json
stresskit run https://httpbin.org/get -o results.csv
```

---

## Example Output

```
⚡ StressKit v1.0.0
  Target:      https://httpbin.org/get
  Method:      GET
  Concurrency: 10
  Requests:    100

╭──────────────────────────────────────────────╮
│ StressKit Report  •  2025-03-15T14:32:01Z    │
╰──────────────────────────────────────────────╯

         Overview
┌──────────────────┬───────────┐
│ URL              │ httpbin…  │
│ Method           │ GET       │
│ Concurrency      │ 10        │
│ Total Requests   │ 100       │
│ Successful       │ 100       │
│ Failed           │ 0         │
│ Elapsed Time     │ 2.34s     │
│ Throughput       │ 42.7 req/s│
└──────────────────┴───────────┘

           Latency
┌──────────────┬────────────┐
│ Min          │  45.21 ms  │  ← green
│ Max          │ 312.87 ms  │  ← yellow
│ Mean         │  98.43 ms  │  ← green
│ Median (p50) │  89.12 ms  │
│ p90          │ 178.56 ms  │
│ p95          │ 234.89 ms  │  ← yellow
│ p99          │ 298.34 ms  │
│ Std Dev      │  52.31 ms  │
└──────────────┴────────────┘

Latency Distribution
   45.2 -   71.9 ms │ ████████████████████ 28
   71.9 -   98.7 ms │ ████████████████████████████ 35
   98.7 -  125.4 ms │ ██████████████ 18
  125.4 -  152.1 ms │ ████████ 9
  178.9 -  312.9 ms │ ████ 5

Throughput Timeline (req/s per second)
  ▃▅▇█▇▆▅▇█▆  (peak: 52 req/s)
```

---

## CLI Reference

### `stresskit run <URL>`

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--method` | `-m` | HTTP method (GET, POST, PUT, DELETE, PATCH) | `GET` |
| `--concurrency` | `-c` | Number of concurrent workers | `10` |
| `--requests` | `-n` | Total number of requests | `100` |
| `--duration` | `-d` | Run for N seconds (overrides `--requests`) | — |
| `--header` | `-H` | Custom header, repeatable (`"Key: Value"`) | — |
| `--body` | `-b` | JSON request body | — |
| `--timeout` | `-t` | Request timeout in seconds | `30` |
| `--output` | `-o` | Export to `.json` or `.csv` file | — |
| `--compare` | — | Path to previous JSON report for delta comparison | — |
| `--threshold-good` | — | Latency threshold for green (ms) | `200` |
| `--threshold-warn` | — | Latency threshold for yellow/red (ms) | `500` |

### `stresskit compare <file1.json> <file2.json>`

Loads two saved JSON reports and displays a side-by-side comparison table:

```bash
stresskit compare before.json after.json
```

```
╭──────────────────────────────────────────────╮
│ StressKit Comparison                          │
╰──────────────────────────────────────────────╯

                    Performance Delta
┌─────────────────┬─────────┬─────────┬─────────┬──────────┐
│ Metric          │ before  │ after   │ Delta   │ % Change │
├─────────────────┼─────────┼─────────┼─────────┼──────────┤
│ Requests/sec    │  42.70  │  67.30  │ ▲ 24.60 │ ▲ 57.6%  │  ← green
│ Mean Latency    │  98.43  │  62.18  │ ▼ 36.25 │ ▼ 36.8%  │  ← green
│ p95 Latency     │ 234.89  │ 145.32  │ ▼ 89.57 │ ▼ 38.1%  │  ← green
│ Failed Requests │   0.00  │   3.00  │ ▲  3.00 │ ▲  —     │  ← red
└─────────────────┴─────────┴─────────┴─────────┴──────────┘
```

### `stresskit history`

```bash
stresskit history --limit 10
```

Shows past runs from the local SQLite database at `~/.stresskit/runs.db`.

---

## Metrics Reference

**Latency**: min, max, mean, median, p50, p75, p90, p95, p99, standard deviation

**Throughput**: total requests/second, successful requests/second

**Errors**: HTTP status code breakdown, timeout count, connection error count

**Timeline**: per-second throughput shown as a Unicode sparkline

**Histogram**: latency distribution rendered as a color-coded horizontal bar chart

---

## Architecture

```
stresskit/
├── pyproject.toml          # Package config, dependencies, CLI entry point
├── stresskit/
│   ├── __init__.py         # Version
│   ├── cli.py              # Typer CLI — command definitions, argument parsing, progress bar
│   ├── engine.py           # Async load engine — aiohttp workers, connection pooling, timing
│   ├── stats.py            # Statistics — percentiles, histograms, timeline bucketing
│   ├── reporter.py         # Rich terminal renderer — tables, charts, sparklines, color-coding
│   ├── exporter.py         # JSON/CSV export and auto-save to ~/.stresskit/history/
│   ├── comparator.py       # Report comparison — delta computation, improvement detection
│   ├── history.py          # SQLite logging — run summaries persisted across sessions
│   └── models.py           # Pydantic models — RunConfig, RequestResult, RunReport, etc.
├── tests/
│   ├── test_engine.py      # Async engine tests with mocked aiohttp sessions
│   ├── test_stats.py       # Percentile, histogram, timeline, and report builder tests
│   ├── test_comparator.py  # Delta computation and file comparison tests
│   └── test_cli.py         # CLI integration tests via typer.testing.CliRunner
└── .github/workflows/
    └── ci.yml              # Lint, test, publish on Python 3.10/3.11/3.12
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| CLI Framework | [Typer](https://typer.tiangolo.com/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| HTTP Engine | [aiohttp](https://docs.aiohttp.org/) + asyncio |
| Data Models | [Pydantic v2](https://docs.pydantic.dev/) |
| History Store | SQLite3 |
| Testing | pytest + pytest-asyncio |
| Linting | Ruff |
| CI/CD | GitHub Actions |

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest tests/ -v`)
5. Lint your code (`ruff check .`)
6. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.