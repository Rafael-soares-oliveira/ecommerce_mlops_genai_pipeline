CREATE TABLE IF NOT EXISTS raw_data.orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Processing', 'Shipped', 'Complete', 'Returned', 'Cancelled')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    returned_at TIMESTAMP WITH TIME ZONE,
    shipped_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    num_of_item SMALLINT NOT NULL CHECK (num_of_item > 0),

    CONSTRAINT check_shipped_after_created CHECK (shipped_at >= created_at),
    CONSTRAINT check_delivered_after_shipped CHECK (delivered_at >= shipped_at),
    CONSTRAINT check_returned_after_delivered CHECK (returned_at >= delivered_at),

    CONSTRAINT fk_orders_users FOREIGN KEY (user_id) REFERENCES raw_data.users (id)
);

COMMENT ON TABLE raw_data.orders IS 'Cabeçalho de pedidos dos usuários. Acompanha o status e as datas do ciclo de vida da entrega (funil logístico).';
COMMENT ON COLUMN raw_data.orders.status IS 'Status atual do pedido. Valores permitidos: Processing, Shipped, Complete, Returned, Cancelled.';
COMMENT ON COLUMN raw_data.orders.num_of_item IS 'Quantidade total de itens no pedido.';
