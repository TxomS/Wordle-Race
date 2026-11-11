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
        lobby_max_wait_seconds: float,
        lobby_silence_seconds: float,
        rng: random.Random | None = None,
    ) -> None:
        self.store = store
        self.words = words
        self.presence = presence
        self.ttl_seconds = ttl_seconds  # for a game being played
        self.finished_ttl_seconds = finished_ttl_seconds  # for a game that has finished
        self.lobby_max_wait_seconds = lobby_max_wait_seconds  # longest a lobby may wait for a second player
        self.lobby_silence_seconds = lobby_silence_seconds  # how long a lobby survives its creator leaving
        self.rng = rng  # tests can pass a seeded Random; None means secure randomness

    def cleanup(self) -> int:
        """Delete abandoned games. There are three kinds, each with its own rule.

        A game being played is abandoned when BOTH hold:
          - nobody has guessed in it for longer than the time limit (15 minutes), and
          - no player's page has asked the server about it for longer than that.
        The second rule keeps a game alive while someone still has it open, like a player
        who walked away to think.

        A finished game uses the same rule with a short limit (2 minutes): its result has
        been shown, and a page stops asking about a game once it has seen it finish.

        A lobby (a race waiting for its second player) is abandoned when EITHER holds:
          - it has been waiting longer than the maximum wait (15 minutes), even if its
            creator is still looking at it, or
          - nobody has asked about it for a couple of minutes (the creator closed the tab).
        A lobby has no progress to protect, so nobody is kept waiting in a page that is gone.

        After a backend restart, players not yet seen get a short benefit of the doubt (see
        presence.py). The background sweep (sweeper.py) calls this every minute."""
        now = time.time()  # the database stores wall-clock times
        with self.store.write() as conn:
            stale = self.store.list_idle(conn, now - self.ttl_seconds, rules.PLAYING)
            stale += self.store.list_idle(conn, now - self.finished_ttl_seconds, rules.FINISHED)
            abandoned = [game.code for game in stale if not self._someone_is_here(game)]
            for lobby, created in self.store.list_waiting(conn):
                waited_too_long = now - created > self.lobby_max_wait_seconds
                if waited_too_long or not self._someone_is_here(lobby, self.lobby_silence_seconds):
                    abandoned.append(lobby.code)
            removed = self.store.delete(conn, abandoned)
        if removed:
            log.info("removed %d abandoned game(s)", removed)
        return removed

    def _someone_is_here(self, game: Game, window: float | None = None) -> bool:
        """Has any player of this game been heard from within the window? By default the
        window is the game's own limit: short once finished, long while being played."""
        if window is None:
            window = self.finished_ttl_seconds if game.status == rules.FINISHED else self.ttl_seconds
        return any(self.presence.seen_within(game.code, p.id, window) for p in game.players)

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
        """Get a seat in a game, and the token for it.

        - If a seat is free, take it.
        - If not, but a player has disconnected (the same "Disconnected" the other player
          sees), take over that seat. The newcomer carries on from the same board, and the
          old player's token stops working. This is how someone who closed the tab and lost
          it gets back in, just by using the game's code again.
        - Otherwise the game is full (ROOM_FULL).

        The write lock means that if two people arrive at the same moment, they cannot both
        get the same seat."""
        token = new_token()
        player_id = hash_token(token)
        took_over = False
        with self.store.write() as conn:
            game = self.store.load(conn, _clean_code(code))
            if game is None:
                raise GameNotFound()
            if len(game.players) < game.capacity:
                rules.add_player(game, player_id)
            else:
                seat = self._disconnected_seat(game)
                rules.take_over_seat(game, seat.id, player_id)
                took_over = True
            self.store.save(conn, game)
            # Done inside the transaction, before anyone else can get the lock: otherwise a
            # second newcomer could look, see the seat's new owner as "not seen yet", and
            # take the same seat again.
            self.presence.touch(game.code, player_id)
        if took_over:
            log.info("player took over a disconnected seat code=%s player=%d", game.code, _player_number(game, player_id))
        else:
            log.info("player joined code=%s player=%d", game.code, _player_number(game, player_id))
        return token, self._view(game, player_id)

    def _disconnected_seat(self, game: Game):
        """The seat a newcomer may take: one whose player shows as disconnected. If both do,
        the one that has been silent the longest, since that is the likelier one to belong
        to somebody who is not coming back."""
        gone = [p for p in game.players if not self.presence.is_connected(game.code, p.id)]
        if not gone:
            raise rules.RoomFull()
        return max(gone, key=lambda p: self.presence.silent_for(game.code, p.id))

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
