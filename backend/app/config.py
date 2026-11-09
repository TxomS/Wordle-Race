"""Settings, read from environment variables. Every setting has a default, so the
app starts without any configuration."""

import os
from dataclasses import dataclass
from pathlib import Path

# backend/app/config.py -> backend/data
_DEFAULT_WORDS_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Settings:
    db_path: str  # the SQLite file
    words_dir: Path  # folder holding answers.txt and allowed.txt
    presence_timeout_seconds: float = 15.0  # silence longer than this shows as "disconnected"
    # A game still being played, or a lobby still waiting, is deleted when nobody has guessed
    # in or joined it for this long AND no page has asked the server about it for this long
    # (an open page keeps its game alive).
    game_ttl_minutes: float = 15.0
    # The same rule for a game that has finished, with a much shorter time: its result has
    # been shown, and each page stops asking once it has seen it.
    finished_game_ttl_minutes: float = 2.0
    # How often the background sweep looks for abandoned games. A game can therefore live
    # up to this much longer than the limits above.
    sweep_interval_minutes: float = 1.0


def load_settings() -> Settings:
    return Settings(
        db_path=os.environ.get("DB_PATH", "wordle.db"),
        words_dir=Path(os.environ.get("WORDS_DIR", str(_DEFAULT_WORDS_DIR))),
        presence_timeout_seconds=float(os.environ.get("PRESENCE_TIMEOUT_SECONDS", "15")),
        game_ttl_minutes=float(os.environ.get("GAME_TTL_MINUTES", "15")),
        finished_game_ttl_minutes=float(os.environ.get("FINISHED_GAME_TTL_MINUTES", "2")),
        sweep_interval_minutes=float(os.environ.get("SWEEP_EVERY_MINUTES", "1")),
    )
