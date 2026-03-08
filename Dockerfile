FROM tensorchord/vchord-postgres:pg18-v1.1.0

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-18-postgis-3 \
    postgresql-18-timescaledb \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "shared_preload_libraries = 'timescaledb,vchord,pg_stat_statements'" >> /usr/share/postgresql/postgresql.conf.sample

USER postgres
