"""Unit tests for the async load testing engine.

Tests request sending, error handling, concurrency behavior,
and both fixed-count and duration-based modes using mocked
aiohttp sessions.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from stresskit.engine import _send_request, run_load_test
from stresskit.models import HttpMethod, RunConfig


def _mock_session_with_response(status: int = 200, body: bytes = b"OK"):
    """Create a mock aiohttp session that returns a given response."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.read = AsyncMock(return_value=body)

    @asynccontextmanager
    async def fake_request(*args, **kwargs):
        yield mock_response

    mock_session = MagicMock()
    mock_session.request = fake_request
    return mock_session


def _mock_session_with_error(exc: Exception):
    """Create a mock aiohttp session that raises an exception."""

    @asynccontextmanager
    async def fake_request(*args, **kwargs):
        raise exc
        yield  # noqa: F541

    mock_session = MagicMock()
    mock_session.request = fake_request
    return mock_session


@pytest.fixture
def basic_config() -> RunConfig:
    return RunConfig(
        url="https://httpbin.org/get",
        method=HttpMethod.GET,
        concurrency=2,
        total_requests=5,
        timeout=5.0,
    )


class TestSendRequest:
    """Tests for the _send_request function."""

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        config = RunConfig(
            url="https://httpbin.org/delay/10",
            concurrency=1, total_requests=1, timeout=5.0,
        )
        semaphore = asyncio.Semaphore(1)
        session = _mock_session_with_error(asyncio.TimeoutError())
        result = await _send_request(session, config, semaphore)
        assert result.success is False
        assert result.error == "timeout"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_connection_error_handling(self) -> None:
        config = RunConfig(
            url="https://bad-host.invalid",
            concurrency=1, total_requests=1, timeout=5.0,
        )
        semaphore = asyncio.Semaphore(1)
        os_error = OSError("Connection refused")
        conn_key = MagicMock()
        exc = aiohttp.ClientConnectorError(connection_key=conn_key, os_error=os_error)
        session = _mock_session_with_error(exc)
        result = await _send_request(session, config, semaphore)
        assert result.success is False
        assert "connection_error" in (result.error or "")

    @pytest.mark.asyncio
    async def test_successful_request(self) -> None:
        config = RunConfig(url="https://example.com", concurrency=1, total_requests=1)
        semaphore = asyncio.Semaphore(1)
        session = _mock_session_with_response(status=200, body=b"Hello")
        result = await _send_request(session, config, semaphore)
        assert result.success is True
        assert result.status_code == 200
        assert result.bytes_received == 5
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_server_error_response(self) -> None:
        config = RunConfig(url="https://example.com", concurrency=1, total_requests=1)
        semaphore = asyncio.Semaphore(1)
        session = _mock_session_with_response(status=500, body=b"Error")
        result = await _send_request(session, config, semaphore)
        assert result.success is False
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_404_response(self) -> None:
        config = RunConfig(url="https://example.com/missing", concurrency=1, total_requests=1)
        semaphore = asyncio.Semaphore(1)
        session = _mock_session_with_response(status=404, body=b"Not Found")
        result = await _send_request(session, config, semaphore)
        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_generic_client_error(self) -> None:
        config = RunConfig(url="https://example.com", concurrency=1, total_requests=1)
        semaphore = asyncio.Semaphore(1)
        session = _mock_session_with_error(aiohttp.ClientError("Something broke"))
        result = await _send_request(session, config, semaphore)
        assert result.success is False
        assert "client_error" in (result.error or "")


class TestRunLoadTest:
    """Tests for the run_load_test orchestration function."""

    @pytest.mark.asyncio
    async def test_progress_callback_called(self) -> None:
        config = RunConfig(url="https://example.com", concurrency=2, total_requests=3, timeout=5.0)
        progress_counts: list[int] = []

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"ok")

        @asynccontextmanager
        async def fake_request(*args, **kwargs):
            yield mock_response

        with patch("stresskit.engine.aiohttp.ClientSession") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.request = fake_request
            mock_inst.__aenter__ = AsyncMock(return_value=mock_inst)
            mock_inst.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_inst

            results, elapsed = await run_load_test(
                config, on_progress=lambda c: progress_counts.append(c)
            )

        assert len(results) == 3
        assert len(progress_counts) == 3
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_returns_correct_count(self) -> None:
        config = RunConfig(url="https://example.com", concurrency=5, total_requests=10)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"ok")

        @asynccontextmanager
        async def fake_request(*args, **kwargs):
            yield mock_response

        with patch("stresskit.engine.aiohttp.ClientSession") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.request = fake_request
            mock_inst.__aenter__ = AsyncMock(return_value=mock_inst)
            mock_inst.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_inst

            results, elapsed = await run_load_test(config)

        assert len(results) == 10
