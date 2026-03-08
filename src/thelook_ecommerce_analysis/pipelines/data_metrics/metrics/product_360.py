import ibis


def product_360(
    order_items: ibis.Table, products: ibis.Table, inventory_items: ibis.Table
) -> ibis.Table:
    # 0. Data de referência (Snapshot para simular CURRENT_DATE)
    ref_date = order_items.aggregate(snapshot_date=order_items.created_at.max())

    # 1. Filtro base
    oi_filtered = order_items.filter(
        [order_items.status != "Cancelled", order_items.created_at.notnull()]
    )

    # 2. Sales Metrics
    valid_status = ["Complete", "Returned", "Shipped"]

    sales_agg = oi_filtered.group_by(
        ["product_id", oi_filtered.created_at.year().name("sales_year")]
    ).aggregate(
        total_units_sold=oi_filtered["id"].count(),
        total_revenue=oi_filtered.sale_price.sum(),
        return_rate=(
            (oi_filtered.status == "Returned").ifelse(1, 0).sum().cast("float64")
            / (oi_filtered.status.isin(valid_status)).ifelse(1, 0).sum().nullif(0)
        ),
        avg_to_shipping_days=(
            (
                oi_filtered.shipped_at.epoch_seconds()
                - oi_filtered.created_at.epoch_seconds()
            ).mean()
            / 86400
        ),
        aov=oi_filtered.sale_price.mean(),
        last_sale_date=oi_filtered.created_at.max(),
    )

    # 3. Inventory Stats
    inventory_stats = inventory_items.group_by("product_id").aggregate(
        turnover_ratio=(
            inventory_items.sold_at.count().cast("float64")
            / (inventory_items.sold_at.isnull()).ifelse(1, 0).sum().nullif(0)
        ),
        avg_days_to_sell=(
            (
                inventory_items.sold_at.epoch_seconds()
                - inventory_items.created_at.epoch_seconds()
            ).mean()
            / 86400
        ),
        current_stock=(inventory_items.sold_at.isnull()).ifelse(1, 0).sum(),
    )

    # 4. Joins
    # Usamos o prefixo para evitar colisão de colunas 'id' e 'product_id'
    result = products.join(sales_agg, products["id"] == sales_agg.product_id).left_join(
        inventory_stats, products["id"] == inventory_stats.product_id
    )

    # Cross join com a data de referência
    result = result.cross_join(ref_date)

    # 5. Projeção Final
    final_df = result.select(
        product_id=result["id"],
        sales_year=result.sales_year,
        category=result.category,
        product_name=result.name,
        total_units_sold=result.total_units_sold,
        total_revenue=result.total_revenue.round(2),
        avg_shipping_days=result.avg_to_shipping_days.round(1),
        # Diferença de tempo convertida para dias
        days_since_last_sale=(
            (
                result.snapshot_date.epoch_seconds()
                - result.last_sale_date.epoch_seconds()
            )
            / 86400
        ).cast("int64"),
        stock_qt=result.current_stock.fillna(0),
        inventory_turnover=result.turnover_ratio.round(2),
        avg_days_to_sell=result.avg_days_to_sell.round(2),
        return_rate_pct=(result.return_rate * 100).round(2),
        avg_margin_pct=(
            ((result.aov - result.cost) / result.aov.nullif(0)) * 100
        ).round(2),
        aov=result.aov.round(2),
    ).order_by([ibis.desc("sales_year"), ibis.desc("total_revenue")])

    return final_df
