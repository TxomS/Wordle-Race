"""Race mode through the HTTP interface: joining, fairness, secrecy, presence, isolation."""

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import ANSWER, WRONG_WORDS, Clock

A_WORDS = ["slate", "sloth", "abbey"]  # guessed only by player A
B_WORDS = ["boost", "robot", "babes"]  # guessed only by player B


def create_race(client):
    response = client.post("/api/games", json={"mode": "race"})
    assert response.status_code == 201
    body = response.json()
    return body["code"], {"X-Player-Token": body["token"]}


def join(client, code):
    return client.post(f"/api/games/{code}/join")


def start_race(client):
    """A creates a race, B joins it. Returns the code and both players' headers."""
    code, a = create_race(client)
    response = join(client, code)
    assert response.status_code == 201
    return code, a, {"X-Player-Token": response.json()["token"]}


def guess(client, code, headers, word, **extra):
    return client.post(f"/api/games/{code}/guesses", json={"guess": word, **extra}, headers=headers)


def get(client, code, headers):
    return client.get(f"/api/games/{code}", headers=headers)


def error_code(response):
    return response.json()["error"]["code"]


def opponent_connected(client, code, headers):
    return get(client, code, headers).json()["opponent"]["connected"]


# --- Creating and joining ------------------------------------------------------


def test_a_new_race_waits_for_the_opponent(client):
    code, a = create_race(client)
    game = get(client, code, a).json()
    assert (game["mode"], game["status"]) == ("race", "waiting")
    assert game["opponent"] is None

    early = guess(client, code, a, "slate")
    assert early.status_code == 409
    assert error_code(early) == "GAME_NOT_STARTED"


def test_joining_starts_the_race_for_both_players(client):
    code, a = create_race(client)
    response = join(client, code)
    assert response.status_code == 201
    body = response.json()

    assert body["code"] == code
    assert body["token"] and body["token"] != a["X-Player-Token"]
    assert body["game"]["status"] == "playing"
    assert body["game"]["opponent"] == {"connected": True, "guesses": []}

    creator_view = get(client, code, a).json()
    assert creator_view["status"] == "playing"
    assert creator_view["opponent"] == {"connected": True, "guesses": []}


def test_a_full_race_cannot_be_joined_again(client):
    code, _, _ = start_race(client)
    third = join(client, code)
    assert third.status_code == 409
    assert error_code(third) == "ROOM_FULL"


def test_a_solo_game_cannot_be_joined(client):
    code = client.post("/api/games", json={"mode": "solo"}).json()["code"]
    assert error_code(join(client, code)) == "ROOM_FULL"


def test_joining_an_unknown_code_is_not_found_and_codes_ignore_case(client):
    assert join(client, "ZZZZZ").status_code == 404
    code, _ = create_race(client)
    assert join(client, code.lower()).status_code == 201


def test_when_two_people_join_the_last_seat_together_exactly_one_gets_it(settings):
    app = create_app(settings)
    for _ in range(10):
        code, _ = create_race(TestClient(app))
        barrier = threading.Barrier(2)

        def try_to_join():
            client = TestClient(app)
            barrier.wait()
            return join(client, code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: try_to_join(), range(2)))

        assert sorted(r.status_code for r in results) == [201, 409]
        assert error_code(next(r for r in results if r.status_code == 409)) == "ROOM_FULL"


# --- Secrecy ---------------------------------------------------------------------


def test_a_whole_race_never_leaks_the_answer_or_the_opponents_letters(client):
    code, a, b = start_race(client)
    to_a, to_b = [], []  # the text of every response each player receives

    for a_word, b_word in zip(A_WORDS, B_WORDS):
        to_a.append(guess(client, code, a, a_word).text)
        to_b.append(guess(client, code, b, b_word).text)
        to_a.append(get(client, code, a).text)
        to_b.append(get(client, code, b).text)

    # Nobody has solved it, so nobody may have seen the answer.
    for text in to_a + to_b:
        assert ANSWER not in text.lower()

    # A sees the colors of B's three guesses, and nothing else about them.
    seen_by_a = get(client, code, a).json()["opponent"]["guesses"]
    assert len(seen_by_a) == 3
    assert all(set(guess_) == {"colors"} for guess_ in seen_by_a)

    # Neither player ever receives a word that only the other one guessed.
    for text in to_a:
        assert not any(word in text for word in B_WORDS)
    for text in to_b:
        assert not any(word in text for word in A_WORDS)

    # A solves it. Now the answer is revealed, but still never the opponent's letters.
    final_a = guess(client, code, a, ANSWER)
    final_b = get(client, code, b)
    assert final_a.json()["result"] == {"outcome": "won", "reason": "solved", "answer": ANSWER}
    assert final_b.json()["result"] == {"outcome": "lost", "reason": "opponent_solved", "answer": ANSWER}
    for text in to_a + [final_a.text]:
        assert not any(word in text for word in B_WORDS)
    for text in to_b + [final_b.text]:
        assert not any(word in text for word in A_WORDS)


# --- Fairness and endings ----------------------------------------------------------


