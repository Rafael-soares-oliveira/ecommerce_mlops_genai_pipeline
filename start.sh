#!/bin/bash

set -e

# Remover em caso de encerramento forçado
trap 'rm -f docker-compose.gpu.yml' EXIT

echo "Iniciando Stack Ecommerce MLOps & GenAI Pipeline..."

# 1. Carrega variáveis
if [ -f .env ]; then
    set -a; source .env; set +a;
else
    echo "Erro: .env não encontrado."
    exit 1
fi

# 2. Lógica de detecção de GPU
COMPOSE_FILES="-f docker-compose.yml"

if command -v nvidia-smi &> /dev/null; then
    echo "GPU Nvidia detectada. Ativando suporte..."
    # Cria um override temporário para GPU
    cat <<EOF > docker-compose.gpu.yml
services:
    ollama:
        deploy:
            resources:
                reservations:
                    devices:
                        - driver: nvidia
                          count: 1
                          capabilities: [gpu]
EOF
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
else
    echo "GPU não detectada. Ollama rodará em CPU."
fi

# 3. BUILD & START
echo "Construindo e subindo serviços..."

read -p "Deseja executar com flag --build? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Executando docker compose up -d --build..."
    docker compose $COMPOSE_FILES up -d --build

else
    echo "Executando docker compose up -d..."
    docker compose $COMPOSE_FILES up -d
fi

# 4. OLLAMA
echo "Verificando modelo Ollama ($OLLAMA_MODEL)..."
if ! docker compose exec ollama ollama show "$OLLAMA_MODEL" > /dev/null 2>&1; then
    echo "Modelo não encontrado. Baixando $OLLAMA_MODEL..."
    docker compose exec ollama ollama pull "$OLLAMA_MODEL"
fi

echo "Ambiente Online!"
echo "Streamlit: http://localhost:$STREAMLIT_PORT"
echo "Kedro Viz: http://localhost:$KEDRO_PORT"
echo "PgAdmin: http://localhost:$PGADMIN_PORT"
