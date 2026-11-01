# Development image: source is copied in, then Compose Watch keeps it in sync.
FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY backend/ ./
RUN uv sync --frozen
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn adify_api.main:app --reload --host 0.0.0.0 --port 8000"]
