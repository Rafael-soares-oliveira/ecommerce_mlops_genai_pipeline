FROM docker.io/library/python:3.13-slim-bookworm
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/



# Cache para modelos do Hugging Face (sentence-transformers
ENV UV_LINK_MODE=copy \
    HF_HOME=/app/model_cache \
    UV_PROJECT_ENVIRONMENT="/venv" \
    PATH="/venv/bin:$PATH" \
    # Garante que o Python encontre os módulos em src/
    PYTHONPATH=/app/src:${PYTHONPATH} \
    # Evita criação de .pyc dentro do container
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalação das depedências mínimas do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

# --- CAMADA 1: Dependências Python ---
# Copia apenas os arquivos de definição. Se eles não mudarem, essa etapa é pulada.
COPY pyproject.toml uv.lock ./

ARG UV_CONCURRENT_DOWNLOADS=10
ARG UV_CONCURRENT_BUILDS=4

# Instala as depedências e pré-baixa o modelo no build
# --no-install-project impede que ele tente ler o código agora
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group heavy --no-install-project

# --- CAMADA 2: Cache do Modelo (O Segredo está aqui) ---
# Recebe o nome do modelo como argumento de build
ARG EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"

# Roda um script Python simples APENAS para baixar o modelo e salvar no HF_HOME.
# Se o ARG mudar, essa camada é invalidada e ele baixa o novo.
RUN --mount=type=cache,target=/root/.cache/uv \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

# Copia o código fonte
COPY . .

# Instala o projeto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group heavy

CMD ["uv", "run", "streamlit", "run", "src/app.py"]
