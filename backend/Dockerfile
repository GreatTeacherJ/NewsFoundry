FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/src/ ./src/

EXPOSE 8000

CMD [".venv/bin/python", "src/main.py"]