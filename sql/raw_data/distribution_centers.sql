CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS raw_data.distribution_centers (
    id INTEGER PRIMARY KEY,
    name TEXT COLLATE case_insensitive NOT NULL CONSTRAINT uq_dc_name UNIQUE,
    latitude DOUBLE PRECISION CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION CHECK (longitude BETWEEN -180 AND 180),
    distribution_center_geom GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
    ) STORED
);

-- Comentários para o LLM (Text-to-SQL)
COMMENT ON TABLE raw_data.distribution_centers IS 'Localizações físicas dos centros de distribuição. Use para cálculos de logística, rotas e distâncias.';
COMMENT ON COLUMN raw_data.distribution_centers.name IS 'Nome único do centro de distribuição (case-insensitive).';
COMMENT ON COLUMN raw_data.distribution_centers.distribution_center_geom IS 'Ponto geográfico (PostGIS). Obrigatório para cálculos de distância (ex: ST_Distance) ou junções espaciais com a tabela de usuários.';
