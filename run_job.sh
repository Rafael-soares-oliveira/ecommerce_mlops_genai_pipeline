#!/bin/bash

set -e

echo "Inciando Job Diário do Kedro: $(date)"

# 1. EPHEMERAL WORKER
docker compose run --rm kedro-worker

# 2. Reinicia o Kedro Viz (para ler os novos dados/experimentos gerados)
echo "Reiniciando Kedro Viz..."

# 3. Reiniciar Streamlit (limpar cache)
echo "Reiniciando Streamlit..."
docker compose restart streamlit


echo "Job finalizado com sucesso."
