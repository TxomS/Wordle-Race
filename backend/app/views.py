"""What a player is allowed to see: the ONLY place that builds data for the browser.

The rest of the backend works with the full Game (hidden answer, every player's
letters). A Game never leaves the server. Everything sent to a browser is built
here, field by field, from the point of view of one player:

  - your own guesses: letters and colors
  - the opponent's guesses: colors only, never letters (not even after the game)
  - the hidden answer: only once the game is finished
  - no player ids or tokens

These models are also used as the API's response models, so FastAPI drops any
field that is not declared here, a second wall behind the code below.
"""

from typing import Literal

from pydantic import BaseModel

from app.rules import MAX_GUESSES, WORD_LENGTH, Game, get_player, result_for

Color = Literal["green", "yellow", "grey"]


class OwnGuess(BaseModel):
    word: str
    colors: list[Color]


class OpponentGuess(BaseModel):
    colors: list[Color]  # deliberately no `word`


class Me(BaseModel):
    status: Literal["playing", "solved", "out_of_guesses"]
    guesses: list[OwnGuess]


class Opponent(BaseModel):
    connected: bool
    guesses: list[OpponentGuess]


class ResultView(BaseModel):
    outcome: Literal["won", "lost", "draw"]
    reason: Literal["solved", "opponent_solved", "out_of_guesses", "both_out_of_guesses"]
    answer: str  # only ever present in a finished game


class GameView(BaseModel):
    code: str
    mode: Literal["solo", "race"]
    status: Literal["waiting", "playing", "finished"]
    word_length: int
    max_guesses: int
    me: Me
    opponent: Opponent | None  # None in a solo game, or while waiting for the opponent
    result: ResultView | None  # None until the game is finished


def game_view(game: Game, player_id: str, opponent_connected: bool = True) -> GameView:
    """The game as seen by one player. Raises NotInGame if `player_id` is not a player."""
    me = get_player(game, player_id)
    opponent = next((p for p in game.players if p.id != player_id), None)
    result = result_for(game, player_id)

    return GameView(
        code=game.code,
        mode=game.mode,
        status=game.status,
        word_length=WORD_LENGTH,
        max_guesses=MAX_GUESSES,
        me=Me(
            status=me.status,
            guesses=[OwnGuess(word=g.word, colors=g.colors) for g in me.guesses],
        ),
        opponent=(
            None
            if opponent is None
            else Opponent(
                connected=opponent_connected,
                guesses=[OpponentGuess(colors=g.colors) for g in opponent.guesses],
            )
        ),
        result=(
            None
            if result is None
            else ResultView(outcome=result.outcome, reason=result.reason, answer=game.answer)
        ),
    )
