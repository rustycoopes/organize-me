# ---- Build stage: compiles the Tailwind CSS build. The ~35-40MB Tailwind CLI binary and the
# build-only Python packages that fetch it never reach the runtime image below - see
# docs/adr/design-refresh-per-service-tailwind-build.md. The compile step (below) is a separate
# RUN layer from `COPY app`, but Docker's cache invalidation still cascades correctly: any change
# under app/ invalidates `COPY app` and therefore forces the compile layer to rerun too, so cached
# CSS can never silently drift out of sync with the templates it was built from.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --group build --no-install-project

COPY app ./app
COPY scripts ./scripts
RUN uv run python scripts/build_css.py

# ---- Runtime stage: no Tailwind CLI, no build-only Python packages - only the compiled
# stylesheet and fonts are copied in from the builder stage.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends supervisor git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY supervisord.conf ./supervisord.conf
COPY --from=builder /app/app/static/css/app.css ./app/static/css/app.css
COPY --from=builder /app/app/static/fonts ./app/static/fonts

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
