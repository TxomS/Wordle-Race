"""Unit tests for the game rules: joining, guessing, end conditions, winner selection.

Everything here works on plain Game objects. No HTTP, no database.
"""

import pytest

from app.rules import (
    FINISHED,
    GREEN,
    GREY,
    MAX_GUESSES,
    PLAYING,
    RACE,
    SOLO,
    WAITING,
    BadFormat,
    GameNotStarted,
    GameOver,
    NoGuessesLeft,
    NotAWord,
    NotInGame,
    RoomFull,
    StaleIndex,
    add_player,
    new_game,
    result_for,
    submit_guess,
)

ANSWER = "crane"
WRONG = ["slate", "sloth", "boost", "robot", "abbey", "babes"]  # six different wrong words
ALLOWED = frozenset(WRONG + [ANSWER])


def solo_game():
    game = new_game("SOLO1", ANSWER, SOLO)
    add_player(game, "p1")
    return game


def race_game():
    game = new_game("RACE1", ANSWER, RACE)
    add_player(game, "a")
    add_player(game, "b")
    return game


def play(game, player_id, word, **kwargs):
    return submit_guess(game, player_id, word, ALLOWED, **kwargs)


def play_wrong(game, player_id, count):
    for word in WRONG[:count]:
        play(game, player_id, word)


# --- Joining -----------------------------------------------------------------


def test_race_waits_for_the_second_player_then_starts():
    game = new_game("R1", ANSWER, RACE)
    assert game.status == WAITING
    add_player(game, "a")
    assert game.status == WAITING
    add_player(game, "b")
    assert game.status == PLAYING


def test_solo_starts_as_soon_as_the_player_joins():
    game = new_game("S1", ANSWER, SOLO)
    add_player(game, "p1")
    assert game.status == PLAYING


def test_a_full_game_takes_no_more_players():
    with pytest.raises(RoomFull):
        add_player(race_game(), "c")
    with pytest.raises(RoomFull):
        add_player(solo_game(), "p2")


def test_unknown_game_mode_is_refused():
    with pytest.raises(ValueError):
        new_game("X1", ANSWER, "tournament")


def test_cannot_guess_before_the_opponent_has_joined():
    game = new_game("R1", ANSWER, RACE)
    add_player(game, "a")
    with pytest.raises(GameNotStarted):
        play(game, "a", "slate")


# --- Accepting and refusing a guess ---------------------------------------------


def test_accepted_guess_is_scored_and_recorded():
    game = solo_game()
    guess = play(game, "p1", "slate")
    assert guess.word == "slate"
    assert guess.colors == [GREY, GREY, GREEN, GREY, GREEN]  # crane vs slate: A and E in place
    assert game.players[0].guesses == [guess]


def test_guess_is_normalised_to_lowercase_without_padding():
    game = solo_game()
    assert play(game, "p1", "  SLATE ").word == "slate"


def test_sequence_numbers_follow_the_order_the_server_accepted_guesses():
    game = race_game()
    first = play(game, "a", "slate")
    second = play(game, "b", "sloth")
    third = play(game, "a", "boost")
    assert (first.seq, second.seq, third.seq) == (1, 2, 3)


def test_someone_who_is_not_in_the_game_is_refused():
    with pytest.raises(NotInGame):
        play(solo_game(), "stranger", "slate")


@pytest.mark.parametrize("bad", ["", "cran", "cranes", "cr4ne", "cr ne", "cr-ne"])
def test_badly_formed_guess_is_refused_and_costs_nothing(bad):
    game = solo_game()
    with pytest.raises(BadFormat):
        play(game, "p1", bad)
    assert game.players[0].guesses == []
    assert game.next_seq == 1


def test_word_outside_the_list_is_refused_and_costs_nothing():
    game = solo_game()
    with pytest.raises(NotAWord):
        play(game, "p1", "zzzzz")
    assert game.players[0].guesses == []
    assert game.next_seq == 1


def test_stale_index_is_refused_and_matching_index_is_accepted():
    game = solo_game()
    with pytest.raises(StaleIndex):
        play(game, "p1", "slate", expected_index=1)  # client thinks it already made a guess
    assert game.players[0].guesses == []
    play(game, "p1", "slate", expected_index=0)
    play(game, "p1", "sloth", expected_index=1)
    with pytest.raises(StaleIndex):
        play(game, "p1", "boost", expected_index=1)  # the same request sent twice
    assert len(game.players[0].guesses) == 2


