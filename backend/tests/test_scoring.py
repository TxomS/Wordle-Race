"""Unit tests for score_guess. No HTTP, no storage: just the rule itself.

Expected results are written as short strings: g = green, y = yellow, x = grey.
"""

import random

import pytest

from app.rules import GREEN, GREY, YELLOW, score_guess

_NAMES = {"g": GREEN, "y": YELLOW, "x": GREY}


def colors(pattern: str) -> list[str]:
    return [_NAMES[c] for c in pattern]


@pytest.mark.parametrize(
    ("answer", "guess", "expected"),
    [
        # The example from the brief.
        pytest.param("abbey", "babes", "yyggx", id="brief-example"),
        # Plain cases.
        pytest.param("crane", "crane", "ggggg", id="exact-match"),
        pytest.param("crane", "sloth", "xxxxx", id="nothing-in-common"),
        pytest.param("crane", "nacre", "yyyyg", id="anagram-all-in-wrong-places"),
        # The guess repeats a letter the answer has only once: only one copy is marked.
        pytest.param("crane", "eerie", "xxyxg", id="repeated-guess-letter-green-wins-over-yellow"),
        pytest.param("crane", "eager", "yyxxy", id="repeated-guess-letter-second-copy-is-grey"),
        # The answer repeats a letter the guess has only once: the single copy is yellow.
        pytest.param("speed", "crane", "xxxxy", id="repeated-answer-letter-single-guess-letter"),
        # Both repeat the letter.
        pytest.param("speed", "eerie", "yyxxx", id="both-repeat-no-greens"),
        pytest.param("robot", "boost", "ygyxg", id="one-green-one-yellow-for-the-same-letter"),
        # Greens are decided first, so BBBBB only lights up the two real B positions.
        pytest.param("abbey", "bbbbb", "xggxx", id="all-same-letter-greens-only"),
        pytest.param("robot", "ooooo", "xgxgx", id="all-same-letter-two-copies"),
        # Three L in the guess, two in the answer: one green, one yellow, the third grey.
        pytest.param("llama", "lilal", "gxyyx", id="green-uses-up-one-of-two-copies"),
    ],
)
def test_scoring_table(answer, guess, expected):
    assert score_guess(answer, guess) == colors(expected)


def test_scoring_ignores_case():
    assert score_guess("ABBEY", "BABES") == score_guess("abbey", "babes")


def test_scoring_rejects_different_lengths():
    with pytest.raises(ValueError):
        score_guess("abbey", "bab")


def test_scoring_matches_the_wordle_rule_on_random_words():
    """Check the two defining properties of the rule on thousands of random pairs.

    Words are built from only three letters, so repeated letters are the norm,
    which is exactly where scoring bugs hide.

      1. A tile is green if and only if that position matches the answer.
      2. For every letter, the number of green + yellow tiles equals
         min(copies in the guess, copies in the answer).
    """
    rng = random.Random(1234)
    for _ in range(3000):
        answer = "".join(rng.choice("abc") for _ in range(5))
        guess = "".join(rng.choice("abc") for _ in range(5))
        result = score_guess(answer, guess)

        for position, color in enumerate(result):
            assert (color == GREEN) == (guess[position] == answer[position]), (answer, guess)

        for letter in set(guess):
            marked = sum(1 for position, color in enumerate(result) if guess[position] == letter and color != GREY)
            assert marked == min(guess.count(letter), answer.count(letter)), (answer, guess)
