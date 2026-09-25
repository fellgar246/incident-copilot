"""Strict timeout for one remediation write. Failures are not retried."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError


class RemediationTimeoutError(TimeoutError):
    """The safe write exceeded its deadline and was not retried."""


def run_once[T](fn: Callable[[], T], *, timeout_seconds: float) -> T:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="remediation")
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise RemediationTimeoutError(f"remediation exceeded {timeout_seconds} seconds") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
