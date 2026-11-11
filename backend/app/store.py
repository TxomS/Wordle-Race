"""SQLite persistence.

One table, one row per game. The whole Game is stored as JSON in `data`; `status`
and `updated_at` are separate columns so old games can be found and cleaned up.

Every change to a game happens inside write(), which opens its transaction with
BEGIN IMMEDIATE. SQLite lets only one writer in at a time, so two requests that
change the same game are applied strictly one after the other: the second one
waits, then loads the game the first one saved. That is what makes "who solved
first" a well-defined question (see rules.submit_guess).

Reads (read()) never take that lock, so polling does not slow down guessing.
"""

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from app.rules import Game, Guess, Player

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    code TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS games_updated_at ON games (updated_at);
"""


def _dump(game: Game) -> str:
    return json.dumps(asdict(game))


def _load(text: str) -> Game:
    raw = json.loads(text)
    players = [
        Player(id=p["id"], guesses=[Guess(**guess) for guess in p["guesses"]])
        for p in raw["players"]
    ]
    return Game(
        code=raw["code"],
        answer=raw["answer"],
        mode=raw["mode"],
        players=players,
        status=raw["status"],
        winner_id=raw["winner_id"],
        next_seq=raw["next_seq"],
    )


class GameStore:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        # isolation_level=None: we issue BEGIN / COMMIT ourselves.
        # timeout: how long a writer waits for the previous writer to finish.
        return sqlite3.connect(self.path, timeout=5, isolation_level=None)

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """A transaction that holds the write lock from the start. Commits when the
        block ends normally; rolls everything back if the block raises."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def load(self, conn: sqlite3.Connection, code: str) -> Game | None:
        row = conn.execute("SELECT data FROM games WHERE code = ?", (code,)).fetchone()
        return None if row is None else _load(row[0])

    def insert(self, conn: sqlite3.Connection, game: Game) -> bool:
        """Add a new game. Returns False if that code is already taken."""
        try:
            conn.execute(
                "INSERT INTO games (code, data, status, updated_at) VALUES (?, ?, ?, ?)",
                (game.code, _dump(game), game.status, time.time()),
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def list_idle(self, conn: sqlite3.Connection, cutoff: float, status: str) -> list[Game]:
        """Every game with this status that was last changed before `cutoff` (a Unix
        timestamp). Only guesses and joins count as a change; merely polling a game does not."""
        rows = conn.execute("SELECT data FROM games WHERE updated_at < ? AND status = ?", (cutoff, status))
        return [_load(row[0]) for row in rows.fetchall()]

    def list_waiting(self, conn: sqlite3.Connection) -> list[tuple[Game, float]]:
        """Every lobby (a race waiting for its second player), with the time it was created
        as a Unix timestamp. Nothing changes a lobby until someone joins, so the time it was
        last changed is the time it was created."""
        rows = conn.execute("SELECT data, updated_at FROM games WHERE status = 'waiting'").fetchall()
        return [(_load(data), created) for data, created in rows]

    def delete(self, conn: sqlite3.Connection, codes: list[str]) -> int:
        """Delete these games. Returns how many were asked for."""
        conn.executemany("DELETE FROM games WHERE code = ?", [(code,) for code in codes])
        return len(codes)

    def save(self, conn: sqlite3.Connection, game: Game) -> None:
        conn.execute(
            "UPDATE games SET data = ?, status = ?, updated_at = ? WHERE code = ?",
            (_dump(game), game.status, time.time(), game.code),
        )
