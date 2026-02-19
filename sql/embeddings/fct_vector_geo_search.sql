CREATE TABLE IF NOT EXISTS embeddings.fct_vector_geo_search (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL, -- ID original da raw_data.users

    -- Metadados para o RAG e filtros rápidos (Text-to-SQL)
    city TEXT,
    country TEXT,
    avg_spend DOUBLE PRECISION,
    chunk_text TEXT NOT NULL, -- O texto que gerou o embedding (essencial para o RAG)

    -- Coluna Espacial (PostGIS)
    user_geom geography(POINT) NOT NULL,

    -- Coluna Vetorial (pgvector)
    embedding vector(384),

    -- Relacionamento
    CONSTRAINT fk_vsearch_user
        FOREIGN KEY (user_id)
        REFERENCES raw_data.users (id)
        ON DELETE CASCADE
);

-- Comentários para fct_vector_geo_search
COMMENT ON TABLE embeddings.fct_vector_geo_search IS 'Busca híbrida de usuários. Une busca semântica (vetores), filtros de negócio (gasto médio) e raio espacial (PostGIS).';
COMMENT ON COLUMN embeddings.fct_vector_geo_search.avg_spend IS 'Ticket médio de gasto do usuário. Ótimo para pré-filtro.';
COMMENT ON COLUMN embeddings.fct_vector_geo_search.embedding IS 'Vetor semântico do perfil do usuário para busca por similaridade.';
