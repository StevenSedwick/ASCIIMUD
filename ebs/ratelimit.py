"""Simple monotonic-clock token bucket. Not thread-safe; fine for asyncio."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    rate: float        # tokens per second
    capacity: float    # max tokens
    _tokens: float = 0.0
    _last: float = 0.0

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._last = time.monotonic()

    def take(self, n: float = 1.0) -> bool:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False
