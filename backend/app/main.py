import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api import register_error_handlers, router
from app.config import Settings, load_settings
from app.presence import Presence
from app.service import GameService
from app.store import GameStore
from app.sweeper import Sweeper
from app.words import load_word_lists

log = logging.getLogger("wordle")


def create_app(settings: Settings | None = None, clock: Callable[[], float] = time.monotonic) -> FastAPI:
    """Build the application. Tests pass their own Settings (temporary database, small
    word lists) and a fake clock; the real server calls this through `uvicorn --factory`
    with no arguments."""
    settings = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Fail fast: a broken word list or an unusable database stops the app at startup.
    words = load_word_lists(settings.words_dir)
    store = GameStore(settings.db_path)
    ttl_seconds = settings.game_ttl_minutes * 60
    # Presence must be remembered at least as long as the cleanup asks about it.
    presence = Presence(settings.presence_timeout_seconds, clock, remember_seconds=max(3600, ttl_seconds))
    service = GameService(
        store,
        words,
        presence,
        ttl_seconds=ttl_seconds,
        finished_ttl_seconds=settings.finished_game_ttl_minutes * 60,
        lobby_max_wait_seconds=settings.lobby_max_wait_minutes * 60,
        lobby_silence_seconds=settings.lobby_silence_minutes * 60,
    )
    sweeper = Sweeper(service.cleanup, interval_seconds=settings.sweep_interval_minutes * 60)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # The sweep runs only while the app is running (not in tests that skip startup).
        sweeper.start()
        log.info("sweeping for abandoned games every %g minute(s)", settings.sweep_interval_minutes)
        try:
            yield
        finally:
            sweeper.stop()

    # Every route lives under /api so nginx can send /api/* here and everything else
    # to the React app. The interactive docs are at /api/docs.
    app = FastAPI(
        title="Wordle Race",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.service = service
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

    log.info("ready: %d possible answers, %d allowed guesses", len(words.answers), len(words.allowed))
    return app
