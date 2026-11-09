"""HTTP layer: routes, request validation and error mapping. No game logic lives here."""

from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.rules import GameError
from app.service import BadToken, GameService
from app.views import GameView

router = APIRouter(prefix="/api/games")


class CreateGameRequest(BaseModel):
    mode: Literal["solo", "race"]


class GuessRequest(BaseModel):
    # Only the size is limited here. Whether it is a valid guess is the rules' decision,
    # so the browser gets the same error shape for every kind of refusal.
    guess: str = Field(max_length=32)
    # How many guesses the client believes it has made. Optional; see rules.submit_guess.
    index: int | None = Field(default=None, ge=0)


class CreatedGame(BaseModel):
    code: str
    token: str  # the player's secret. It is sent once, here, and kept by the browser.
    game: GameView


def get_service(request: Request) -> GameService:
    return request.app.state.service


def require_token(x_player_token: str | None = Header(default=None)) -> str:
    if not x_player_token:
        raise BadToken()
    return x_player_token


@router.post("", status_code=201)
def create_game(body: CreateGameRequest, service: GameService = Depends(get_service)) -> CreatedGame:
    token, game = service.create_game(body.mode)
    return CreatedGame(code=game.code, token=token, game=game)


@router.get("/{code}")
def get_game(
    code: str,
    token: str = Depends(require_token),
    service: GameService = Depends(get_service),
) -> GameView:
    return service.get_game(code, token)


@router.post("/{code}/guesses")
def submit_guess(
    code: str,
    body: GuessRequest,
    token: str = Depends(require_token),
    service: GameService = Depends(get_service),
) -> GameView:
    return service.submit_guess(code, token, body.guess, body.index)


# --- Errors --------------------------------------------------------------------

# Anything not listed here is a "conflict with the current state of the game" (409):
# GAME_NOT_STARTED, GAME_OVER, NO_GUESSES_LEFT, STALE_INDEX, ROOM_FULL.
_STATUS_BY_CODE = {
    "BAD_FORMAT": 422,
    "NOT_A_WORD": 422,
    "NOT_FOUND": 404,
    "BAD_TOKEN": 401,
    "NOT_IN_GAME": 401,
}


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def register_error_handlers(app: FastAPI) -> None:
    """Every error leaves as {"error": {"code": ..., "message": ...}}."""

    @app.exception_handler(GameError)
    async def handle_game_error(request: Request, exc: GameError) -> JSONResponse:
        return _error(_STATUS_BY_CODE.get(exc.code, 409), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_bad_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Deliberately generic: the details would echo the caller's input back.
        return _error(422, "BAD_REQUEST", "The request body is not valid.")
