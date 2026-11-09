"""The use cases: create a game, join it, read it, submit a guess.

Each one follows the same shape: load the game from the store, apply a rule from
rules.py, save, and return what the player is allowed to see (views.py).
Changes run inside one store.write() transaction, so they never interleave.
Every successful request also records that the player was just seen (presence.py).
"""

import hashlib
import random
import secrets

from app import rules
from app.presence import Presence
from app.rules import Game, GameError
from app.store import GameStore
from app.views import GameView, game_view
from app.words import WordLists, pick_answer

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


class GameService:
    def __init__(
        self,
        store: GameStore,
        words: WordLists,
        presence: Presence,
        rng: random.Random | None = None,
    ) -> None:
        self.store = store
        self.words = words
        self.presence = presence
        self.rng = rng  # tests can pass a seeded Random; None means secure randomness

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
        return self._view(game, player_id)

    def _view(self, game: Game, player_id: str) -> GameView:
        opponent = next((p for p in game.players if p.id != player_id), None)
        connected = opponent is not None and self.presence.is_connected(game.code, opponent.id)
        return game_view(game, player_id, opponent_connected=connected)
