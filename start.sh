#!/bin/bash

set -e

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
                          count: all
                          capabilities: [gpu]
EOF
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
else
    echo "GPU não detectada. Ollama rodará em CPU."
fi

# 3. BUILD & START
echo "Construindo e subindo serviços..."
docker compose $COMPOSE_FILES up -d --build

# 4. OLLAMA
echo "Verificando modelo Ollama ($OLLAMA_MODEL)..."
docker compose exec -d ollama ollama pull $OLLAMA_MODEL

echo "Ambiente Online!"
echo "Streamlit: http://localhost:$STREAMLIT_PORT"
echo "Kedro Viz: http://localhost:$KEDRO_PORT"
echo "PgAdmin: http://localhost:$PGADMIN_PORT"
