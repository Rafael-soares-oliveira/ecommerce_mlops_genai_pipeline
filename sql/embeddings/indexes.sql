-- ------------------------------------------------
-- fct_user_logistics
-- ------------------------------------------------
-- Índice GIST para consultas de proximidade rápidas
CREATE INDEX IF NOT EXISTS idx_logistics_user_geom ON embeddings.fct_user_logistics USING GIST (user_geom);

-- ------------------------------------------------
-- fct_vector_geo_search
-- ------------------------------------------------
--- Índices para Busca Híbrida (Geometria + Filtros + Vetores)
-- 1. Índice Espacial (GIST) para ST_DWithin ou filtros geográficos
CREATE INDEX IF NOT EXISTS idx_vsearch_geom
ON embeddings.fct_vector_geo_search USING GIST (user_geom);

-- 2. Índice para filtros de agregação (quem gasta mais)
CREATE INDEX IF NOT EXISTS idx_vsearch_spend
ON embeddings.fct_vector_geo_search (avg_spend DESC);

-- 3. Índice HNSW para busca vetorial de alta performance
-- Nota: HNSW é mais rápido que IVFFlat para buscas ANN em NLP
CREATE INDEX IF NOT EXISTS idx_vsearch_vector
ON embeddings.fct_vector_geo_search
USING hnsw (embedding vector_cosine_ops)
WITH (m=24, ef_construction=256);

-- ------------------------------------------------
-- map_hotspots_h3
-- ------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_hotspots_geom ON embeddings.map_hotspots_h3 USING GIST (grid_geom);

-- ------------------------------------------------
-- products_embeddings
-- ------------------------------------------------
-- Índice para performance de filtros SQL clássicos (Hybrid Search)
-- O PostgreSQL usará estes índices antes de calcular a distância vetorial se o filtro for muito seletivo
CREATE INDEX IF NOT EXISTS idx_emb_brand ON embeddings.products_embeddings(brand);
CREATE INDEX IF NOT EXISTS idx_emb_category ON embeddings.products_embeddings(category);

-- Índice HNSW para busca rápida (Approximate Nearest Neighbor)
-- Utiliza vector_cosine_ops, pois se trata de NLP
CREATE INDEX IF NOT EXISTS idx_product_embedding ON embeddings.products_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m=24, ef_construction=256);
