"""What a player may see. Built straight from the rules, no HTTP involved."""

import pytest

from app.rules import RACE, NotInGame, add_player, new_game, submit_guess
from app.views import game_view

ANSWER = "crane"
ALLOWED = frozenset({"crane", "slate", "sloth"})
A, B = "player-a-secret-id", "player-b-secret-id"  # long ids, so a leak is easy to spot in text


def race_with_one_guess_each():
    game = new_game("RACE1", ANSWER, RACE)
    add_player(game, A)
    add_player(game, B)
    submit_guess(game, A, "slate", ALLOWED)
    submit_guess(game, B, "sloth", ALLOWED)
    return game


def text_of(game, player_id):
    return game_view(game, player_id).model_dump_json()


def test_opponent_guesses_are_colors_only():
    view = game_view(race_with_one_guess_each(), A)
    assert [list(guess.model_dump()) for guess in view.opponent.guesses] == [["colors"]]
    assert view.opponent.guesses[0].colors  # the colors themselves are visible


def test_opponent_letters_never_appear_while_the_game_is_going():
    game = race_with_one_guess_each()
    assert "sloth" not in text_of(game, A)  # B's guess, as seen by A
    assert "slate" not in text_of(game, B)  # A's guess, as seen by B


def test_the_answer_is_hidden_until_the_game_is_finished():
    game = race_with_one_guess_each()
    for player_id in (A, B):
        assert ANSWER not in text_of(game, player_id)
        assert game_view(game, player_id).result is None


def test_after_the_end_the_answer_appears_but_the_opponents_letters_still_do_not():
    game = race_with_one_guess_each()
    submit_guess(game, A, ANSWER, ALLOWED)  # A solves it

    view_for_b = game_view(game, B)
    assert view_for_b.result.answer == ANSWER
    assert view_for_b.result.outcome == "lost"
    assert "slate" not in view_for_b.model_dump_json()  # A's earlier guess is still only colors


def test_player_ids_never_appear():
    game = race_with_one_guess_each()
    for player_id in (A, B):
        text = text_of(game, player_id)
        assert A not in text
        assert B not in text


def test_a_waiting_race_has_no_opponent_yet():
    game = new_game("RACE2", ANSWER, RACE)
    add_player(game, A)
    view = game_view(game, A)
    assert view.status == "waiting"
    assert view.opponent is None


def test_a_stranger_gets_no_view():
    game = race_with_one_guess_each()
    with pytest.raises(NotInGame):
        game_view(game, "someone-else")
