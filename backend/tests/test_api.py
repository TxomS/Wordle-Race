"""API tests: the real app, a real SQLite file, and the HTTP interface only."""

import re
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.rules import MAX_GUESSES, WORD_LENGTH
from conftest import ANSWER, WRONG_WORDS, Clock

CODE_PATTERN = re.compile(r"[A-HJKMNP-Z2-9]{5}")  # no I, L, O, 0 or 1
GAME_FIELDS = {"code", "mode", "status", "word_length", "max_guesses", "me", "opponent", "result"}


def start_solo(client):
    response = client.post("/api/games", json={"mode": "solo"})
    assert response.status_code == 201
    body = response.json()
    return body["code"], {"X-Player-Token": body["token"]}, body


def guess(client, code, headers, word, **extra):
    return client.post(f"/api/games/{code}/guesses", json={"guess": word, **extra}, headers=headers)


def get_game(client, code, headers):
    return client.get(f"/api/games/{code}", headers=headers)


# --- Basics ------------------------------------------------------------------


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_responses_are_never_cached(client):
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_create_a_solo_game(client):
    code, _, body = start_solo(client)
    assert CODE_PATTERN.fullmatch(code)
    assert body["token"]

    game = body["game"]
    assert set(game) == GAME_FIELDS
    assert game["code"] == code
    assert game["mode"] == "solo"
    assert game["status"] == "playing"
    assert (game["word_length"], game["max_guesses"]) == (WORD_LENGTH, MAX_GUESSES)
    assert game["me"] == {"status": "playing", "guesses": []}
    assert game["opponent"] is None
    assert game["result"] is None


# --- Playing a solo game -----------------------------------------------------


def test_play_to_a_win(client):
    code, headers, _ = start_solo(client)

    response = guess(client, code, headers, "slate")
    assert response.status_code == 200
    game = response.json()
    assert game["me"]["guesses"] == [{"word": "slate", "colors": ["grey", "grey", "green", "grey", "green"]}]
    assert game["status"] == "playing"
    assert game["result"] is None

    game = guess(client, code, headers, ANSWER).json()
    assert game["status"] == "finished"
    assert game["me"]["status"] == "solved"
    assert game["result"] == {"outcome": "won", "reason": "solved", "answer": ANSWER}


def test_running_out_of_guesses_loses_and_reveals_the_answer(client):
    words = WRONG_WORDS[:MAX_GUESSES]
    code, headers, _ = start_solo(client)
    for word in words[:-1]:
        assert guess(client, code, headers, word).json()["status"] == "playing"

    game = guess(client, code, headers, words[-1]).json()
    assert game["status"] == "finished"
    assert game["result"] == {"outcome": "lost", "reason": "out_of_guesses", "answer": ANSWER}

    seventh = guess(client, code, headers, "slate")
    assert seventh.status_code == 409
    assert seventh.json()["error"]["code"] == "GAME_OVER"


def test_a_guess_after_the_game_has_ended_is_refused(client):
    code, headers, _ = start_solo(client)
    guess(client, code, headers, ANSWER)
    response = guess(client, code, headers, "slate")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GAME_OVER"


def test_guesses_are_case_insensitive(client):
    code, headers, _ = start_solo(client)
    game = guess(client, code, headers, "SLATE").json()
    assert game["me"]["guesses"][0]["word"] == "slate"


# --- Refusals ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "status", "error_code"),
    [
        ("abc", 422, "BAD_FORMAT"),
        ("cranes", 422, "BAD_FORMAT"),
        ("12345", 422, "BAD_FORMAT"),
        ("sla te", 422, "BAD_FORMAT"),
        ("zzzzz", 422, "NOT_A_WORD"),
    ],
)
def test_refused_guesses_cost_nothing(client, word, status, error_code):
    code, headers, _ = start_solo(client)
    response = guess(client, code, headers, word)
    assert response.status_code == status
    assert response.json()["error"]["code"] == error_code
    assert get_game(client, code, headers).json()["me"]["guesses"] == []


