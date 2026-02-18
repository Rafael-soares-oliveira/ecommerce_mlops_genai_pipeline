-- 1. Criação da Tabela.
-- No TimescaleDB, a PK deve obrigatoriamente conter a coluna de tempo.
CREATE TABLE IF NOT EXISTS raw_data.events (
    id INTEGER NOT NULL,
    user_id INTEGER,
    sequence_number INTEGER,
    session_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address TEXT,
    city TEXT COLLATE case_insensitive, -- RAG ignora acento/case
    state TEXT COLLATE case_insensitive,
    postal_code TEXT,
    browser TEXT,
    traffic_source TEXT,
    uri TEXT,
    event_type TEXT CHECK (event_type IN ('product', 'department', 'cart', 'purchase', 'cancel', 'home')),
    visitor_type TEXT, -- Coluna criada via pipeline
    extracted_product_id INTEGER, -- Coluna criada via pipeline
    extracted_page_type TEXT, -- Coluna criada via pipeline
    PRIMARY KEY (id, created_at) -- PK Composta para Hypertables
);
