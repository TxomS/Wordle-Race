"""Who has been seen recently: the "opponent disconnected" signal, and the check that
keeps a game alive while someone still has it open.

This is deliberately kept in memory and not in the database. It is a fact about the
last few seconds or minutes, not part of the game: writing it to disk on every poll
would turn every read into a write, and a stale value would be wrong anyway.

A player counts as seen if the server has heard from them (any request that carries
their token, so polling and guessing both count) less than a given time ago.

After a backend restart this memory is empty. Without a rule for that, everyone would
look absent until their next poll: both players would flash as "disconnected", and a
cleanup could delete a game a player is looking at right now. So a player who has not
been seen since startup gets the benefit of the doubt for one window (the same length
as the question being asked); people who really left stop polling and count as absent
once that window ends.
"""

import threading
import time
from collections.abc import Callable

_PRUNE_EVERY = 60  # seconds between clean-ups of this memory
_REMEMBER_FOR = 3600  # by default, entries older than this are dropped to keep memory small


class Presence:
    def __init__(
        self,
        timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        remember_seconds: float = _REMEMBER_FOR,
    ) -> None:
        self.timeout = timeout_seconds  # silence longer than this shows as "disconnected"
        self._clock = clock  # tests pass a fake clock they can move forward
        self._remember = remember_seconds  # must be at least as long as any window we are asked about
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
                cutoff = now - self._remember
                self._last_seen = {key: seen for key, seen in self._last_seen.items() if seen >= cutoff}
                self._last_prune = now

    def seen_within(self, code: str, player_id: str, seconds: float) -> bool:
        """Has this player been heard from less than `seconds` ago?"""
        now = self._clock()
        last = self._last_seen.get((code, player_id))
        if last is None:
            return now - self._started < seconds  # not seen since startup: benefit of the doubt
        return now - last < seconds

    def is_connected(self, code: str, player_id: str) -> bool:
        return self.seen_within(code, player_id, self.timeout)
