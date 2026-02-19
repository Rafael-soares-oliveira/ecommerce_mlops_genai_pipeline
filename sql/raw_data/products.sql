CREATE TABLE IF NOT EXISTS raw_data.products (
    id INTEGER PRIMARY KEY,
    cost NUMERIC(10, 2) NOT NULL CHECK (cost > 0),
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    retail_price NUMERIC(10, 2) NOT NULL CHECK (retail_price >= 0),
    department TEXT NOT NULL,
    sku TEXT NOT NULL,
    distribution_center_id SMALLINT NOT NULL,

    CONSTRAINT fk_products_distribution_centers FOREIGN KEY (distribution_center_id) REFERENCES raw_data.distribution_centers (id)
);

COMMENT ON TABLE raw_data.products IS 'Catálogo mestre de produtos. Representa modelos/tipos de produtos, não os itens físicos em estoque (veja inventory_items para estoque).';
COMMENT ON COLUMN raw_data.products.cost IS 'Custo padrão de aquisição do produto.';
COMMENT ON COLUMN raw_data.products.retail_price IS 'Preço de venda sugerido ao consumidor.';
COMMENT ON COLUMN raw_data.products.distribution_center_id IS 'Chave estrangeira para raw_data.distribution_centers indicando o CD padrão do produto.';
