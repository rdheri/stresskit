# ⚡ StressKit

**Developer-friendly API load testing and performance profiling CLI.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/stresskit.svg)](https://pypi.org/project/stresskit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/rdheri/stresskit/actions/workflows/ci.yml/badge.svg)](https://github.com/rdheri/stresskit/actions)

StressKit takes an API endpoint, hammers it with configurable concurrent requests, and generates a clean, professional performance report — all from your terminal.

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

## Project Structure

```
stresskit/
├── pyproject.toml          # Package config, dependencies, CLI entry point
├── README.md
├── LICENSE
├── stresskit/
│   ├── __init__.py         # Version
│   ├── cli.py              # Typer CLI definitions and commands
│   ├── engine.py           # Async load testing engine (aiohttp)
│   ├── stats.py            # Statistics computation (percentiles, histograms)
│   ├── reporter.py         # Rich terminal output rendering
│   ├── exporter.py         # JSON/CSV export logic
│   ├── comparator.py       # Report comparison logic
│   ├── history.py          # SQLite history logging and retrieval
│   └── models.py           # Pydantic models for all data structures
├── tests/
│   ├── test_engine.py
│   ├── test_stats.py
│   ├── test_comparator.py
│   └── test_cli.py
└── .github/workflows/ci.yml
```

---

## Development

```bash
# Clone and install
git clone https://github.com/rdheri/stresskit.git
cd stresskit
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=stresskit --cov-report=term-missing

# Lint
ruff check stresskit/ tests/

# Type check
mypy stresskit/
```

---

## Creating a Demo Recording

Since StressKit is a CLI tool, the best way to showcase it is with a terminal recording:

### Option 1: asciinema (recommended)

```bash
# Install
pip install asciinema

# Record
asciinema rec stresskit-demo.cast

# Inside the recording, run:
stresskit run https://httpbin.org/get -c 20 -n 200

# Stop recording with Ctrl+D, then upload:
asciinema upload stresskit-demo.cast
```

Embed in README: `[![asciicast](https://asciinema.org/a/YOUR_ID.svg)](https://asciinema.org/a/YOUR_ID)`

### Option 2: terminalizer (GIF)

```bash
npm install -g terminalizer
terminalizer record stresskit-demo
# Run your commands, then Ctrl+D
terminalizer render stresskit-demo -o demo.gif
```

---

## Publishing to PyPI

```bash
# 1. Create accounts at https://pypi.org and https://test.pypi.org

# 2. Build the package
pip install build twine
python -m build

# 3. Upload to Test PyPI first
twine upload --repository testpypi dist/*

# 4. Test the install
pip install --index-url https://test.pypi.org/simple/ stresskit

# 5. Upload to production PyPI
twine upload dist/*
```

Or use the GitHub Actions workflow — just push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

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
