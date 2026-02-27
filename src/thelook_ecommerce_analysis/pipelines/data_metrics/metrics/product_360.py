import ibis


def product_360(
    order_items: ibis.Table, products: ibis.Table, inventory_items: ibis.Table
) -> ibis.Table:
    """
    Calculates products 360 view.

    SQL:
        >>>
        with sales_metrics as (
            select
                oi.product_id,

                -- Taxa de Devolução (Itens devolvidos / Total Itens Entregues ou Completos -> desconsiderado 'Processing' e 'Cancelled')
                (
                    count(case when oi.status = 'Returned' then 1 end)::numeric /
                    nullif(count(case when oi.status in ('Complete', 'Returned', 'Shipped') then 1 end), 0)
                ) as return_rate,

                -- Tempo de Envio: extrai os segundos e converte para dias (86400s = 24h)
                avg(extract(epoch from (oi.shipped_at - oi.created_at))/86400) as avg_to_shipping_days,

                -- Average Ticket (AOV)
                avg(oi.sale_price) as aov
            from raw_data.order_items oi
            join raw_data.products p on oi.product_id = p.id
            where oi.status not in ('Cancelled')
            group by 1
        ),
        stock_metrics as (
            select
                ii.product_id,

                -- Aging do Estoque (Média de dias dos itens parados(não vendidos))
                avg(current_date - ii.created_at::date) as avg_aging_days,
                count(*) as stock_qt
            from raw_data.inventory_items ii
            where ii.sold_at is null -- Não vendido
            group by 1
        )
        select
            p.category,
            p.name as product_name,
            round(sa.return_rate * 100, 2) as return_rate_pct,
            round(sa.avg_to_shipping_days::numeric, 2) as avg_to_shipping_days,
            round(
                ((sa.aov - p.cost) / nullif(sa.aov, 0)) * 100, 2
            ) as avg_margin_pct,
            round(sa.aov, 2) as aov,
            round(st.avg_aging_days, 2) as avg_aging_days,
            coalesce(stock_qt, 0) as stock_qt
        from raw_data.products p
        left join sales_metrics sa on p.id = sa.product_id
        left join stock_metrics st on p.id = st.product_id
        order by avg_aging_days desc;
    """
    # 1. Sales Metrics
    # Filtro inicial - Remover itens cancelados
    oi = order_items.filter(order_items.status != "Cancelled")
    valid_status = ["Complete", "Returned", "Shipped"]

    # Join com produtos para obter o custo
    sales_agg = oi.group_by("product_id").aggregate(
        return_rate=(
            (oi.status == "Returned").ifelse(1, 0).sum()
            / (oi.status.isin(valid_status)).ifelse(1, 0).sum().nullif(0)
        ),
        # Converte para segundos e depois para horas e dividi por 24horas (86400 == 24horas)
        avg_to_shipping_days=(
            (oi.shipped_at.epoch_seconds() - oi.created_at.epoch_seconds()).mean()
            / 86400
        ),
        aov=oi.sale_price.mean(),
    )

    # 2. Stock Metrics
    ii = inventory_items.filter(inventory_items.sold_at.isnull())

    stock_agg = ii.group_by("product_id").aggregate(
        avg_aging_days=(
            ibis.now().epoch_seconds() - ii.created_at.epoch_seconds()
        ).mean()
        / 86400,
        stock_qt=ii.count(),
    )

    # 3. Joins e Cálculos finais
    result = products.left_join(
        sales_agg, products.id == sales_agg.product_id
    ).left_join(stock_agg, products.id == stock_agg.product_id)

    final_df = result.select(
        category=products.category,
        product_name=products.name,
        return_rate_pct=(result.return_rate * 100).round(2),
        avg_to_shipping_days=result.avg_to_shipping_days.round(2),
        avg_margin_pct=(
            ((result.aov - products.cost) / result.aov.nullif(0)) * 100
        ).round(2),
        aov=result.aov.round(2),
        avg_aging_days=result.avg_aging_days.round(2),
        stock_qt=ibis.coalesce(result.stock_qt, 0),
    ).order_by(ibis.desc("avg_aging_days"))

    return final_df
