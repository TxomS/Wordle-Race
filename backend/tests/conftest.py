"""Shared test setup: a tiny word list with a known answer and a temporary database."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ANSWER = "crane"
WRONG_WORDS = ["slate", "sloth", "boost", "robot", "abbey", "babes"]  # six different wrong guesses


class Clock:
    """A fake clock: tests move time forward by hand instead of waiting."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def words_dir(tmp_path):
    directory = tmp_path / "words"
    directory.mkdir()
    (directory / "answers.txt").write_text(f"{ANSWER}\n", encoding="utf-8")
    (directory / "allowed.txt").write_text("\n".join(sorted(WRONG_WORDS)) + "\n", encoding="utf-8")
    return directory


@pytest.fixture
def settings(tmp_path, words_dir):
    return Settings(db_path=str(tmp_path / "games.db"), words_dir=words_dir)


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))
