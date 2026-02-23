FROM docker.io/library/python:3.13-slim-bookworm
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    HF_HOME=/app/model_cache \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

# 1. Instala dependências (Camada estática)
COPY pyproject.toml uv.lock README.md ./

# Estrutura mínima para o Hatchling não falhar a build
COPY src/thelook_ecommerce_analysis/__init__.py src/thelook_ecommerce_analysis/__init__.py

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group heavy --no-install-project

# 2. Cache do Modelo (Só invalida se o ARG mudar)
ARG EMBEDDING_MODEL_NAME
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

# 3. Código fonte (Última camada, muda com frequência)
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group heavy
