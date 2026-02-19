CREATE TABLE IF NOT EXISTS raw_data.inventory_items (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    sold_at TIMESTAMP WITH TIME ZONE,
    cost NUMERIC(10, 2) NOT NULL CHECK (cost >= 0),
    product_category TEXT NOT NULL COLLATE case_insensitive,
    product_name TEXT NOT NULL COLLATE case_insensitive,
    product_brand TEXT NOT NULL COLLATE case_insensitive,
    product_retail_price NUMERIC(10, 2) NOT NULL CHECK (product_retail_price >= 0),
    product_department TEXT NOT NULL COLLATE case_insensitive,
    product_sku TEXT NOT NULL,
    product_distribution_center_id INTEGER NOT NULL,

    CONSTRAINT check_sold_after_created_inv CHECK (sold_at >= created_at),

    CONSTRAINT fk_inventory_distribution FOREIGN KEY (product_distribution_center_id) REFERENCES raw_data.distribution_centers (id)
);

COMMENT ON TABLE raw_data.inventory_items IS 'Itens individuais no inventário. Cada linha é um produto físico único. Use para controle de estoque, custos e margens.';
COMMENT ON COLUMN raw_data.inventory_items.sold_at IS 'Data em que o item foi vendido. Se for NULL, o item ainda está disponível em estoque.';
COMMENT ON COLUMN raw_data.inventory_items.cost IS 'Custo de aquisição. Use junto com product_retail_price para calcular margem de lucro.';
COMMENT ON COLUMN raw_data.inventory_items.product_distribution_center_id IS 'Chave estrangeira para raw_data.distribution_centers.';
