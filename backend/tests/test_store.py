"""The SQLite store: saving, loading, rolling back and, above all, taking turns."""

import sqlite3
import threading

import pytest

from app.rules import SOLO, add_player, new_game, submit_guess
from app.store import GameStore


def make_game(code="ABC23"):
    game = new_game(code, "crane", SOLO)
    add_player(game, "player-id")
    submit_guess(game, "player-id", "slate", {"slate"})
    return game


@pytest.fixture
def store(tmp_path):
    return GameStore(str(tmp_path / "games.db"))


def test_a_saved_game_comes_back_identical(store):
    game = make_game()
    with store.write() as conn:
        assert store.insert(conn, game) is True
    with store.read() as conn:
        assert store.load(conn, "ABC23") == game


def test_loading_an_unknown_code_returns_none(store):
    with store.read() as conn:
        assert store.load(conn, "NOPE2") is None


def test_inserting_an_existing_code_is_refused(store):
    with store.write() as conn:
        assert store.insert(conn, make_game()) is True
    with store.write() as conn:
        assert store.insert(conn, make_game()) is False


def test_a_failed_write_is_rolled_back_completely(store):
    game = make_game()
    with store.write() as conn:
        store.insert(conn, game)

    with pytest.raises(RuntimeError):
        with store.write() as conn:
            changed = store.load(conn, "ABC23")
            changed.next_seq = 99
            store.save(conn, changed)
            raise RuntimeError("something went wrong after saving")

    with store.read() as conn:
        assert store.load(conn, "ABC23").next_seq == game.next_seq


def test_idle_games_can_be_listed_and_deleted(store):
    with store.write() as conn:
        store.insert(conn, make_game("OLD11"))
        store.insert(conn, make_game("NEW22"))
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE games SET updated_at = 1000 WHERE code = 'OLD11'")

    with store.write() as conn:
        assert [game.code for game in store.list_idle(conn, cutoff=2000)] == ["OLD11"]
        assert store.delete(conn, ["OLD11"]) == 1
    with store.read() as conn:
        assert store.load(conn, "OLD11") is None
        assert store.load(conn, "NEW22") is not None


def test_data_is_still_there_for_a_new_store_on_the_same_file(store):
    with store.write() as conn:
        store.insert(conn, make_game())
    reopened = GameStore(store.path)
    with reopened.read() as conn:
        assert reopened.load(conn, "ABC23") is not None


def test_simultaneous_writers_take_turns_and_no_update_is_lost(store):
    """20 threads each read the game, add one, and save it. Without a write lock around
    the whole read-modify-write, some would read the same value and overwrite each
    other. With it, every update lands: this is what orders "who solved first"."""
    game = make_game()
    with store.write() as conn:
        store.insert(conn, game)
    start = game.next_seq
    errors = []

    def bump():
        try:
            with store.write() as conn:
                current = store.load(conn, "ABC23")
                current.next_seq += 1
                store.save(conn, current)
        except Exception as exc:  # pragma: no cover - only reached if the lock misbehaves
            errors.append(exc)

    threads = [threading.Thread(target=bump) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with store.read() as conn:
        assert store.load(conn, "ABC23").next_seq == start + 20