# --- Solo: how a game ends -------------------------------------------------------


def test_solving_the_word_wins_a_solo_game():
    game = solo_game()
    play(game, "p1", "slate")
    play(game, "p1", ANSWER)
    assert game.status == FINISHED
    assert game.winner_id == "p1"
    assert result_for(game, "p1").outcome == "won"


def test_solving_on_the_last_guess_still_wins():
    game = solo_game()
    play_wrong(game, "p1", MAX_GUESSES - 1)
    play(game, "p1", ANSWER)
    assert game.status == FINISHED
    assert game.winner_id == "p1"


def test_six_wrong_guesses_end_a_solo_game_as_a_loss():
    game = solo_game()
    play_wrong(game, "p1", MAX_GUESSES)
    assert game.status == FINISHED
    assert game.winner_id is None
    result = result_for(game, "p1")
    assert (result.outcome, result.reason) == ("lost", "out_of_guesses")


def test_a_seventh_guess_is_refused():
    game = solo_game()
    play_wrong(game, "p1", MAX_GUESSES)
    with pytest.raises(GameOver):
        play(game, "p1", "slate")
    assert len(game.players[0].guesses) == MAX_GUESSES


def test_no_guess_is_accepted_after_the_game_has_ended():
    game = solo_game()
    play(game, "p1", ANSWER)
    with pytest.raises(GameOver):
        play(game, "p1", "slate")
    with pytest.raises(GameOver):  # the game-over check comes before the word checks
        play(game, "p1", "zzzzz")


# --- Race: winner selection -------------------------------------------------------


def test_first_solve_wins_even_if_the_other_player_would_have_needed_fewer_guesses():
    game = race_game()
    play(game, "b", "slate")  # b has made 1 guess ...
    play_wrong(game, "a", 4)
    play(game, "a", ANSWER)  # ... but a solves first, on a's fifth guess
    assert game.status == FINISHED
    assert game.winner_id == "a"

    with pytest.raises(GameOver):  # b's solving guess arrives too late
        play(game, "b", ANSWER)
    assert len(game.players[1].guesses) == 1  # and is not recorded
    assert game.winner_id == "a"


def test_when_two_solving_guesses_arrive_together_the_first_one_applied_wins():
    game = race_game()
    play(game, "b", ANSWER)  # the server happens to handle b's request first
    with pytest.raises(GameOver):
        play(game, "a", ANSWER)
    assert game.winner_id == "b"


def test_both_players_running_out_of_guesses_is_a_draw():
    game = race_game()
    for word in WRONG:  # a and b alternate
        play(game, "a", word)
        assert game.status == PLAYING
        play(game, "b", word)
    assert game.status == FINISHED
    assert game.winner_id is None
    for player_id in ("a", "b"):
        result = result_for(game, player_id)
        assert (result.outcome, result.reason) == ("draw", "both_out_of_guesses")


def test_a_player_out_of_guesses_does_not_end_the_race_while_the_other_plays_on():
    game = race_game()
    play_wrong(game, "a", MAX_GUESSES)
    assert game.status == PLAYING
    with pytest.raises(NoGuessesLeft):
        play(game, "a", "slate")

    play(game, "b", ANSWER)  # b can still win
    assert game.winner_id == "b"
    result = result_for(game, "a")
    assert (result.outcome, result.reason) == ("lost", "opponent_solved")


# --- Results and player status ----------------------------------------------------


def test_there_is_no_result_while_the_game_is_still_going():
    game = race_game()
    assert result_for(game, "a") is None
    play(game, "a", "slate")
    assert result_for(game, "b") is None


def test_result_is_reported_from_each_players_point_of_view():
    game = race_game()
    play(game, "a", ANSWER)
    won = result_for(game, "a")
    lost = result_for(game, "b")
    assert (won.outcome, won.reason) == ("won", "solved")
    assert (lost.outcome, lost.reason) == ("lost", "opponent_solved")


def test_player_status_follows_the_board():
    game = race_game()
    a, b = game.players
    assert a.status == "playing"
    play_wrong(game, "a", MAX_GUESSES)
    assert a.status == "out_of_guesses"
    play(game, "b", ANSWER)
    assert b.status == "solved"
