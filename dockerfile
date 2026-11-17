FROM ghcr.io/astral-sh/uv:0.12.5-python3.12-alpine3.23 AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apk add --no-cache build-base postgresql-dev libffi-dev zlib-dev

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY etl/ ./etl/
COPY data/ ./data/
COPY sql/ ./sql/


FROM python:3.12-alpine3.23

WORKDIR /app

RUN apk add --no-cache libpq postgresql-client \
    && addgroup -S appuser && adduser -S -G appuser -h /app appuser

COPY --from=builder --chown=appuser:appuser /app .

ENV PATH="/app/.venv/bin:$PATH"

USER appuser

CMD ["sh", "-c", "psql -f sql/init.sql && python etl/etl.py && psql -f sql/analytics.sql"]