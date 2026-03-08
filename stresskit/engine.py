"""Async load testing engine using aiohttp.

Provides the core load generation logic:
- Configurable concurrent workers via asyncio semaphores
- Accurate per-request timing with time.perf_counter()
- Connection pooling with aiohttp.TCPConnector
- Graceful error handling for timeouts, connection failures, and HTTP errors
- Real-time progress reporting via callback
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import aiohttp

from stresskit.models import RequestResult, RunConfig


async def _send_request(
    session: aiohttp.ClientSession,
    config: RunConfig,
    semaphore: asyncio.Semaphore,
) -> RequestResult:
    """Send a single HTTP request and capture the result.

    Args:
        session: aiohttp client session with connection pooling.
        config: Run configuration with URL, method, headers, etc.
        semaphore: Concurrency limiter.

    Returns:
        RequestResult with timing, status, and error information.
    """
    async with semaphore:
        timestamp = time.time()
        start = time.perf_counter()

        try:
            async with session.request(
                method=config.method.value,
                url=config.url,
                headers=config.headers or None,
                data=config.body,
                timeout=aiohttp.ClientTimeout(total=config.timeout),
            ) as response:
                body = await response.read()
                elapsed_ms = (time.perf_counter() - start) * 1000.0

                return RequestResult(
                    timestamp=timestamp,
                    latency_ms=round(elapsed_ms, 3),
                    status_code=response.status,
                    success=200 <= response.status < 300,
                    bytes_received=len(body),
                )

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                latency_ms=round(elapsed_ms, 3),
                success=False,
                error="timeout",
            )
        except aiohttp.ClientConnectorError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                latency_ms=round(elapsed_ms, 3),
                success=False,
                error=f"connection_error: {exc}",
            )
        except aiohttp.ClientError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                latency_ms=round(elapsed_ms, 3),
                success=False,
                error=f"client_error: {exc}",
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                latency_ms=round(elapsed_ms, 3),
                success=False,
                error=f"unexpected: {type(exc).__name__}: {exc}",
            )


async def run_load_test(
    config: RunConfig,
    on_progress: Callable[[int], None] | None = None,
) -> tuple[list[RequestResult], float]:
    """Execute a load test according to the given configuration.

    Supports two modes:
    1. Fixed request count: sends exactly `config.total_requests` requests.
    2. Duration-based: sends requests continuously for `config.duration` seconds.

    Args:
        config: Load test configuration.
        on_progress: Optional callback invoked after each completed request with the
            cumulative count so far.

    Returns:
        A tuple of (list of RequestResults, total elapsed seconds).
    """
    semaphore = asyncio.Semaphore(config.concurrency)
    connector = aiohttp.TCPConnector(
        limit=config.concurrency,
        limit_per_host=config.concurrency,
        enable_cleanup_closed=True,
    )

    results: list[RequestResult] = []
    wall_start = time.perf_counter()

    async with aiohttp.ClientSession(connector=connector) as session:
        if config.duration is not None:
            # Duration-based mode: keep spawning requests until time expires
            results = await _run_duration_mode(
                session, config, semaphore, on_progress
            )
        else:
            # Fixed request count mode
            total = config.total_requests or 100
            tasks: list[asyncio.Task[RequestResult]] = []

            for _ in range(total):
                task = asyncio.create_task(_send_request(session, config, semaphore))
                tasks.append(task)

            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                if on_progress:
                    on_progress(len(results))

    wall_elapsed = time.perf_counter() - wall_start
    return results, round(wall_elapsed, 4)


async def _run_duration_mode(
    session: aiohttp.ClientSession,
    config: RunConfig,
    semaphore: asyncio.Semaphore,
    on_progress: Callable[[int], None] | None,
) -> list[RequestResult]:
    """Run requests continuously for a fixed duration.

    Args:
        session: aiohttp client session.
        config: Configuration with duration set.
        semaphore: Concurrency limiter.
        on_progress: Progress callback.

    Returns:
        List of all completed request results.
    """
    assert config.duration is not None
    duration = config.duration
    results: list[RequestResult] = []
    pending: set[asyncio.Task[RequestResult]] = set()
    start_time = time.perf_counter()

    while True:
        elapsed = time.perf_counter() - start_time
        if elapsed >= duration:
            break

        # Fill up to concurrency limit
        while len(pending) < config.concurrency:
            if time.perf_counter() - start_time >= duration:
                break
            task = asyncio.create_task(_send_request(session, config, semaphore))
            pending.add(task)

        if not pending:
            break

        # Wait for at least one task to complete
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            results.append(task.result())
            if on_progress:
                on_progress(len(results))

    # Wait for remaining in-flight requests
    if pending:
        done, _ = await asyncio.wait(pending)
        for task in done:
            results.append(task.result())
            if on_progress:
                on_progress(len(results))

    return results
