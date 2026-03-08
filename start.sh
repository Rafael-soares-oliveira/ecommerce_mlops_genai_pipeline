#!/bin/bash

set -e

echo "Iniciando Stack Ecommerce MLOps & GenAI Pipeline..."

# 1. Carrega variáveis
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "Erro: .env não encontrado."
    exit 1
fi

# 2. Verificação de variáveis essenciais
required_vars=("POSTGRES_USER" "POSTGRES_PASSWORD" "POSTGRES_DB" "OLLAMA_MODEL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Erro: Variável de ambiente $var não definida em .env"
        exit 1
    fi
done

# 3. Verificação de GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Nvidia detectada. Ativando suporte..."
    DOCKER_BUILDKIT=1 DOCKER_CONTEXT=default
else
    echo "GPU não detectada. Ollama rodará em CPU."
fi

# ============================================
# 4. Docker Compose Profile Selection
# ============================================
COMPOSE_FLAGS=""

echo ""
echo "Selecione os serviços a executar:"
read -p "  ✓ Incluir PgAdmin para debug? [y/N] " -n 1 -r debug_choice
echo
if [[ $debug_choice =~ ^[Yy]$ ]]; then
    COMPOSE_FLAGS="$COMPOSE_FLAGS --profile debug"
    echo "  ℹ️  PgAdmin: http://localhost:$PGADMIN_PORT"
fi

# ============================================
# 5. Build Decision
# ============================================
echo ""
read -p "Deseja fazer rebuild das imagens? [y/N] " -n 1 -r build_choice
echo

if [[ $build_choice =~ ^[Yy]$ ]]; then
    echo "🔨 Construindo imagens Docker..."
    BUILD_FLAG="--build"
    if command -v nvidia-smi &> /dev/null; then
        DOCKER_BUILDKIT=1 docker compose $COMPOSE_FLAGS build --no-cache
    fi
else
    BUILD_FLAG=""
fi

# ============================================
# 6. Start Services
# ============================================
echo ""
echo "🚀 Iniciando serviços..."
docker compose up -d $COMPOSE_FLAGS $BUILD_FLAG

# ============================================
# 7. Wait for Services
# ============================================
echo ""
echo "⏳ Aguardando serviços ficarem online..."
sleep 8

# ============================================
# 8. Health Checks
# ============================================
echo ""
echo "🏥 Verificando saúde dos serviços..."

# Check PostgreSQL
if docker ps -a | grep -q thelook_postgres; then
    if docker exec thelook_postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" &> /dev/null; then
        echo "  ✅ PostgreSQL online"
    else
        echo "  ⚠️  PostgreSQL ainda inicializando..."
    fi
fi

# Check Ollama
if docker ps -a | grep -q ollama-service; then
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo "  ✅ Ollama online"
    else
        echo "  ⚠️  Ollama ainda inicializando..."
    fi
fi

# ============================================
# 9. Ollama Model Management
# ============================================
if docker ps | grep -q ollama-service; then
    echo ""
    echo "📦 Gerenciando modelo Ollama: $OLLAMA_MODEL"

    if docker exec ollama-service ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
        echo "  ✅ Modelo $OLLAMA_MODEL já presente"
    else
        echo "  📥 Baixando modelo $OLLAMA_MODEL..."
        echo "     (Esta operação pode levar vários minutos na primeira execução)"
        docker exec -it ollama-service ollama pull "$OLLAMA_MODEL"
    fi
fi

# ============================================
# 10. Service URLs
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Stack Online!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Serviços Disponíveis:"
echo "  • Streamlit:     http://localhost:$STREAMLIT_PORT"
if [[ $debug_choice =~ ^[Yy]$ ]]; then
    echo "  • PgAdmin:       http://localhost:$PGADMIN_PORT"
fi
if [[ -n "$KEDRO_PORT" ]]; then
    if [[ $debug_choice =~ ^[Yy]$ ]]; then
        echo "  • Kedro Viz:     http://localhost:$KEDRO_PORT"
    fi
fi
echo ""
echo "🔧 Útil para troubleshooting:"
echo "  • Ver logs:      docker compose logs -f"
echo "  • Status:        docker compose ps"
echo "  • Stats:         docker stats"
echo "PgAdmin: http://localhost:$PGADMIN_PORT"