def test_the_first_solver_wins_and_the_late_solver_is_told_game_over(client):
    code, a, b = start_race(client)
    assert guess(client, code, a, ANSWER).json()["result"]["outcome"] == "won"

    late = guess(client, code, b, ANSWER)
    assert late.status_code == 409
    assert error_code(late) == "GAME_OVER"
    assert get(client, code, b).json()["result"]["outcome"] == "lost"
    assert get(client, code, b).json()["me"]["guesses"] == []  # the late guess was not recorded


def test_two_winning_guesses_at_the_same_moment_produce_exactly_one_winner(settings):
    app = create_app(settings)
    for _ in range(10):
        setup = TestClient(app)
        code, a, b = start_race(setup)
        barrier = threading.Barrier(2)

        def solve(headers):
            client = TestClient(app)
            barrier.wait()  # both requests leave at the same moment
            return guess(client, code, headers, ANSWER)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(solve, [a, b]))

        assert sorted(r.status_code for r in results) == [200, 409]
        winner = next(r for r in results if r.status_code == 200)
        loser = next(r for r in results if r.status_code == 409)
        assert winner.json()["result"]["outcome"] == "won"
        assert error_code(loser) == "GAME_OVER"
        # Both players now agree on the result.
        outcomes = [get(setup, code, headers).json()["result"]["outcome"] for headers in (a, b)]
        assert sorted(outcomes) == ["lost", "won"]


def test_both_players_running_out_of_guesses_is_a_draw(client):
    code, a, b = start_race(client)
    for word in WRONG_WORDS:
        guess(client, code, a, word)
        assert get(client, code, a).json()["status"] == "playing"
        guess(client, code, b, word)

    for headers in (a, b):
        game = get(client, code, headers).json()
        assert game["status"] == "finished"
        assert game["result"] == {"outcome": "draw", "reason": "both_out_of_guesses", "answer": ANSWER}


def test_a_player_out_of_guesses_waits_while_the_other_plays_on(client):
    code, a, b = start_race(client)
    for word in WRONG_WORDS:
        guess(client, code, a, word)

    game = get(client, code, a).json()
    assert (game["status"], game["me"]["status"], game["result"]) == ("playing", "out_of_guesses", None)
    seventh = guess(client, code, a, "slate")
    assert seventh.status_code == 409
    assert error_code(seventh) == "NO_GUESSES_LEFT"

    assert guess(client, code, b, ANSWER).json()["result"]["outcome"] == "won"
    assert get(client, code, a).json()["result"]["reason"] == "opponent_solved"


# --- Several races, restart ---------------------------------------------------------


def test_two_races_at_once_do_not_affect_each_other(client):
    code1, a1, b1 = start_race(client)
    code2, a2, b2 = start_race(client)
    assert code1 != code2

    guess(client, code1, a1, "slate")
    guess(client, code2, a2, "sloth")
    guess(client, code2, b2, "boost")
    assert guess(client, code1, a1, ANSWER).json()["status"] == "finished"  # race 1 ends

    race2 = get(client, code2, a2).json()  # race 2 carries on untouched
    assert (race2["status"], race2["result"]) == ("playing", None)
    assert len(race2["me"]["guesses"]) == 1
    assert len(race2["opponent"]["guesses"]) == 1
    assert guess(client, code2, b2, ANSWER).json()["result"]["outcome"] == "won"

    # Nobody can reach into the other race.
    assert get(client, code1, a2).status_code == 401
    assert get(client, code2, a1).status_code == 401
    assert guess(client, code1, b2, "slate").status_code == 401


def test_a_race_survives_a_backend_restart(settings):
    first_run = TestClient(create_app(settings))
    code, a, b = start_race(first_run)
    guess(first_run, code, a, "slate")
    guess(first_run, code, b, "boost")
    before = [get(first_run, code, headers).json() for headers in (a, b)]

    restarted = TestClient(create_app(settings))  # a new process, same database file
    assert [get(restarted, code, headers).json() for headers in (a, b)] == before

    assert guess(restarted, code, b, ANSWER).json()["result"]["outcome"] == "won"
    assert get(restarted, code, a).json()["result"]["outcome"] == "lost"


# --- Presence --------------------------------------------------------------------------


def test_an_opponent_who_stops_polling_shows_as_disconnected(settings):
    clock = Clock()
    client = TestClient(create_app(settings, clock=clock))
    code, a, b = start_race(client)
    assert opponent_connected(client, code, a) is True

    clock.advance(10)
    assert opponent_connected(client, code, a) is True  # 10 s of silence is still fine

    clock.advance(10)  # B has now been silent for 20 s while A kept polling
    assert opponent_connected(client, code, a) is False
    assert opponent_connected(client, code, b) is True  # B polling shows B is back, and A is not silent
    assert opponent_connected(client, code, a) is True


def test_after_a_restart_players_are_assumed_present_for_one_timeout(settings):
    clock = Clock()
    code, a, b = start_race(TestClient(create_app(settings, clock=clock)))

    clock.advance(100)
    restarted = TestClient(create_app(settings, clock=clock))  # empty presence memory
    assert opponent_connected(restarted, code, a) is True  # B not seen yet, but just restarted

    clock.advance(10)
    assert opponent_connected(restarted, code, a) is True
    clock.advance(10)  # 20 s since the restart and B never polled: B really is gone
    assert opponent_connected(restarted, code, a) is False
