"""Pure game rules.

No HTTP, no database, no files: only functions on plain data, so everything here
can be unit-tested on its own. The rest of the backend (storage, API) is built
around this module.
"""

import re
from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass, field

# --- Settings of the game ------------------------------------------------------

WORD_LENGTH = 5
MAX_GUESSES = 6  # per player

# Tile colors.
GREEN = "green"  # right letter, right position
YELLOW = "yellow"  # letter is in the word, but somewhere else
GREY = "grey"  # not in the word, or all of its copies are already accounted for

# Game modes. A solo game is simply a game with room for one player.
SOLO = "solo"
RACE = "race"

# Game status: waiting for the second player -> playing -> finished.
WAITING = "waiting"
PLAYING = "playing"
FINISHED = "finished"

_FORMAT = re.compile(rf"[a-z]{{{WORD_LENGTH}}}")


def is_valid_format(word: str) -> bool:
    """True if `word` is exactly WORD_LENGTH lowercase letters a-z."""
    return _FORMAT.fullmatch(word) is not None


# --- Scoring -------------------------------------------------------------------


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


# --- Errors --------------------------------------------------------------------


class GameError(Exception):
    """A move the rules refuse. `code` is a stable machine-readable name that the
    API passes on to the browser; `message` is a human-readable explanation."""

    code = "GAME_ERROR"
    message = "The game rejected this move."

    def __init__(self) -> None:
        super().__init__(self.message)


class RoomFull(GameError):
    code = "ROOM_FULL"
    message = "This game already has all its players."


class NotInGame(GameError):
    code = "NOT_IN_GAME"
    message = "You are not a player in this game."


class GameNotStarted(GameError):
    code = "GAME_NOT_STARTED"
    message = "The game starts when the second player joins."


class GameOver(GameError):
    code = "GAME_OVER"
    message = "The game is over."


class NoGuessesLeft(GameError):
    code = "NO_GUESSES_LEFT"
    message = "You have used all your guesses."


class StaleIndex(GameError):
    code = "STALE_INDEX"
    message = "Your board is out of date."


class BadFormat(GameError):
    code = "BAD_FORMAT"
    message = f"A guess must be exactly {WORD_LENGTH} letters."


class NotAWord(GameError):
    code = "NOT_A_WORD"
    message = "Not in the word list."


# --- Game state ----------------------------------------------------------------


@dataclass
class Guess:
    word: str
    colors: list[str]
    seq: int  # 1, 2, 3...: the order in which the server accepted guesses in this game


@dataclass
class Player:
    id: str
    guesses: list[Guess] = field(default_factory=list)

    @property
    def solved(self) -> bool:
        return any(all(color == GREEN for color in guess.colors) for guess in self.guesses)

    @property
    def out_of_guesses(self) -> bool:
        return len(self.guesses) >= MAX_GUESSES and not self.solved

    @property
    def status(self) -> str:
        if self.solved:
            return "solved"
        if self.out_of_guesses:
            return "out_of_guesses"
        return "playing"


@dataclass
class Game:
    code: str
    answer: str
    mode: str  # SOLO or RACE
    players: list[Player] = field(default_factory=list)
    status: str = WAITING
    winner_id: str | None = None
    next_seq: int = 1

    @property
    def capacity(self) -> int:
        return 1 if self.mode == SOLO else 2


@dataclass(frozen=True)
class Result:
    """How a finished game ended, from one player's point of view."""

    outcome: str  # "won", "lost" or "draw"
    reason: str  # "solved", "opponent_solved", "out_of_guesses" or "both_out_of_guesses"


# --- Game rules ----------------------------------------------------------------


def new_game(code: str, answer: str, mode: str) -> Game:
    if mode not in (SOLO, RACE):
        raise ValueError(f"unknown game mode: {mode!r}")
    return Game(code=code, answer=answer, mode=mode)


def add_player(game: Game, player_id: str) -> Player:
    """Seat a player. The game starts as soon as every seat is taken."""
    if len(game.players) >= game.capacity:
        raise RoomFull()
    player = Player(id=player_id)
    game.players.append(player)
    if len(game.players) == game.capacity:
        game.status = PLAYING
    return player


def get_player(game: Game, player_id: str) -> Player:
    for player in game.players:
        if player.id == player_id:
            return player
    raise NotInGame()


def submit_guess(
    game: Game,
    player_id: str,
    word: str,
    allowed: Collection[str],
    expected_index: int | None = None,
) -> Guess:
    """Apply one guess. Raises a GameError if the rules refuse it; otherwise
    scores it, records it, and ends the game if this guess decided it.

    The checks run in a fixed order, so every refusal has one clear reason, and a
    refused guess changes nothing (it never costs the player a guess):

      1. the player is in this game
      2. the game has started
      3. the game is not already over
      4. the player still has guesses left
      5. `expected_index` (how many guesses the caller thinks the player has made)
         matches reality. This protects against a double-click or a retried request
         burning two guesses.
      6. the word is well formed
      7. the word is in the allowed list

    Winner selection: the first guess that solves the word wins. Guesses are applied
    one at a time in the order the server receives them, so there is always exactly
    one first. Once a game is finished, step 3 refuses everything else, so a second
    solving guess that arrives "at the same moment" is simply too late.
    """
    player = get_player(game, player_id)

    if game.status == WAITING:
        raise GameNotStarted()
    if game.status == FINISHED:
        raise GameOver()
    if len(player.guesses) >= MAX_GUESSES:
        raise NoGuessesLeft()
    if expected_index is not None and expected_index != len(player.guesses):
        raise StaleIndex()

    word = word.strip().lower()
    if not is_valid_format(word):
        raise BadFormat()
    if word not in allowed:
        raise NotAWord()

    guess = Guess(word=word, colors=score_guess(game.answer, word), seq=game.next_seq)
    game.next_seq += 1
    player.guesses.append(guess)

    if player.solved:
        game.status = FINISHED
        game.winner_id = player.id
    elif all(p.out_of_guesses for p in game.players):
        game.status = FINISHED  # nobody solved it: no winner

    return guess


def result_for(game: Game, player_id: str) -> Result | None:
    """The outcome of a finished game for one player, or None while it is still going."""
    if game.status != FINISHED:
        return None
    if game.winner_id == player_id:
        return Result("won", "solved")
    if game.winner_id is not None:
        return Result("lost", "opponent_solved")
    if game.mode == SOLO:
        return Result("lost", "out_of_guesses")
    return Result("draw", "both_out_of_guesses")