@pytest.mark.parametrize(
    "body",
    [{}, {"guess": 12345}, {"guess": "slate", "index": -1}, {"guess": "x" * 100}],
)
def test_malformed_guess_requests_get_the_standard_error_shape(client, body):
    code, headers, _ = start_solo(client)
    response = client.post(f"/api/games/{code}/guesses", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_unknown_game_mode_is_refused(client):
    response = client.post("/api/games", json={"mode": "tournament"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_stale_index_is_refused_so_a_retry_cannot_burn_a_second_guess(client):
    code, headers, _ = start_solo(client)
    assert guess(client, code, headers, "slate", index=0).status_code == 200
    again = guess(client, code, headers, "slate", index=0)  # the same request sent twice
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "STALE_INDEX"
    assert len(get_game(client, code, headers).json()["me"]["guesses"]) == 1


def test_token_and_code_problems(client):
    code, headers, _ = start_solo(client)
    other_code, other_headers, _ = start_solo(client)

    def error_of(response):
        return response.status_code, response.json()["error"]["code"]

    assert error_of(client.get(f"/api/games/{code}")) == (401, "BAD_TOKEN")  # no token
    assert error_of(client.get(f"/api/games/{code}", headers={"X-Player-Token": "nope"})) == (401, "NOT_IN_GAME")
    assert error_of(get_game(client, code, other_headers)) == (401, "NOT_IN_GAME")  # token of another game
    assert error_of(get_game(client, "ZZZZZ", headers)) == (404, "NOT_FOUND")
    assert error_of(guess(client, code, other_headers, "slate")) == (401, "NOT_IN_GAME")
    assert error_of(guess(client, "ZZZZZ", headers, "slate")) == (404, "NOT_FOUND")
    assert get_game(client, other_code, other_headers).status_code == 200  # the games are independent


def test_game_codes_are_case_insensitive(client):
    code, headers, _ = start_solo(client)
    assert get_game(client, code.lower(), headers).status_code == 200


# --- Secrecy -----------------------------------------------------------------


def test_the_answer_never_reaches_the_client_before_the_game_ends(client):
    """The brief's key check: play a game and look at every response body."""
    seen = []

    created = client.post("/api/games", json={"mode": "solo"})
    seen.append(created.text)
    body = created.json()
    code, headers = body["code"], {"X-Player-Token": body["token"]}

    seen.append(get_game(client, code, headers).text)
    seen.append(guess(client, code, headers, "zzzzz").text)  # refused: not a word
    seen.append(guess(client, code, headers, "abc").text)  # refused: bad format
    seen.append(guess(client, code, headers, "slate", index=5).text)  # refused: stale
    words = WRONG_WORDS[:MAX_GUESSES]
    for word in words[:-1]:  # all but the last wrong guess: the game is still going
        seen.append(guess(client, code, headers, word).text)
        seen.append(get_game(client, code, headers).text)
    seen.append(client.get("/api/openapi.json").text)

    for text in seen:
        assert ANSWER not in text.lower()

    # After the game ends the answer is revealed.
    final = guess(client, code, headers, words[-1])
    assert ANSWER in final.text.lower()


def test_the_response_has_exactly_the_documented_fields(client):
    """If someone adds a field to the response, this test makes them notice (and review it)."""
    code, headers, body = start_solo(client)
    game = guess(client, code, headers, "slate").json()
    assert set(body) == {"code", "token", "game"}
    assert set(game) == GAME_FIELDS
    assert set(game["me"]) == {"status", "guesses"}
    assert set(game["me"]["guesses"][0]) == {"word", "colors"}


def test_the_player_token_is_not_stored_in_the_database(client, settings):
    _, _, body = start_solo(client)
    with sqlite3.connect(settings.db_path) as conn:
        rows = conn.execute("SELECT code, data, status FROM games").fetchall()
    assert rows, "the game should have been saved"
    assert all(body["token"] not in str(column) for row in rows for column in row)


# --- Cleanup of old games ---------------------------------------------------------


def run_cleanup(client):
    """Run the clean-up once, as the background sweep does every few minutes."""
    return client.app.state.service.cleanup()


def make_everything_old(settings):
    """Pretend every game in the database was last played two days ago."""
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("UPDATE games SET updated_at = ?", (time.time() - 2 * 24 * 3600,))


def test_abandoned_games_are_deleted_by_the_cleanup(settings):
    clock = Clock()
    client = TestClient(create_app(settings, clock=clock))
    old_code, old_headers, _ = start_solo(client)
    make_everything_old(settings)
    recent_code, recent_headers, _ = start_solo(client)

    clock.advance(16 * 60)  # nobody has asked about the old game for longer than the limit
    run_cleanup(client)
    assert get_game(client, old_code, old_headers).status_code == 404
    assert get_game(client, recent_code, recent_headers).status_code == 200  # recent games stay


def test_a_game_that_someone_is_still_polling_is_not_deleted_even_when_idle(settings):
    clock = Clock()
    client = TestClient(create_app(settings, clock=clock))
    code, headers, _ = start_solo(client)
    make_everything_old(settings)  # no guess for a very long time ...

    clock.advance(10 * 60)
    assert get_game(client, code, headers).status_code == 200  # ... but the page is open and asks
    clock.advance(10 * 60)
    run_cleanup(client)  # idle, but someone asked 10 minutes ago, inside the limit
    assert get_game(client, code, headers).status_code == 200  # (this request counts as asking too)

    clock.advance(16 * 60)  # now the page has been silent for longer than the limit
    run_cleanup(client)
    assert get_game(client, code, headers).status_code == 404


def set_idle_for(settings, code, seconds):
    """Pretend one game was last played `seconds` ago."""
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("UPDATE games SET updated_at = ? WHERE code = ?", (time.time() - seconds, code))


def test_the_default_limit_is_fifteen_minutes(settings):
    clock = Clock()
    client = TestClient(create_app(settings, clock=clock))
    stale_code, stale_headers, _ = start_solo(client)
    fresh_code, fresh_headers, _ = start_solo(client)
    set_idle_for(settings, stale_code, 20 * 60)  # idle for 20 minutes
    set_idle_for(settings, fresh_code, 10 * 60)  # idle for 10 minutes

    clock.advance(16 * 60)  # nobody has asked about either game for longer than the limit
    run_cleanup(client)
    assert get_game(client, stale_code, stale_headers).status_code == 404
    assert get_game(client, fresh_code, fresh_headers).status_code == 200


def stored_codes(settings):
    with sqlite3.connect(settings.db_path) as conn:
        return {row[0] for row in conn.execute("SELECT code FROM games")}


def test_after_a_restart_idle_games_get_one_limit_of_benefit_of_the_doubt(settings):
    clock = Clock()
    first_run = TestClient(create_app(settings, clock=clock))
    code, _, _ = start_solo(first_run)
    make_everything_old(settings)

    # A restart empties the memory of who is around, and a page may be polling this very
    # moment, so nothing is deleted yet.
    restarted = TestClient(create_app(settings, clock=clock))
    run_cleanup(restarted)
    assert code in stored_codes(settings)

    clock.advance(16 * 60)  # nobody turned up for a whole limit: now it really is abandoned
    run_cleanup(restarted)
    assert code not in stored_codes(settings)


# --- Refresh and restart -------------------------------------------------------


def test_refreshing_returns_the_same_progress(client):
    code, headers, _ = start_solo(client)
    guess(client, code, headers, "slate")
    last = guess(client, code, headers, "sloth").json()
    assert get_game(client, code, headers).json() == last


def test_a_game_survives_a_backend_restart(settings):
    first_run = TestClient(create_app(settings))
    code, headers, _ = start_solo(first_run)
    before = guess(first_run, code, headers, "slate").json()

    restarted = TestClient(create_app(settings))  # a new process, same database file
    assert get_game(restarted, code, headers).json() == before
    after = guess(restarted, code, headers, ANSWER).json()
    assert after["result"]["outcome"] == "won"
