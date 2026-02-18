FROM docker.io/library/postgres:18

USER root

RUN apt-get update && apt-get install -y \
    curl \
    postgresql-18-postgis-3 \
    postgresql-18-pgvector \
    && curl -s https://packagecloud.io/install/repositories/timescale/timescaledb/script.deb.sh | bash \
    && apt-get install -y timescaledb-2-postgresql-18 timescaledb-toolkit-postgresql-18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configura o loader e roda o tune de forma automática (prevendo 2GB de RAM, ajuste se necessário)
RUN echo "shared_preload_libraries = 'timescaledb,pg_stat_statements,vector'" >> /usr/share/postgresql/postgresql.conf.sample \
    && timescaledb-tune --quiet --yes --memory=4GB --cpus=4 --conf-path=/usr/share/postgresql/postgresql.conf.sample

USER postgres
