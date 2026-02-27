import ibis


def session_conversion(events: ibis.Table) -> ibis.Table:
    """
    Calculates time to purchase.

    SQL:
        >>>
        with metrics as (
            select
                session_id,
                extract(epoch from (max(created_at) - min(created_at))) / 60 as duration_min,
                max(case when event_type = 'purchase' then 1 else 0 end) as has_purchase
            from raw_data.events
            group by 1
        )
        select
            case
                when duration_min < 1 then '0-1 min'
                when duration_min < 5 then '1-5 min'
                when duration_min < 10 then '5-10 min'
                else '10+ min'
            end as session_duration_bucket,
            count(*) as total_sessions,
            sum(has_purchase) as total_sales,
            ROUND(avg(has_purchase) * 100, 2) as conversion_rate
        from metrics
        group by 1
        order by min(duration_min);
    """
    metrics = (
        events.group_by("session_id")
        .aggregate(
            duration_min=(
                events.created_at.max().epoch_seconds()
                - events.created_at.min().epoch_seconds()
            )
            / 60,
            has_purchase=ibis.ifelse(events.event_type == "purchase", 1, 0).max(),  # type: ignore erro no type hint
        )
        .order_by("duration_min")
    )

    bucket = ibis.cases(
        (metrics.duration_min < 1, "0-1 min"),  # noqa: PLR2004
        (metrics.duration_min < 5, "1-5 min"),  # noqa: PLR2004
        (metrics.duration_min < 10, "5-10min"),  # noqa: PLR2004
        else_="10+ min",
    ).name("session_duration_bucket")

    final_df = metrics.group_by(bucket).aggregate(
        total_sessions=metrics.count(),
        total_sales=metrics.has_purchase.sum(),
        conversion_rate=(metrics.has_purchase.mean() * 100).round(2),
    )

    return final_df


def traffic_source_performance(
    users: ibis.Table, orders: ibis.Table, order_items: ibis.Table
) -> ibis.Table:
    """
    Calculates traffic source metrics.

    SQL:
        >>>
        SELECT
            u.traffic_source,
            COUNT(DISTINCT u.id) AS acquired_users,
            COUNT(DISTINCT o.order_id) AS total_orders,
            ROUND(COUNT(DISTINCT o.user_id)::numeric / COUNT(DISTINCT u.id) * 100, 2) AS user_conversion_rate,
            ROUND(AVG(oi.sale_price)::numeric, 2) AS avg_ticket
        FROM raw_data.users u
        LEFT JOIN raw_data.orders o ON u.id = o.user_id
        LEFT JOIN raw_data.order_items oi ON o.order_id = oi.order_id
        GROUP BY 1
        ORDER BY 5 DESC;
    """
    u = users.select("id", "traffic_source")
    o = orders.select("user_id", "order_id")
    oi = order_items.select("order_id", "sale_price")

    final_df = (
        u.left_join(o, u.id == o.user_id, rname="{name}_orders")
        .left_join(oi, o.order_id == oi.order_id, rname="{name}_items")
        .group_by(u.traffic_source)
        .aggregate(
            acquired_users=u.id.nunique(),
            total_orders=o.order_id.nunique(),
            user_conversion_rate=(o.user_id.nunique() / u.id.nunique() * 100).round(2),
            avg_ticket=oi.sale_price.mean().round(2),
        )
        .order_by(ibis.desc("avg_ticket"))
    )

    return final_df


def sales_funnel(events: ibis.Table) -> ibis.Table:
    """
    Calculates web_analytics metrics per year.

    SQL:
        >>>
        WITH funil AS (
            SELECT
                EXTRACT(YEAR FROM created_at) AS year,
                session_id,
                MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
                MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase,
                MAX(CASE WHEN extracted_product_id IS NOT NULL THEN 1 ELSE 0 END) AS has_product_view
            FROM raw_data.events
            GROUP BY 1, 2
        )
        SELECT
            YEAR,
            COUNT(*) AS total_sessions,
            ROUND(AVG(has_cart) * 100, 2) AS added_cart,
            ROUND(AVG(has_purchase) * 100, 2) AS purchased,
            ROUND(
                COUNT(*) FILTER (WHERE has_cart = 1 AND has_purchase = 0)::numeric /
                NULLIF(COUNT(*) FILTER (WHERE has_cart = 1), 0) * 100,
                2
            ) AS abandon_cart,
            ROUND(
                COUNT(*) FILTER (WHERE has_product_view = 1 AND has_cart = 0)::numeric /
                NULLIF(COUNT(*) FILTER (WHERE has_product_view = 1), 0) * 100,
                2
            ) AS drop_off
        FROM funil
        GROUP BY 1
        ORDER BY 1;
    """
    metrics = events.group_by("session_id", year=events.created_at.year()).aggregate(
        has_cart=(events.event_type == "cart").ifelse(1.0, 0.0).max(),
        has_purchase=(events.event_type == "purchase").ifelse(1.0, 0.0).max(),
        has_product_view=events.extracted_product_id.notnull().ifelse(1.0, 0.0).max(),
    )

    final_df = (
        metrics.group_by("year")
        .aggregate(
            total_sessions=metrics.count(),
            added_cart=(metrics.has_cart.mean() * 100).round(2),
            purchased=(metrics.has_purchase.mean() * 100).round(2),
            abandon_cart=(
                metrics.count(
                    where=(metrics.has_cart == 1) & (metrics.has_purchase == 0)
                )
                / metrics.count(where=metrics.has_cart == 1).nullif(ibis.literal(0))
                * 100
            ).round(2),
            drop_off=(
                metrics.count(
                    where=(metrics.has_product_view == 1) & (metrics.has_cart == 0)
                )
                / metrics.count(where=metrics.has_product_view == 1).nullif(
                    ibis.literal(0)
                )
                * 100
            ).round(2),
        )
        .order_by("year")
    )

    return final_df
