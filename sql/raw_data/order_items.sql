CREATE TABLE IF NOT EXISTS raw_data.order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    status TEXT CHECK (status IN ('Processing', 'Shipped', 'Complete', 'Returned', 'Cancelled')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    shipped_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    returned_at TIMESTAMP WITH TIME ZONE,
    sale_price NUMERIC(10, 2) CHECK (sale_price >= 0),

    CONSTRAINT check_shipped_after_created CHECK (shipped_at >= created_at),
    CONSTRAINT check_delivered_after_shipped CHECK (delivered_at >= shipped_at),
    CONSTRAINT check_returned_after_delivered CHECK (returned_at >= delivered_at),

    CONSTRAINT fk_order_items_orders FOREIGN KEY (order_id) REFERENCES raw_data.orders (order_id),
    CONSTRAINT fk_order_items_users FOREIGN KEY (user_id) REFERENCES raw_data.users (id),
    CONSTRAINT fk_order_items_products FOREIGN KEY (product_id) REFERENCES raw_data.products (id),
    CONSTRAINT fk_order_items_inventory_items FOREIGN KEY (inventory_item_id) REFERENCES raw_data.inventory_items (id)
);
