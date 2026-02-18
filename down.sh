#!/bin/bash

echo "Parando e removendo Containers..."

# Remove containers e rede, mantém volumes por padrão
docker compose down

# Pergunta sobre volumes
read -p "Deseja apagar também os volumes persistentes? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removendo volumes..."
    docker compose down -v

    # Remove arquivo temporário de GPU se existir
    rm -f docker-compose.gpu.yml
    echo "Tudo limpo."

else
    echo "Volumes mantidos."
fi
