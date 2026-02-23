---------------------------------------------
-- --- 1. Habilita Extensões Fundamentais ---
-- ------------------------------------------

-- Habilita extensão TimescaleDB -> DEVE SER O PRIMEIRO COMANDO
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Habilita extensão de vetores
CREATE EXTENSION IF NOT EXISTS vchord CASCADE;

-- Habilita PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Habilita Hybrid Search (Vector + Keyword) no RAG
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Monitoramento
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

--------------------------------
-- --- 2. Criação de Schemas ---
-- -----------------------------
CREATE SCHEMA IF NOT EXISTS raw_data;
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS embeddings;

-- 4. --- Permissões ---
-- Atualmente, é redundante, mas caso necessite criar outro usuário já está escrito
GRANT ALL PRIVILEGES ON SCHEMA raw_data TO admin;
GRANT ALL PRIVILEGES ON SCHEMA metrics TO admin;
GRANT ALL PRIVILEGES ON SCHEMA embeddings TO admin;

-- Define que novas tabelas criadas nestes scheams terão permissões padrão
ALTER DEFAULT PRIVILEGES IN SCHEMA raw_data GRANT ALL ON TABLES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA metrics GRANT ALL ON TABLES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA embeddings GRANT ALL ON TABLES TO admin;

-- 5. Criar a Collation para buscas robustas no RAG
CREATE COLLATION IF NOT EXISTS case_insensitive (
    provider = 'icu',
    locale = 'und-u-ks-level2',
    deterministic = false
);
