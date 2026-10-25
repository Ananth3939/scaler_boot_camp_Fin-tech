from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from time import monotonic

from finsight.models import ResearchResponse


class ResearchStore:
    """Bounded in-memory lookup for recent API results; entries expire after a short TTL."""

    def __init__(self, ttl_seconds: int, max_entries: int = 128) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("ttl_seconds and max_entries must be greater than zero")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[float, ResearchResponse]] = OrderedDict()
        self._lock = RLock()

    def put(self, result: ResearchResponse) -> None:
        with self._lock:
            self._purge_expired()
            self._entries[result.request_id] = (monotonic() + self._ttl_seconds, result)
            self._entries.move_to_end(result.request_id)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def get(self, request_id: str) -> ResearchResponse | None:
        with self._lock:
            self._purge_expired()
            entry = self._entries.get(request_id)
            if entry is None:
                return None
            self._entries.move_to_end(request_id)
            return entry[1]

    def _purge_expired(self) -> None:
        now = monotonic()
        expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
