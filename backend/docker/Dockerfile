# Source is bind-mounted by docker-compose.yml.
FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project
EXPOSE 8000
CMD ["uvicorn", "adify_api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
