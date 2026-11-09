"""The use cases: create a game, join it, read it, submit a guess, and clean up.

Each game use case follows the same shape: load the game from the store, apply a rule
from rules.py, save, and return what the player is allowed to see (views.py).
Changes run inside one store.write() transaction, so they never interleave.
Every successful request also records that the player was just seen (presence.py).

Logging: key events are logged (a game created, a player joined, a guess accepted, a
game finished), identified by the game code. Logs never contain the hidden word, the
words players guess, or tokens: whoever reads the logs must learn nothing that the
players are not allowed to see.
"""

import hashlib
import logging
import random
import secrets
import time

from app import rules
from app.presence import Presence
from app.rules import Game, GameError
from app.store import GameStore
from app.views import GameView, game_view
from app.words import WordLists, pick_answer

log = logging.getLogger("wordle")

# Room codes avoid look-alike characters: no I, L, O, 0 or 1. 31 symbols ^ 5 places = 28 million codes.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 5
_MAX_CODE_ATTEMPTS = 10


class GameNotFound(GameError):
    code = "NOT_FOUND"
    message = "No game with that code."


class BadToken(GameError):
    code = "BAD_TOKEN"
    message = "Missing player token."


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def new_token() -> str:
    return secrets.token_urlsafe(16)


def hash_token(token: str) -> str:
    """The database stores only this hash, never the token itself. The browser keeps the
    token; a leaked database therefore does not let anyone act as a player."""
    return hashlib.sha256(token.encode()).hexdigest()


def _clean_code(code: str) -> str:
    return code.strip().upper()


def _player_id(token: str) -> str:
    if not token:
        raise BadToken()
    return hash_token(token)


def _player_number(game: Game, player_id: str) -> int:
    return 1 + [player.id for player in game.players].index(player_id)


def _describe_result(game: Game) -> str:
    if game.winner_id is None:
        return "nobody won"
    return f"player {_player_number(game, game.winner_id)} won"


class GameService:
    def __init__(
        self,
        store: GameStore,
        words: WordLists,
        presence: Presence,
        ttl_seconds: float,
        finished_ttl_seconds: float,
        rng: random.Random | None = None,
    ) -> None:
        self.store = store
        self.words = words
        self.presence = presence
        self.ttl_seconds = ttl_seconds  # for a game being played or waited for
        self.finished_ttl_seconds = finished_ttl_seconds  # for a game that has finished
        self.rng = rng  # tests can pass a seeded Random; None means secure randomness

    def cleanup(self) -> int:
        """Delete abandoned games. A game is abandoned when BOTH hold:
          - nobody has guessed in it or joined it for longer than its time limit, and
          - no player's page has asked the server about it for longer than that limit.
        The second rule keeps a game alive while someone still has it open: a lobby
        waiting for a friend, or a player who walked away to think.

        The limit is long (15 minutes by default) for a game that is still being played or
        waited for, and short (2 minutes) for a game that has finished: its result has been
        shown, and a page stops asking about a game once it has seen it finish. Two minutes
        is still enough for a slow background tab to ask once more and see who won.

        After a backend restart, players not yet seen get a short benefit of the doubt (see
        presence.py). The background sweep (sweeper.py) calls this every minute."""
        now = time.time()  # the database stores wall-clock times
        with self.store.write() as conn:
            stale = self.store.list_idle(conn, now - self.ttl_seconds, finished=False)
            stale += self.store.list_idle(conn, now - self.finished_ttl_seconds, finished=True)
            abandoned = [game.code for game in stale if not self._someone_is_here(game)]
            removed = self.store.delete(conn, abandoned)
        if removed:
            log.info("removed %d abandoned game(s)", removed)
        return removed

    def _someone_is_here(self, game: Game) -> bool:
        limit = self.finished_ttl_seconds if game.status == rules.FINISHED else self.ttl_seconds
        return any(self.presence.seen_within(game.code, p.id, limit) for p in game.players)

    def create_game(self, mode: str) -> tuple[str, GameView]:
        """Create a game with its first player. Returns that player's secret token and view."""
        token = new_token()
        player_id = hash_token(token)
        answer = pick_answer(self.words.answers, self.rng)

        for _ in range(_MAX_CODE_ATTEMPTS):
            game = rules.new_game(new_code(), answer, mode)
            rules.add_player(game, player_id)
            with self.store.write() as conn:
                created = self.store.insert(conn, game)
            if created:
                self.presence.touch(game.code, player_id)
                log.info("game created code=%s mode=%s", game.code, mode)
                return token, self._view(game, player_id)
        raise RuntimeError("could not find a free game code")

    def join_game(self, code: str) -> tuple[str, GameView]:
        """Take the free seat in a game. The write lock means that if two people join the
        last seat at the same moment, exactly one gets it and the other gets ROOM_FULL."""
        token = new_token()
        player_id = hash_token(token)
        with self.store.write() as conn:
            game = self.store.load(conn, _clean_code(code))
            if game is None:
                raise GameNotFound()
            rules.add_player(game, player_id)
            self.store.save(conn, game)
        self.presence.touch(game.code, player_id)
        log.info("player joined code=%s player=%d", game.code, _player_number(game, player_id))
        return token, self._view(game, player_id)

    def get_game(self, code: str, token: str) -> GameView:
        """Read-only: used for polling and for coming back after a refresh."""
        player_id = _player_id(token)
        with self.store.read() as conn:
            game = self.store.load(conn, _clean_code(code))
        if game is None:
            raise GameNotFound()
        view = self._view(game, player_id)  # refuses strangers, so only real players are tracked
        self.presence.touch(game.code, player_id)
        return view

    def submit_guess(self, code: str, token: str, word: str, expected_index: int | None = None) -> GameView:
        player_id = _player_id(token)
        with self.store.write() as conn:
            game = self.store.load(conn, _clean_code(code))
            if game is None:
                raise GameNotFound()
            rules.submit_guess(game, player_id, word, self.words.allowed, expected_index)
            self.store.save(conn, game)
        self.presence.touch(game.code, player_id)

        player = rules.get_player(game, player_id)
        log.info(
            "guess accepted code=%s player=%d guesses=%d",
            game.code,
            _player_number(game, player_id),
            len(player.guesses),
        )
        if game.status == rules.FINISHED:
            log.info("game finished code=%s result=%s", game.code, _describe_result(game))
        return self._view(game, player_id)

    def _view(self, game: Game, player_id: str) -> GameView:
        opponent = next((p for p in game.players if p.id != player_id), None)
        connected = opponent is not None and self.presence.is_connected(game.code, opponent.id)
        return game_view(game, player_id, opponent_connected=connected)
