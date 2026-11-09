"""Tests for the word lists: both the shipped files and the loader."""

import random
import re
from pathlib import Path

import pytest

from app.words import load_word_lists, pick_answer, read_word_file

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _lines(name: str) -> list[str]:
    return (DATA_DIR / name).read_text(encoding="utf-8").splitlines()


# --- the shipped files -------------------------------------------------------


@pytest.mark.parametrize("name", ["answers.txt", "allowed.txt"])
def test_shipped_file_is_clean(name):
    lines = _lines(name)
    assert lines, f"{name} is empty"
    assert all(re.fullmatch(r"[a-z]{5}", line) for line in lines), "every line must be 5 letters a-z, lowercase, no blanks"
    assert len(lines) == len(set(lines)), "no duplicate words"
    assert lines == sorted(lines), "keep the file sorted"


def test_every_answer_is_an_allowed_guess():
    assert set(_lines("answers.txt")) <= set(_lines("allowed.txt"))


def test_allowed_list_is_larger_than_answers():
    assert len(_lines("allowed.txt")) > len(_lines("answers.txt"))


def test_answers_include_repeated_letter_words():
    """Repeated letters are where scoring bugs hide, so the sample answers should have some."""
    repeated = [word for word in _lines("answers.txt") if len(set(word)) < len(word)]
    assert len(repeated) >= 10


def test_shipped_files_load():
    lists = load_word_lists(DATA_DIR)
    assert len(lists.answers) == len(set(lists.answers))
    assert set(lists.answers) <= lists.allowed


# --- the loader --------------------------------------------------------------


def _write(directory: Path, answers: str, allowed: str) -> Path:
    (directory / "answers.txt").write_text(answers, encoding="utf-8")
    (directory / "allowed.txt").write_text(allowed, encoding="utf-8")
    return directory


def test_loader_lowercases_trims_and_skips_blank_lines(tmp_path):
    _write(tmp_path, "  ABBEY \n\ncrane\n", "slate\n")
    assert read_word_file(tmp_path / "answers.txt") == ["abbey", "crane"]


def test_loader_adds_answers_to_allowed_guesses(tmp_path):
    _write(tmp_path, "abbey\n", "crane\n")  # allowed.txt forgot "abbey"
    lists = load_word_lists(tmp_path)
    assert "abbey" in lists.allowed
    assert "crane" in lists.allowed


def test_loader_removes_duplicate_answers(tmp_path):
    _write(tmp_path, "abbey\ncrane\nabbey\n", "abbey\n")
    assert load_word_lists(tmp_path).answers == ("abbey", "crane")


@pytest.mark.parametrize("bad", ["four", "toolong", "ab1de", "ab-de", "cafés", "two words"])
def test_loader_rejects_bad_words_and_names_the_line(tmp_path, bad):
    _write(tmp_path, f"abbey\n{bad}\n", "abbey\n")
    with pytest.raises(ValueError, match=r"answers\.txt line 2"):
        load_word_lists(tmp_path)


def test_loader_rejects_empty_answer_list(tmp_path):
    _write(tmp_path, "\n\n", "abbey\n")
    with pytest.raises(ValueError, match="no words"):
        load_word_lists(tmp_path)


# --- picking the hidden word -------------------------------------------------


def test_pick_answer_is_reproducible_with_a_seeded_random():
    words = ["abbey", "crane", "slate", "robot"]
    assert pick_answer(words, random.Random(7)) == pick_answer(words, random.Random(7))


def test_pick_answer_always_returns_a_listed_word():
    words = ["abbey", "crane", "slate", "robot"]
    assert all(pick_answer(words) in words for _ in range(200))
