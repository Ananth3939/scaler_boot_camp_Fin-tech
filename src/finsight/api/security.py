from __future__ import annotations

from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """A bounded per-client sliding-window limiter for one local API process."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        max_clients: int = 10_000,
    ) -> None:
        if max_requests <= 0 or window_seconds <= 0 or max_clients <= 0:
            raise ValueError("rate limit, window, and max_clients must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_clients = max_clients
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def retry_after(self, client_key: str) -> int | None:
        now = monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            expired = [
                key
                for key, timestamps in self._requests.items()
                if not timestamps or timestamps[-1] <= cutoff
            ]
            for key in expired:
                self._requests.pop(key, None)

            bucket = self._requests.get(client_key)
            if bucket is None:
                while len(self._requests) >= self._max_clients:
                    self._requests.popitem(last=False)
                bucket = deque()
                self._requests[client_key] = bucket
            else:
                self._requests.move_to_end(client_key)

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                return max(1, ceil(bucket[0] + self._window_seconds - now))
            bucket.append(now)
            return None
