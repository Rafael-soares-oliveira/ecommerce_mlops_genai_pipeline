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
    browser TEXT NOT NULL,
    traffic_source TEXT NOT NULL,
    uri TEXT,
    event_type TEXT CHECK (event_type IN ('product', 'department', 'cart', 'purchase', 'cancel', 'home')),
    visitor_type TEXT NOT NULL, -- Coluna criada via pipeline
    extracted_product_id INTEGER NOT NULL, -- Coluna criada via pipeline
    extracted_page_type TEXT NOT NULL, -- Coluna criada via pipeline
    PRIMARY KEY (id, created_at) -- PK Composta para Hypertables
);

COMMENT ON TABLE raw_data.events IS 'Dados de navegação web (clickstream) dos usuários. Use para análise de funil, tráfego, sessões e comportamento em tela.';
COMMENT ON COLUMN raw_data.events.session_id IS 'Identificador único da sessão. Agrupa uma sequência de eventos de um mesmo acesso.';
COMMENT ON COLUMN raw_data.events.event_type IS 'Ação mapeada do usuário. Valores estritos: product, department, cart, purchase, cancel, home.';
COMMENT ON COLUMN raw_data.events.extracted_product_id IS 'ID do produto acessado, derivado do evento. Útil para cruzar visualizações com a tabela products.';
