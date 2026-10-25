from __future__ import annotations

from collections.abc import Callable
from threading import Event, RLock
from time import monotonic
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """Small thread-safe in-memory cache that coalesces concurrent cache misses."""

    def __init__(self, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._ttl_seconds = ttl_seconds
        self._entries: dict[K, tuple[float, V]] = {}
        self._inflight: dict[K, Event] = {}
        self._lock = RLock()

    def get_or_set(self, key: K, loader: Callable[[], V]) -> V:
        while True:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None:
                    expires_at, value = entry
                    if expires_at > monotonic():
                        return value
                    del self._entries[key]

                wait_event = self._inflight.get(key)
                if wait_event is None:
                    wait_event = Event()
                    self._inflight[key] = wait_event
                    is_loader = True
                else:
                    is_loader = False

            if not is_loader:
                wait_event.wait()
                continue

            try:
                value = loader()
            except BaseException:
                with self._lock:
                    self._inflight.pop(key, None)
                    wait_event.set()
                raise

            with self._lock:
                self._entries[key] = (monotonic() + self._ttl_seconds, value)
                self._inflight.pop(key, None)
                wait_event.set()
            return value
