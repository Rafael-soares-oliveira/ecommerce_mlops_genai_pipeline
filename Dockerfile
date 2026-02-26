FROM tensorchord/vchord-postgres:pg18-v1.1.0

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg && \
    curl -fSsL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/apt.postgresql.org.gpg && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list

# Instalando extensões
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-18-postgis-3 \
    postgresql-18-timescaledb \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "shared_preload_libraries = 'timescaledb,vchord,pg_stat_statements'" >> /usr/share/postgresql/postgresql.conf.sample

USER postgres
