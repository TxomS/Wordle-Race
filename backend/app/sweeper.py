"""A background thread that runs one job every so often.

Here the job is removing abandoned games (GameService.cleanup). Running it on a timer,
and not only when someone happens to start a game, means abandoned games really do
disappear when the time limit says they should, even if nobody is using the app.
"""

import logging
import threading
from collections.abc import Callable

log = logging.getLogger("wordle")


class Sweeper:
    def __init__(self, job: Callable[[], object], interval_seconds: float) -> None:
        self._job = job
        self._interval = interval_seconds
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stopping.clear()
        # A daemon thread never keeps the process alive on its own.
        self._thread = threading.Thread(target=self._run, name="sweeper", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        # Event.wait() is both the sleep and the stop signal: it returns True as soon as
        # stop() is called, so shutting down never waits for a whole interval.
        while not self._stopping.wait(self._interval):
            try:
                self._job()
            except Exception:
                # One failed sweep (say the database was briefly busy) must not end all future ones.
                log.exception("background sweep failed")
