FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libgl1 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    U2NET_HOME=/models \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev

RUN mkdir -p /models
VOLUME ["/models"]

EXPOSE 8000
# models list | models pull <id> | models pull --all
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
