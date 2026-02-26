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

# 2. Verificação de GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Nvidia detectada. Ativando suporte..."
else
    echo "GPU não detectada. Ollama rodará em CPU."
fi

# 3. BUILD & START
echo "Construindo e subindo serviços..."

read -p "Deseja executar com flag --build? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Executando docker compose up -d --build..."
    docker compose up -d --build

else
    echo "Executando docker compose up -d..."
    docker compose up -d
fi

# 4. OLLAMA
echo "Aguardando serviços ficarem online..."
sleep 5

echo "Verificando modelo Ollama ($OLLAMA_MODEL)..."
if ! docker exec ollama-service ollama list | grep -q "$OLLAMA_MODEL"; then
    echo "📥 Baixando modelo $OLLAMA_MODEL..."
    docker exec -it ollama-service ollama pull "$OLLAMA_MODEL"
else
    echo "✅ Modelo $OLLAMA_MODEL já está presente."
fi

echo "---"
echo "Stack Online!"
echo "Streamlit: http://localhost:$STREAMLIT_PORT"
echo "PgAdmin: http://localhost:$PGADMIN_PORT"
