"""Unit tests for the presence tracker, using a fake clock."""

from app.presence import Presence
from conftest import Clock


def make(timeout=15.0):
    clock = Clock()
    return Presence(timeout, clock), clock


def test_a_player_heard_from_recently_is_connected():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(14)
    assert presence.is_connected("G1", "p1")


def test_a_player_silent_for_the_whole_timeout_is_disconnected():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(15)  # exactly the timeout: no longer connected
    assert not presence.is_connected("G1", "p1")


def test_touching_again_brings_a_player_back():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(30)
    assert not presence.is_connected("G1", "p1")
    presence.touch("G1", "p1")
    assert presence.is_connected("G1", "p1")


def test_an_unseen_player_is_assumed_present_only_right_after_startup():
    presence, clock = make()
    assert presence.is_connected("G1", "never-seen")  # the process just started
    clock.advance(15)
    assert not presence.is_connected("G1", "never-seen")  # a real absence now shows


def test_players_are_tracked_per_game():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(20)
    presence.touch("G2", "p1")
    assert presence.is_connected("G2", "p1")
    assert not presence.is_connected("G1", "p1")


def test_old_entries_are_forgotten_so_memory_does_not_grow_forever():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(4000)  # more than an hour
    presence.touch("G2", "p2")  # touching triggers the periodic clean-up
    assert ("G1", "p1") not in presence._last_seen
    assert ("G2", "p2") in presence._last_seen
