CREATE TABLE IF NOT EXISTS embeddings.products_embeddings (
    id SERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL,
    chunk_text TEXT NOT NULL,

    -- Colunas de Metadados (Para pré-filtragem rápida)
    brand TEXT,
    category TEXT,
    department TEXT,
    retail_price DOUBLE PRECISION,

    -- O Vetor (384 dimensões para all-MiniLM-L6-v2) - Mudar quando necessário
    embedding vector(384),

    CONSTRAINT fk_embedding_product
        FOREIGN KEY (source_id)
        REFERENCES raw_data.products (id)
        ON DELETE CASCADE
);

-- Comentários para products_embeddings
COMMENT ON TABLE embeddings.products_embeddings IS 'Tabela de busca semântica para produtos usando pgvector. Use para encontrar produtos similares por contexto textual.';
COMMENT ON COLUMN embeddings.products_embeddings.chunk_text IS 'Texto original que gerou o vetor. Retorne esta coluna no SELECT.';
COMMENT ON COLUMN embeddings.products_embeddings.embedding IS 'Vetor (384 dim). OBRIGATÓRIO usar operador <=> com placeholder para ordenação de similaridade.';
