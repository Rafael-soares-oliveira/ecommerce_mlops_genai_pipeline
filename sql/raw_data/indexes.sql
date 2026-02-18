-- =====================================================================
--  1. OTIMIZAÇÃO DE FOREIGN KEYS (FAST JOINS)
-- =====================================================================

-- Tabela EVENTS
-- Join com Users e Ordenação Temporal
CREATE INDEX IF NOT EXISTS idx_events_user_id ON raw_data.events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON raw_data.events(created_at DESC);

-- Para funis de conversão
CREATE INDEX IF NOT EXISTS idx_events_type_session ON raw_data.events(event_type, session_id);

-- Para identificar Usuários registrados ('Registered') e convidados ('Guest')
CREATE INDEX IF NOT EXISTS idx_events_visitor_type ON raw_data.events(visitor_type);

-- Para tabelas criadas a partir de uri
CREATE INDEX IF NOT EXISTS idx_events_product_id ON raw_data.events(extracted_product_id);
CREATE INDEX IF NOT EXISTS idx_events_page_type ON raw_data.events(extracted_page_type);

-- Tabela ORDERS
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON raw_data.orders (created_at);

------------------------------------------------------------------------
-- Tabela ORDER_ITEMS
-- Join para saber quem comprou o que
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON raw_data.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON raw_data.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_user_id ON raw_data.order_items(user_id);

------------------------------------------------------------------------
-- Tabela INVENTORY_ITEMS
CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON raw_data.inventory_items(product_id);

-- =====================================================================
--  2. ÍNDICES PARA FILTROS E ANALYTICS (WHERE / GROUP BY)
-- =====================================================================

-- Acelera: Queries com ITEMS e STATUS
CREATE INDEX IF NOT EXISTS idx_order_items_status ON raw_data.order_items(status);

-- Acelera: "Vendas por período
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON raw_data.orders(created_at);

-- =====================================================================
--  3. ÍNDICES PARA BUSCA TEXTUAL / RAG (Hybrid Search)
-- =====================================================================
-- Permite query: WHERE name LIKE '%product%' de forma instantânea
-- A ativação do pg_trgm está no init.sql
CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON raw_data.products USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_brand_trgm ON raw_data.products USING GIN (brand gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_category_trgm ON raw_data.products USING GIN (category gin_trgm_ops);

-- Achar usuário por cidade rapidamente
CREATE INDEX IF NOT EXISTS idx_users_city ON raw_data.users(city);

-- =====================================================================
--  4. ÍNDICES DE GEOLOCALIZAÇÃO
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_users_geom ON raw_data.users USING GIST (user_geom);

CREATE INDEX IF NOT EXISTS idx_distribution_centers_geom ON raw_data.distribution_centers USING GIST (distribution_center_geom);

-- 2. Transformação em Hypertable
-- Particionando por 'created_at' usando intervalo de 1 mês por chunk.
SELECT create_hypertable(
    'raw_data.events',
    'created_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

-- 3. Configurar Compressão (Segmentada por session_id para o funil)
ALTER TABLE raw_data.events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'session_id, id',
    timescaledb.compress_orderby = 'created_at DESC'
);
