"""Cooldown tracking, global throttle, and identical-message dedupe."""
from __future__ import annotations

import time
from collections import deque
from typing import Deque


class Cooldowns:
    def __init__(self, global_min_interval: float, dedupe_window: float,
                 dedupe_ring_size: int = 32) -> None:
        self.global_min = float(global_min_interval)
        self.dedupe_window = float(dedupe_window)
        self._last_at: dict[str, float] = {}
        self._last_global: float | None = None
        self._recent: Deque[tuple[float, str]] = deque(maxlen=dedupe_ring_size)

    # ---- per-key gating ----
    def ready(self, key: str, min_interval: float, now: float | None = None) -> bool:
        if key not in self._last_at:
            return True
        n = time.monotonic() if now is None else now
        return (n - self._last_at[key]) >= float(min_interval)

    def mark(self, key: str, now: float | None = None) -> None:
        self._last_at[key] = time.monotonic() if now is None else now

    # ---- global throttle ----
    def global_ready(self, now: float | None = None) -> bool:
        if self._last_global is None:
            return True
        n = time.monotonic() if now is None else now
        return (n - self._last_global) >= self.global_min

    def mark_global(self, now: float | None = None) -> None:
        self._last_global = time.monotonic() if now is None else now

    # ---- identical-message dedupe ----
    def is_duplicate(self, message: str, now: float | None = None) -> bool:
        n = time.time() if now is None else now
        cutoff = n - self.dedupe_window
        # Drop expired entries lazily.
        while self._recent and self._recent[0][0] < cutoff:
            self._recent.popleft()
        return any(msg == message for _, msg in self._recent)

    def remember(self, message: str, now: float | None = None) -> None:
        n = time.time() if now is None else now
        self._recent.append((n, message))

    def should_send(self, key: str, min_interval: float, message: str) -> bool:
        """One-shot helper: per-key, global, and dedupe must all pass."""
        if not self.ready(key, min_interval):
            return False
        if not self.global_ready():
            return False
        if self.is_duplicate(message):
            return False
        return True

    def commit(self, key: str, message: str) -> None:
        self.mark(key)
        self.mark_global()
        self.remember(message)
