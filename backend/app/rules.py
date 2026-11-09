"""Pure game rules.

No HTTP, no database, no files: only functions on plain data, so everything here
can be unit-tested on its own. The rest of the backend (storage, API) is built
around this module.
"""

from collections import Counter

WORD_LENGTH = 5

GREEN = "green"  # right letter, right position
YELLOW = "yellow"  # letter is in the word, but somewhere else
GREY = "grey"  # not in the word, or all of its copies are already accounted for


def score_guess(answer: str, guess: str) -> list[str]:
    """Return one color per letter of `guess`, following the standard Wordle rule.

    A letter is marked green or yellow only as many times as it appears in the
    answer, and greens take priority. That needs two passes:

      1. Mark every exact match green. The answer letters that were NOT matched
         are what is still "available" for yellows.
      2. Walk the guess left to right. A non-green letter becomes yellow if an
         unmatched copy of it is still available (and uses that copy up);
         otherwise it is grey.

    Example: answer ABBEY, guess BABES.
      pass 1: positions 3 and 4 (B, E) are green; unmatched answer letters: A, B, Y.
      pass 2: B -> yellow (uses the spare B), A -> yellow, S -> grey.
      result: yellow, yellow, green, green, grey.

    Comparison ignores case. Both words must have the same length.
    """
    answer = answer.lower()
    guess = guess.lower()
    if len(answer) != len(guess):
        raise ValueError(f"answer and guess must have the same length ({len(answer)} != {len(guess)})")

    colors = [GREY] * len(guess)
    available = Counter()  # answer letters not used up by a green

    # Pass 1: greens, and count what is left over in the answer.
    for i, (answer_letter, guess_letter) in enumerate(zip(answer, guess)):
        if answer_letter == guess_letter:
            colors[i] = GREEN
        else:
            available[answer_letter] += 1

    # Pass 2: yellows, left to right, only while an unmatched copy remains.
    for i, guess_letter in enumerate(guess):
        if colors[i] == GREEN:
            continue
        if available[guess_letter] > 0:
            colors[i] = YELLOW
            available[guess_letter] -= 1

    return colors
