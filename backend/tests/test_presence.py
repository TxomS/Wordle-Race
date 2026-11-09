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


def test_seen_within_answers_for_the_window_it_is_given():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(600)
    assert presence.seen_within("G1", "p1", 900)
    assert not presence.seen_within("G1", "p1", 600)


def test_a_player_not_seen_since_startup_gets_two_minutes_of_benefit_of_the_doubt():
    presence, clock = make()
    assert presence.seen_within("G1", "never-seen", 900)  # asked about a 15-minute window
    clock.advance(119)
    assert presence.seen_within("G1", "never-seen", 900)
    clock.advance(1)  # two minutes since startup
    assert not presence.seen_within("G1", "never-seen", 900)


def test_the_grace_is_never_longer_than_the_question_being_asked():
    presence, clock = make()
    assert presence.seen_within("G1", "never-seen", 15)
    clock.advance(15)  # a 15-second question gets at most 15 seconds of grace
    assert not presence.seen_within("G1", "never-seen", 15)


def test_the_grace_period_can_be_changed():
    clock = Clock()
    presence = Presence(15.0, clock, grace_seconds=30)
    clock.advance(29)
    assert presence.seen_within("G1", "never-seen", 900)
    clock.advance(1)
    assert not presence.seen_within("G1", "never-seen", 900)


def test_how_long_entries_are_remembered_can_be_changed():
    clock = Clock()
    presence = Presence(15.0, clock, remember_seconds=100)
    presence.touch("G1", "p1")
    clock.advance(200)
    presence.touch("G2", "p2")  # triggers the clean-up
    assert ("G1", "p1") not in presence._last_seen


def test_old_entries_are_forgotten_so_memory_does_not_grow_forever():
    presence, clock = make()
    presence.touch("G1", "p1")
    clock.advance(4000)  # more than an hour
    presence.touch("G2", "p2")  # touching triggers the periodic clean-up
    assert ("G1", "p1") not in presence._last_seen
    assert ("G2", "p2") in presence._last_seen
