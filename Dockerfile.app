FROM astral/uv:python3.13-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    HF_HOME=/app/model_cache \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Instala dependências de sistema essenciais
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# 2. Copia apenas os arquivos de definição
COPY pyproject.toml uv.lock README.md ./

# 3. Sincroniza as bibliotecas sem instalar o projeto local ainda
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group heavy --no-install-project

# 4. Cache do Modelo
ARG EMBEDDING_MODEL_NAME
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

# 5. Copia o restante do código
COPY . .

# 6. Sincronização final do projeto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group heavy

# Expor a porta padrão do Streamlit
EXPOSE 8501

# O comando definitivo é gerenciado pelo docker-compose.yml
CMD ["uv", "run", "streamlit", "run", "src/app.py"]
