import time
from collections.abc import Callable

from fastapi import FastAPI, Request

from app.api import register_error_handlers, router
from app.config import Settings, load_settings
from app.presence import Presence
from app.service import GameService
from app.store import GameStore
from app.words import load_word_lists


def create_app(settings: Settings | None = None, clock: Callable[[], float] = time.monotonic) -> FastAPI:
    """Build the application. Tests pass their own Settings (temporary database, small
    word lists) and a fake clock; the real server calls this through `uvicorn --factory`
    with no arguments."""
    settings = settings or load_settings()

    # Fail fast: a broken word list or an unusable database stops the app at startup.
    words = load_word_lists(settings.words_dir)
    store = GameStore(settings.db_path)
    presence = Presence(settings.presence_timeout_seconds, clock)

    # Every route lives under /api so nginx can send /api/* here and everything else
    # to the React app. The interactive docs are at /api/docs.
    app = FastAPI(
        title="Wordle Race",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.service = GameService(store, words, presence)
    app.include_router(router)
    register_error_handlers(app)

    @app.middleware("http")
    async def never_cache(request: Request, call_next):
        # Polling must always see fresh state, and no proxy should keep a copy of a game.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        # Used by the Docker healthcheck and by the hello page.
        return {"status": "ok"}

    return app
