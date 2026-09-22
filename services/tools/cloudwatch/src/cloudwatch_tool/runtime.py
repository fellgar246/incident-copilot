"""Timeout and bounded retry for a single read-only tool call."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from cloudwatch_tool.errors import ToolRetriesExhausted, ToolTimeoutError, TransientToolError

LOGGER = logging.getLogger("cloudwatch_tool")
MAX_ATTEMPTS = 3


def bounded_call[T](fn: Callable[[], T], *, timeout_seconds: float, attempts: int) -> T:
    """Run `fn` with a timeout. Only transient failures are retried, and only up to `attempts`."""
    if attempts < 1 or attempts > MAX_ATTEMPTS:
        raise ValueError(f"attempts must be between 1 and {MAX_ATTEMPTS}")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _run_once(fn, timeout_seconds)
        except (ToolTimeoutError, TransientToolError) as exc:
            last = exc
            LOGGER.warning(
                "tool.call.retry",
                extra={
                    "fields": {
                        "attempt": attempt,
                        "attempts": attempts,
                        "error": type(exc).__name__,
                    }
                },
            )
    if last is None:
        raise RuntimeError("tool retry loop exited without an error")
    raise ToolRetriesExhausted(f"tool call failed after {attempts} attempts: {last}") from last


def _run_once[T](fn: Callable[[], T], timeout_seconds: float) -> T:
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tool-call")
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise ToolTimeoutError(f"tool call exceeded {timeout_seconds} seconds") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
