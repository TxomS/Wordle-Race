"""Loading the two word lists.

answers.txt  - words that can be picked as the hidden word.
allowed.txt  - every word accepted as a guess.

Both files are plain text, one word per line. Words are lower-cased, and a word
that is not exactly WORD_LENGTH letters a-z stops the app at startup with a clear
message (a broken list should be noticed immediately, not mid-game).
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.rules import WORD_LENGTH, is_valid_format


@dataclass(frozen=True)
class WordLists:
    answers: tuple[str, ...]  # possible hidden words, without duplicates
    allowed: frozenset[str]  # every accepted guess; always contains the answers


def read_word_file(path: Path) -> list[str]:
    """Read one word per line. Blank lines are skipped; bad words raise ValueError."""
    words = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        word = raw.strip().lower()
        if not word:
            continue
        if not is_valid_format(word):
            raise ValueError(f"{path.name} line {line_number}: {raw!r} is not a {WORD_LENGTH}-letter word (a-z only)")
        words.append(word)
    return words


def load_word_lists(directory: str | Path) -> WordLists:
    directory = Path(directory)
    answers = tuple(dict.fromkeys(read_word_file(directory / "answers.txt")))
    if not answers:
        raise ValueError("answers.txt contains no words")
    # Every answer must also be a valid guess, even if allowed.txt forgot it.
    allowed = frozenset(read_word_file(directory / "allowed.txt")) | frozenset(answers)
    return WordLists(answers=answers, allowed=allowed)


def pick_answer(answers: Sequence[str], rng: random.Random | None = None) -> str:
    """Pick the hidden word. Uses the operating system's secure random source by
    default, so the next word cannot be predicted. Tests pass a seeded Random."""
    return (rng or random.SystemRandom()).choice(answers)
