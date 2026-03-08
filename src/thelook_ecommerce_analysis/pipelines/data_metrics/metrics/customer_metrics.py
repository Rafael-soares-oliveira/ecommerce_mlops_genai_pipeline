# ruff: noqa: PLR2004
import ibis
from ibis import _


def customer_rfm_ltv(users: ibis.Table, order_items: ibis.Table) -> ibis.Table:
    """
    Calculates RFM Scores (1-5) e segments clients.

    SQL:
        >>>
            with ref_date as (
                select max(created_at)::date + 1 as snapshot_date
                from raw_data.order_items
                where status not in ('Cancelled', 'Returned')
            ),
            customer_stats as (
                select
                    u.id as user_id,
                    (select snapshot_date from ref_date) - max(oi.created_at)::date as recency_days,
                    count(distinct oi.order_id) as frequency_count,
                    sum(oi.sale_price) as ltv,
                    min(oi.created_at)::date as first_purchase_date
                from raw_data.users u
                join raw_data.order_items oi on u.id = oi.user_id
                where oi.status not in ('Cancelled', 'Returned')
                group by 1
                ),
            rfm_scores as (
                select
                    *,
                    ntile(5) over (order by recency_days desc) as r_score,
                    ntile(5) over (order by frequency_count asc) as f_score,
                    ntile(5) over (order by ltv asc) as m_score
                from customer_stats
            )
                select
                    user_id,
                    recency_days,
                    frequency_count,
                    round(ltv::numeric, 2) as ltv_value,
                    concat(r_score, f_score, m_score) as rfm_score,
                    r_score,
                    f_score,
                    m_score,
                    case
                        when r_score >= 5 and f_score >= 5 then 'Champions (VIP)'
                        when r_score >= 4 and f_score >= 4 then 'Loyal Customers'
                        when r_score >= 3 and f_score >= 3 then 'Potential Loyalist'
                        when r_score <= 2 and f_score >= 4 then 'At Risk (High Value)'
                        when r_score <= 2 and f_score <= 2 then 'Hibernating'
                        when r_score >= 4 and f_score <= 2 then 'New Users'
                        else 'General'
                    end as customer_segment
                from rfm_scores
                order by ltv desc;
    """
    # 1. Filtros globais e Data de referência
    valid_items = order_items.filter(
        order_items.status.notin(("Cancelled", "Returned"))
    )

    snapshot_date = valid_items.created_at.max().cast("date").add(ibis.interval(days=1))

    # 2. Base de Clientes
    customer_stats = (
        users.join(valid_items, users.id == valid_items.user_id)
        .group_by(users.id)
        .aggregate(
            recency_days=(snapshot_date - valid_items.created_at.max().cast("date")),
            frequency_count=valid_items.order_id.nunique(),
            ltv_value=valid_items.sale_price.sum(),
            first_purchase_date=valid_items.created_at.min().cast("date"),
        )
    )

    # 3. RFM Scores (Window Function - NTILE)
    rfm_scores = customer_stats.mutate(
        r_score=ibis.ntile(5).over(order_by=ibis.desc("recency_days")),
        f_score=ibis.ntile(5).over(order_by="frequency_count"),
        m_score=ibis.ntile(5).over(order_by="ltv_value"),
    )

    # 4. Segmentação e Projeção Final
    final_df = rfm_scores.mutate(
        customer_segment=(
            ibis.cases(
                ((_.r_score >= 5) & (_.f_score >= 5), "Champions (VIP)"),
                ((_.r_score >= 4) & (_.f_score >= 4), "Loyal Customers"),
                ((_.r_score >= 3) & (_.f_score >= 3), "Potential Loyalist"),
                ((_.r_score <= 2) & (_.f_score >= 4), "At Risk (High Value)"),
                ((_.r_score <= 2) & (_.f_score <= 2), "Hibernating"),
                ((_.r_score >= 4) & (_.f_score <= 2), "New Users"),
                else_="General",
            )
        ),
        ltv_value=_.ltv_value.round(2),
        rfm_score=_.r_score.cast("string")
        + _.f_score.cast("string")
        + _.m_score.cast("string"),
    ).order_by(_.ltv_value.desc())

    return final_df.select(
        user_id="id",
        recency_days="recency_days",
        frequency_count="frequency_count",
        ltv_value="ltv_value",
        rfm_score="rfm_score",
        r_score="r_score",
        f_score="f_score",
        m_score="m_score",
        customer_segment="customer_segment",
    )


