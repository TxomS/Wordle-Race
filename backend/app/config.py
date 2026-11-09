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


def load_settings() -> Settings:
    return Settings(
        db_path=os.environ.get("DB_PATH", "wordle.db"),
        words_dir=Path(os.environ.get("WORDS_DIR", str(_DEFAULT_WORDS_DIR))),
    )
