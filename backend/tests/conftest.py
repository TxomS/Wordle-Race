"""Shared test setup: a tiny word list with a known answer and a temporary database."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ANSWER = "crane"
WRONG_WORDS = ["slate", "sloth", "boost", "robot", "abbey", "babes"]  # six different wrong guesses


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
