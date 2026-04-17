"""
Shared proactive Riot API rate limiter (inspired by Cassiopeia's approach).

Instead of sleeping a fixed interval and reacting to 429s, this tracker:
  1. Learns the actual limits from X-App-Rate-Limit response headers on first call
  2. Records every request timestamp (including scheduled future ones) in a sliding window
  3. Before each call, computes the exact sleep needed to stay within all limit windows
  4. Is a single global singleton — ingestion worker + live routes share it, so they
     can't collectively exceed the API key's budget.

Dev key defaults (used until first response):  20 req / 1s,  100 req / 120s
Production key limits are auto-detected from headers and replace the defaults.
"""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)

_DEFAULT_WINDOWS = [(20, 1.0), (100, 120.0)]  # dev key


class _SlidingWindowLimiter:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._windows: list[tuple[int, float]] = list(_DEFAULT_WINDOWS)
        self._call_times: list[float] = []   # monotonic timestamps (including future)
        self._limits_confirmed = False

    def update_from_headers(self, headers) -> None:
        """Parse X-App-Rate-Limit header once and replace defaults with real limits."""
        if self._limits_confirmed:
            return
        raw = headers.get("X-App-Rate-Limit") or headers.get("x-app-rate-limit")
        if not raw:
            return
        try:
            windows = []
            for part in raw.split(","):
                count_s, secs_s = part.strip().split(":")
                windows.append((int(count_s), float(secs_s)))
            self._windows = windows
            self._limits_confirmed = True
            logger.info("Rate limiter confirmed from Riot headers: %s", windows)
        except Exception:
            pass

    async def acquire(self) -> None:
        """Block until one more request fits within all rate-limit windows."""
        async with self._lock:
            now = time.monotonic()
            max_window = max(w for _, w in self._windows)

            # Expire entries older than the largest window
            self._call_times = [t for t in self._call_times if now - t < max_window]

            sleep_needed = 0.0
            for max_req, window_secs in self._windows:
                in_window = [t for t in self._call_times if now - t < window_secs]
                if len(in_window) >= max_req:
                    # Oldest entry in this window will expire at: in_window[0] + window_secs
                    wait = (in_window[0] + window_secs) - now + 0.05
                    sleep_needed = max(sleep_needed, wait)

            # Reserve the slot at the time we'll actually send the request
            self._call_times.append(now + sleep_needed)
            self._call_times.sort()

        if sleep_needed > 0:
            logger.debug("Rate limiter sleeping %.2fs to stay within limits", sleep_needed)
            await asyncio.sleep(sleep_needed)


# ── Global singleton ──────────────────────────────────────────────────────────

_limiter = _SlidingWindowLimiter()


async def acquire() -> None:
    await _limiter.acquire()


def update_from_response(response) -> None:
    try:
        _limiter.update_from_headers(response.headers)
    except Exception:
        pass
