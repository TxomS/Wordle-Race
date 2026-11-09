"""The background sweep: a timer around GameService.cleanup().

These tests use real threads and real (very short) intervals, so they wait for things to
happen with a deadline instead of sleeping a fixed time.
"""

import sqlite3
import time
from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import create_app
from app.sweeper import Sweeper


def wait_until(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_the_job_runs_again_and_again_until_it_is_stopped():
    calls = []
    sweeper = Sweeper(lambda: calls.append(1), interval_seconds=0.02)
    sweeper.start()
    assert wait_until(lambda: len(calls) >= 3)
    sweeper.stop()

    count = len(calls)
    time.sleep(0.15)
    assert len(calls) == count  # nothing runs after stop()


def test_a_failing_job_does_not_end_the_sweep(caplog):
    attempts = []

    def job():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("the database was busy")

    sweeper = Sweeper(job, interval_seconds=0.02)
    sweeper.start()
    assert wait_until(lambda: len(attempts) >= 3)  # it kept going after the failure
    sweeper.stop()
    assert "background sweep failed" in caplog.text


def test_stopping_does_not_wait_for_the_interval_to_pass():
    sweeper = Sweeper(lambda: None, interval_seconds=3600)
    sweeper.start()
    started = time.monotonic()
    sweeper.stop()
    assert time.monotonic() - started < 2


def test_the_running_app_removes_abandoned_games_by_itself(settings):
    """No request, no cleanup call: just the app running, as it does in Docker."""
    quick = replace(settings, game_ttl_minutes=0.0005, sweep_interval_minutes=0.002)  # 0.03 s limit, sweep every 0.12 s
    with TestClient(create_app(quick)) as client:  # entering the block starts the app and its sweep
        code = client.post("/api/games", json={"mode": "solo"}).json()["code"]
        with sqlite3.connect(settings.db_path) as conn:
            conn.execute("UPDATE games SET updated_at = 0")  # nobody has played it for ages

        def gone():
            with sqlite3.connect(settings.db_path) as conn:
                return conn.execute("SELECT 1 FROM games WHERE code = ?", (code,)).fetchone() is None

        assert wait_until(gone)


def test_a_game_that_is_still_fresh_is_left_alone_by_the_sweep(settings):
    quick = replace(settings, game_ttl_minutes=60, sweep_interval_minutes=0.002)  # sweeps often, limit one hour
    with TestClient(create_app(quick)) as client:
        code = client.post("/api/games", json={"mode": "solo"}).json()["code"]
        time.sleep(0.5)  # several sweeps happen
        with sqlite3.connect(settings.db_path) as conn:
            assert conn.execute("SELECT 1 FROM games WHERE code = ?", (code,)).fetchone() is not None
