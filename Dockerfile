# ---- Build stage: compiles the Tailwind CSS build. The ~35-40MB Tailwind CLI binary and the
# build-only Python packages that fetch it never reach the runtime image below - see
# docs/adr/design-refresh-per-service-tailwind-build.md. Must stay in the same layer/step as the
# dependency install immediately above it (never cached independently) so a Docker layer-caching
# bug can't serve CSS compiled against a stale template set.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --group build --no-install-project

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