def cohort_retention(
    users: ibis.Table, order_items: ibis.Table, month_limit: int
) -> ibis.Table:
    """
    Cohort Analysis Calculation with a 12-month limitation.

    SQL:
        >>>
        with user_cohorts as (
            select
                oi.user_id,
                u.country,
                date_trunc('month', min(oi.created_at))::date as cohort_month
            from raw_data.order_items oi
            join raw_data.users u on oi.user_id = u.id
            where oi.status not in ('Cancelled', 'Returned')
            group by 1, 2
        ),
        user_activities as (
            select
                oi.user_id,
                date_trunc('month', oi.created_at)::date as activity_month
            from raw_data.order_items oi
            where oi.status not in ('Cancelled', 'Returned')
            group by 1, 2
        ),
        cohort_base as (
            select
                uc.country,
                uc.cohort_month,
                ua.activity_month,
                count(distinct uc.user_id) as active_users,
                (
                    extract(year from age(ua.activity_month, uc.cohort_month)) * 12 + extract(month from age(ua.activity_month, uc.cohort_month))
                ) as month_number
            from user_cohorts uc
            join user_activities ua on uc.user_id = ua.user_id
            group by 1, 2, 3
        ),
        cohort_size as (
            select
                country,
                cohort_month,
                count(distinct user_id) as original_users
            from user_cohorts
            group by 1, 2
        )
        select
            b.country,
            b.cohort_month,
            s.original_users,
            b.month_number,
            b.active_users,
            round((b.active_users::numeric / s.original_users) * 100, 2) as retention_rate
        from cohort_base b
        join cohort_size s on b.cohort_month = s.cohort_month and b.country = s.country
        where b.month_number <= 12
        order by 1, 2, 4;
    """
    # Filtro de status
    valid_items = order_items.filter(
        order_items.status.notin(("Cancelled", "Returned"))
    )

    # 1. User Cohorts (Primeira compra)
    user_cohorts = (
        valid_items.join(users, valid_items.user_id == users.id)
        .group_by([valid_items.user_id, users.country])
        .aggregate(cohort_month=valid_items.created_at.min().truncate("M").cast("date"))
    )

    # 2. User Activities (Meses ativos)
    user_activities = valid_items.select(
        user_id="user_id", activity_month=_.created_at.truncate("M").cast("date")
    ).distinct()

    # 3. Base de Retenção e Cálculo de Mês
    cohort_base = (
        user_cohorts.join(user_activities, "user_id")
        .group_by(["country", "cohort_month", "activity_month"])
        .aggregate(active_users=_.user_id.nunique())
        .mutate(
            # Lógica de diferença de data em meses
            month_number=(
                (_.activity_month.year() - _.cohort_month.year()) * 12
                + (_.activity_month.month() - _.cohort_month.month())
            )
        )
    )

    # 4. Tamanho do Cohort Original
    cohort_size = user_cohorts.group_by(["country", "cohort_month"]).aggregate(
        original_users=_.user_id.nunique()
    )

    # 5. Join Final e Taxa
    final_df = (
        cohort_base.join(cohort_size, ["country", "cohort_month"])
        .filter(_.month_number <= month_limit)
        .mutate(
            retention_rate=(
                (_.active_users.cast("float64") / _.original_users) * 100
            ).round(2)
        )
        .order_by(["country", "cohort_month", "month_number"])
        .select(
            "country",
            "cohort_month",
            "original_users",
            "month_number",
            "active_users",
            "retention_rate",
        )
    )

    return final_df
