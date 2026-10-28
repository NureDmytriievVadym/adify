FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
WORKDIR /app
COPY apps/backend/pyproject.toml apps/backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/backend/src ./src
RUN uv sync --frozen --no-dev && useradd --system --uid 10001 adify
USER adify
EXPOSE 8000
CMD [".venv/bin/uvicorn", "adify_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
