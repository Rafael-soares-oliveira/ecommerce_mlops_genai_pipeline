CREATE TABLE IF NOT EXISTS raw_data.users (
    id INTEGER PRIMARY KEY,
    age SMALLINT CHECK (age > 0),
    gender TEXT CHECK (gender IN ('M', 'F')),
    state TEXT COLLATE case_insensitive,
    city TEXT  COLLATE case_insensitive,
    country TEXT COLLATE case_insensitive,
    latitude DOUBLE PRECISION CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION CHECK (longitude BETWEEN -180 AND 180),
    traffic_source TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    context_summary TEXT,
    user_geom GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
    ) STORED
);

-- Comentários para o LLM (Text-to-SQL)
COMMENT ON TABLE raw_data.users IS 'Dados demográficos dos usuários. Use para filtrar localização, idade ou origem de tráfego.';
COMMENT ON COLUMN raw_data.users.context_summary IS 'Resumo textual do perfil do usuário. Idela para busca semântica e similaridade.';
COMMENT ON COLUMN raw_data.users.user_geom IS 'Localização espacial. Use funções PostGIS como ST_DWithin para cálculos de distância.';
