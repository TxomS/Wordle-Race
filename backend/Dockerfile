FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Install dependencies first so Docker can cache this layer between code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# Test image: the same code plus the test tools and the tests. Used by `make test`.
FROM base AS test
COPY requirements-dev.txt pytest.ini ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
CMD ["pytest"]

# Final image: runs as a non-root user. /data is created and owned by that user
# BEFORE the volume is mounted, so a brand-new named volume is writable by it
# (otherwise SQLite cannot create its file on a fresh machine).
FROM base AS runtime
RUN useradd --system --no-create-home app \
    && mkdir /data \
    && chown app:app /data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
