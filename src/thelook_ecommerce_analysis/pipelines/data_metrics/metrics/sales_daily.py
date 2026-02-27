import ibis

# Deferred Expressions: O _ representa o "resultado da operação anterior". Usar para quando é necessário representar uma tabela criada dentro da função ao invés de quebrar o código em duas etapas.
from ibis import _


def daily_sales_and_revenue(
    order_items: ibis.Table,
    products: ibis.Table,
    users: ibis.Table,
    returns_cost: float,
) -> ibis.Table:
    """
    Calculates financial metrics:
        - Day
        - GMV
        - Net Revenue
        - Gross Profit Optimistic
        - Gross Profit Realistic
        - Logistic Loss
        - Cancellation Rate
        - Returns Rate

    SQL:
        >>>
        with metrics as (
            select
                cast(date_trunc('day', oi.created_at) as date) as day,
                u.country,
                coalesce(sum(oi.sale_price) filter (where oi.status != 'Cancelled'), 0) as gmv,
                coalesce(sum(oi.sale_price) filter (where oi.status not in ('Cancelled', 'Returned')), 0) as net_revenue,
                coalesce(sum(p.cost) filter (where oi.status not in ('Cancelled', 'Returned')), 0) as cogs_net,
                coalesce(sum(p.cost) filter (where oi.status = 'Returned'), 0) as cost_of_returns,
                cast(count(distinct oi.order_id) filter (where oi.status not in ('Cancelled', 'Returned')) as float) as count_orders_valid,
                cast(count(distinct oi.order_id) filter (where oi.status = 'Cancelled') as float) as count_orders_cancelled,
                cast(count(distinct oi.order_id) filter (where oi.status = 'Returned') as float) as count_orders_returned,
                cast(count(distinct oi.order_id) as float) as count_orders_total
            from raw_data.order_items oi
            join raw_data.products p on oi.product_id = p.id
            join raw_data.users u on oi.user_id = u.id
            group by 1, 2
            order by 1 desc, 2
        ),
        final_metrics as (
            select
                day,
                country,
                gmv,
                net_revenue,
                net_revenue - cogs_net as gross_profit_optimistic,
                net_revenue - cogs_net - (cost_of_returns * 0.10) as gross_profit_realistic,
                cost_of_returns * 0.10 as logistic_loss,
                case
                    when count_orders_valid = 0
                    then 0
                    else count_orders_cancelled / count_orders_total * 100
                end as cancellation_rate,
                case
                    when count_orders_valid = 0
                    then 0
                    else count_orders_returned/ count_orders_total * 100
                end  as returns_rate
            from metrics
        )
        select
            day,
            country
            gmv,
            net_revenue,
            gross_profit_optimistic,
            gross_profit_realistic,
            logistic_loss,
            cancellation_rate::numeric(5, 2),
            returns_rate::numeric(5, 2)
        from final_metrics;
    """
    # 1. Preparação (Renomeando ID para evitar colisão)
    products_cost = products.select(product_cost=_.cost, product_ref_id=_.id)
    users_clean = users.select(u_country=_.country, u_id=_.id)

    # 2. Join raw_data.order_items -> raw_data.products -> raw_data.users
    joined = order_items.left_join(
        products_cost, order_items.product_id == products_cost.product_ref_id
    ).left_join(users_clean, order_items.user_id == users_clean.u_id)

    # 3. Definição das regras de negócio
    is_cancelled = joined["status"] == "Cancelled"  # Pedidos cancelados
    is_returned = joined["status"] == "Returned"  # Todos pedidos exceto cancelados

    # Net Eligible: vendas que de fato geraram receita final
    is_net_eligible = joined["status"].notin(("Cancelled", "Returned"))

    # 4. Agregações
    daily_aggregated = joined.group_by(
        day=joined["created_at"].truncate("D").cast("date"), country=joined["u_country"]
    ).aggregate(
        # GMV
        gmv=joined["sale_price"].sum(where=~is_cancelled).fill_null(0),
        # Net Revenue
        net_revenue=joined["sale_price"].sum(where=is_net_eligible).fill_null(0),
        # Cogs: custo dos produtos efetivamente vendidos
        cogs_net=joined["product_cost"].sum(where=is_net_eligible).fill_null(0),
        # Custo total dos itens devolvidos
        cost_of_returns=joined["product_cost"].sum(where=is_returned).fill_null(0),
        # Contagem de Pedidos
        count_orders_valid=joined["order_id"].nunique(where=is_net_eligible),
        count_orders_cancelled=joined["order_id"].nunique(where=is_cancelled),
        count_orders_returned=joined["order_id"].nunique(where=is_returned),
        count_orders_total=joined["order_id"].nunique(),
    )

    # 5. Cálculos Finais e Projeção
    final_view = (
        daily_aggregated
        # Cálculos finais
        .mutate(
            # Lucro Otimista: Receita Líquida - Custo do Produto (Sem custo logística)
            gross_profit_optimistic=_.net_revenue - _.cogs_net,
            # Lucro Realista: Receita Líquida - Custo do Vendido - 10% do Custo (Logística Reversa)
            gross_profit_realistic=(
                _.net_revenue - _.cogs_net - (_.cost_of_returns * returns_cost)
            ),
            # Perda Logística
            logistic_loss=(_.cost_of_returns * returns_cost),
            # AOV (Ticket Médio)
            aov=(
                (_.count_orders_valid == 0)
                .ifelse(0.0, (_.net_revenue / _.count_orders_valid))
                .cast("decimal(10,2)")
            ),
            # Cancellation Rate
            cancellation_rate=(
                (_.count_orders_total == 0)
                .ifelse(0.0, (_.count_orders_cancelled / _.count_orders_total) * 100)
                .cast("decimal(10,2)")
            ),
            # Returned Rate
            returns_rate=(
                (_.count_orders_total == 0)
                .ifelse(0.0, (_.count_orders_returned / _.count_orders_total) * 100)
                .cast("decimal(10, 2)")
            ),
        )
        # Projeção Final
        .select(
            "day",
            "country",
            "gmv",
            "net_revenue",
            "gross_profit_optimistic",
            "gross_profit_realistic",
            "logistic_loss",
            "aov",
            "cancellation_rate",
            "returns_rate",
        )
        .order_by(_.day.desc())
    )

    return final_view
