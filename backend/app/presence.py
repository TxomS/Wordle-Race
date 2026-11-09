"""Who has been seen recently: the "opponent disconnected" signal.

This is deliberately kept in memory and not in the database. It is a fact about
the last few seconds, not part of the game: writing it to disk on every poll
would turn every read into a write, and a stale value would be wrong anyway.

A player counts as connected if the server has heard from them (any request that
carries their token, so polling and guessing both count) less than `timeout`
seconds ago.

After a backend restart this memory is empty. Without a rule for that, both
players would flash as "disconnected" until their next poll. So a player who has
not been seen since startup is assumed present for one timeout window; players
who really left stop polling and show as disconnected once that window ends.
"""

import threading
import time
from collections.abc import Callable

_PRUNE_EVERY = 60  # seconds between clean-ups
_FORGET_AFTER = 3600  # entries older than this are dropped to keep memory small


class Presence:
    def __init__(self, timeout_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.timeout = timeout_seconds
        self._clock = clock  # tests pass a fake clock they can move forward
        self._started = clock()
        self._last_prune = self._started
        self._last_seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def touch(self, code: str, player_id: str) -> None:
        """Record that this player was just heard from."""
        now = self._clock()
        with self._lock:
            self._last_seen[(code, player_id)] = now
            if now - self._last_prune > _PRUNE_EVERY:
                cutoff = now - _FORGET_AFTER
                self._last_seen = {key: seen for key, seen in self._last_seen.items() if seen >= cutoff}
                self._last_prune = now

    def is_connected(self, code: str, player_id: str) -> bool:
        now = self._clock()
        last = self._last_seen.get((code, player_id))
        if last is None:
            return now - self._started < self.timeout  # not seen since startup: benefit of the doubt
        return now - last < self.timeout
