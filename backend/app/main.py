from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Every route lives under /api so that nginx can send /api/* to this service and
    everything else to the React app. The interactive docs are at /api/docs.
    """
    app = FastAPI(
        title="Wordle Race",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        # Used by the Docker healthcheck and by the hello page.
        return {"status": "ok"}

    return app


app = create_app()
