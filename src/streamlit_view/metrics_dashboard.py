from collections.abc import Callable
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st
from plotly.subplots import make_subplots

METRICS = st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_brl(val: Any) -> str:
    if val is None:
        return "R$ 0,00"

    abs_val = abs(val)
    if abs_val >= 1_000_000:  # noqa: PLR2004
        return f"R$ {val / 1_000_000:.1f}M".replace(".", ",")
    elif abs_val >= 1_000:  # noqa: PLR2004
        return f"R$ {val / 1_000:.1f}k".replace(".", ",")

    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def render_kpis(df: pl.DataFrame, mapping: dict) -> None:
    cols = st.columns(len(mapping))
    row = df.row(0, named=True)

    for col, (label, col_name) in zip(cols, mapping.items(), strict=False):
        val = row.get(col_name, 0)
        formatted = (
            fmt_brl(val)
            if "total" in col_name or "avg" in col_name
            else f"{val:,.0f}".replace(",", ".")
        )
        col.metric(label, formatted)


def apply_layout(
    fig: go.Figure, title_x: float = 0.1, showlegend: bool = False, **kwargs: Any
) -> go.Figure:
    layout_args = {
        "title_font_size": 18,
        "title_x": title_x,
        "margin": dict(l=20, r=50, t=50, b=20),
        "font": dict(size=14),
        "showlegend": showlegend,
    }
    if not (any(isinstance(t, (go.Pie, go.Heatmap)) for t in fig.data)):
        layout_args["coloraxis_showscale"] = False
        fig.update_traces(cliponaxis=False)

    if kwargs:
        layout_args.update(**kwargs)

    fig.update_layout(**layout_args)
    return fig


def render_metrics_page(fetch_data_func: Callable[[str], pl.DataFrame]) -> None:
    st.title("📈 Painel de Métricas de Negócio")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Vendas & Financeiro",
            "Clientes & Marketing",
            "Produto & Engajamento",
            "Logística",
            "Geolocalização",
        ],
        key="main_tabs",
    )

    with tab1:
        _render_sales_tab(fetch_data_func)
    with tab2:
        _render_marketing_tab(fetch_data_func)
    with tab3:
        _render_product_tab(fetch_data_func)
    with tab4:
        _render_logistics_tab(fetch_data_func)
    with tab5:
        _render_geo_tab(fetch_data_func)


def _render_sales_tab(fetch_data: Callable) -> None:
    st.subheader("Performance Financeira")

    df_totals = fetch_data("""
        SELECT
            SUM(gmv) as total_gmv,
            SUM(net_revenue) as total_net,
            SUM(gross_profit_realistic) as total_profit,
            AVG(aov)::FLOAT as avg_aov
        FROM metrics.sales_daily
    """)

    if not df_totals.is_empty():
        render_kpis(
            df_totals,
            {
                "GMV Total": "total_gmv",
                "Receita Líquida": "total_net",
                "Lucro": "total_profit",
                "AOV": "avg_aov",
            },
        )

    st.divider()

    df_evolution = fetch_data("""
        SELECT
        date as "Date",
        SUM(net_revenue) as "Net Revenue",
        SUM(gross_profit_realistic) as "Gross Profit Realistic"
        FROM metrics.sales_daily
        GROUP BY 1
        ORDER BY 1
    """)

    fig_evol = px.line(
        df_evolution,
        x="Date",
        y=["Net Revenue", "Gross Profit Realistic"],
        labels={"value": "Valor (R$)", "Date": "Data", "variable": "Métrica"},
        title="Evolução: Receita Líquida vs Lucro Bruto",
        color_discrete_sequence=["#636EFA", "#00CC96"],
    )
    st.plotly_chart(
        apply_layout(fig_evol, title_x=0, showlegend=True), use_container_width=True
    )
    st.divider()

    col_geo, col_fun = st.columns([0.6, 0.4])

    with col_geo:
        df_country = fetch_data("""
            SELECT country as 'Country', SUM(net_revenue) as 'Revenue'
            FROM metrics.sales_daily GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """)
        fig_country = px.bar(
            df_country,
            x="Revenue",
            y="Country",
            orientation="h",
            title="Receita por País (Top 10)",
            color="Revenue",
            text_auto=".2s",
            color_continuous_scale="Greens",
        )
        fig_country.update_traces(textposition="outside")
        fig_country.update_xaxes(visible=False)
        st.plotly_chart(
            apply_layout(fig_country, title_x=0.3), use_container_width=True
        )

    with col_fun:
        df_f = fetch_data("""
            SELECT year, added_cart, purchased
            FROM metrics.sales_funnel ORDER BY year DESC LIMIT 1
        """)
        if not df_f.is_empty():
            row = df_f.row(0, named=True)
            fun_data = {
                "Etapa": ["Visualização", "Carrinho", "Compra"],
                "Valor": [100, row["added_cart"], row["purchased"]],
            }
            fig_funnel = px.funnel(
                fun_data,
                x="Valor",
                y="Etapa",
                title=f"Funil ({int(row['year'])})",
                color_discrete_sequence=["#AB63FA"],
            )
            st.plotly_chart(
                apply_layout(fig_funnel, title_x=0.4), use_container_width=True
            )


def _render_marketing_tab(fetch_data: Callable) -> None:
    st.subheader("Análise de Engajamento, Marketing e Retenção")

    df_mkt_kpis = fetch_data("""
        SELECT
            SUM(acquired_users) as total_users,
            AVG(user_conversion_rate) as avg_conv_rate,
            AVG(avg_ticket) as avg_ticket
        FROM metrics.traffic_source_performance
    """)

    if not df_mkt_kpis.is_empty():
        render_kpis(
            df_mkt_kpis,
            {
                "Usuários": "total_users",
                "Conversão Média": "avg_conv_rate",
                "Ticket Médio": "avg_ticket",
            },
        )

    st.divider()

    df_traffic = fetch_data("""
        SELECT
        traffic_source,
        acquired_users,
        user_conversion_rate,
        avg_ticket::float
        FROM metrics.traffic_source_performance
        ORDER BY acquired_users DESC
    """)

    fig_traffic = make_subplots(specs=[[{"secondary_y": True}]])
    fig_traffic.add_trace(
        go.Bar(
            x=df_traffic["traffic_source"],
            y=df_traffic["acquired_users"],
            name="Usuários",
            marker_color="royalblue",
        ),
        secondary_y=False,
    )
    fig_traffic.add_trace(
        go.Scatter(
            x=df_traffic["traffic_source"],
            y=df_traffic["user_conversion_rate"],
            name="Conv %",
            mode="lines+markers+text",
            text=[f"{x:.1f}%" for x in df_traffic["user_conversion_rate"]],
            line=dict(color="firebrick", width=3),
        ),
        secondary_y=True,
    )
    fig_traffic.update_yaxes(title_text="Usuários", secondary_y=False, showgrid=False)
    fig_traffic.update_yaxes(title_text="Conversão %", secondary_y=True)
    fig_traffic.update_layout(
        title="Volume de Usuários vs. Taxa de Conversão por Canal"
    )
    st.plotly_chart(
        apply_layout(fig_traffic, showlegend=True), use_container_width=True, height=300
    )

    st.divider()
    col_a, col_b = st.columns([1.2, 0.8])

    with col_a:
        df_cohort = fetch_data("""
            SELECT
                cohort_month,
                month_number,
                ROUND(AVG(retention_rate), 2) as retention_rate
            FROM metrics.cohort_retention
            GROUP BY 1, 2
        """)
        if not df_cohort.is_empty():
            fig_cohort = go.Figure(
                data=go.Heatmap(
                    z=df_cohort["retention_rate"],
                    x=df_cohort["month_number"],
                    y=df_cohort["cohort_month"],
                    colorscale="RdYlGn",
                    text=df_cohort["retention_rate"],
                    texttemplate="%{text}",
                    showscale=False,
                )
            )

            st.plotly_chart(
                apply_layout(
                    fig_cohort,
                    title="Retenção por Cohort (%)",
                    title_x=0.3,
                    yaxis=dict(title_text="Cohort Mês", autorange="reversed"),
                    xaxis=dict(title_text="Número Mês", dtick=1),
                ),
                use_container_width=True,
            )

    with col_b:
        df_rfm = fetch_data(
            "SELECT customer_segment, COUNT(*) as qty FROM metrics.customer_rfm_ltv GROUP BY 1"
        )
        fig_rfm = px.pie(
            df_rfm,
            names="customer_segment",
            values="qty",
            title="Segmentação RFM",
            hole=0.4,
        )
        fig_rfm.update_traces(
            textinfo="label+percent",
            textposition="inside",
            textfont=dict(size=14, family="Arial Black"),
        )
        st.plotly_chart(
            apply_layout(fig_rfm, title_x=0.3, showlegend=False),
            use_container_width=True,
        )

    st.divider()
    c1, c2 = st.columns(2)

    with c1:
        df_ltv = fetch_data("""
            SELECT customer_segment, ROUND(AVG(ltv_value)::FLOAT, 2) as avg_ltv
            FROM metrics.customer_rfm_ltv GROUP BY 1 ORDER BY avg_ltv DESC
        """)
        fig_ltv = px.bar(
            df_ltv,
            x="avg_ltv",
            y="customer_segment",
            orientation="h",
            color="avg_ltv",
            title="LTV Médio por Segmento de Cliente",
            text="avg_ltv",
        )
        fig_ltv.update_traces(
            textposition="inside",
            texttemplate="R$%{value:.2f}",
            textfont=dict(size=14, family="Arial Black", weight="bold"),
        )
        st.plotly_chart(
            apply_layout(
                fig_ltv,
                title_x=0.15,
                showlegend=False,
                coloraxis_showscale=False,
                yaxis=dict(title_text=None, showgrid=False),
                xaxis=dict(visible=False),
            ),
            use_container_width=True,
        )

    with c2:
        df_conv = fetch_data(
            "SELECT session_duration_bucket, conversion_rate FROM metrics.session_conversion"
        ).to_pandas()
        fig_conv = px.line(
            df_conv,
            x="session_duration_bucket",
            y="conversion_rate",
            title="Taxa de Conversão por Duração da Sessão",
            markers=True,
            text=[f"{x:.1f}%" for x in df_conv["conversion_rate"]],
        )
        fig_conv.update_traces(
            selector=dict(type="scatter"),
            textfont=dict(size=14, family="Arial Black"),
            textposition="top center",
            cliponaxis=False,
            line_color="firebrick",
        )
        st.plotly_chart(
            apply_layout(
                fig_conv,
                title_x=0.15,
                showlegend=False,
                xaxis=dict(title_text="Duração Sessão", showgrid=False),
                yaxis=dict(title_text=None, showgrid=False, showticklabels=False),
                coloraxis_showscale=False,
            ),
            use_container_width=True,
        )


def _render_product_tab(fetch_data: Callable) -> None:
    st.subheader("Performance de Produto e Saúde de Estoque")
    # 1. Fetch de Dados Consolidados
    df_products = fetch_data("""
        SELECT
            category,
            product_name,
            stock_qt,
            inventory_turnover::FLOAT as turnover,
            avg_days_to_sell::FLOAT as days_to_sell,
            avg_margin_pct::FLOAT as margin,
            aov::FLOAT as aov,
            return_rate_pct::FLOAT as return_rate
        FROM metrics.products_performance
    """)

    if df_products.is_empty():
        st.warning("Nenhum dado de produto encontrado para o período.")
        return

    # 2. KPIs
    kpi_data = df_products.select(
        [
            pl.col("turnover").mean().alias("avg_turnover"),
            pl.col("days_to_sell").mean().alias("avg_shelf_life"),
            pl.col("margin").mean().alias("avg_margin"),
            pl.col("stock_qt").sum().alias("total_stock"),
        ]
    )

    cols = st.columns(4)
    row = kpi_data.row(0, named=True)
    cols[0].metric("Giro Médio (Turnover)", f"{row['avg_turnover']:.1f}x")
    cols[1].metric("Shelf Life Médio", f"{row['avg_shelf_life']:.0f} dias")
    cols[2].metric("Margem Média", f"{row['avg_margin']:.1f}%")
    cols[3].metric("Itens em Estoque", f"{row['total_stock']:,}".replace(",", "."))

    st.divider()

    # 3. Gráficos de Análise
    col_left, col_right = st.columns([0.6, 0.4])

    with col_left:
        # Gráfico 1: Giro de Estoque vs Margem por Categoria
        df_cat = df_products.group_by("category").agg(
            [
                pl.col("turnover").mean().round(3),
                pl.col("margin").mean().round(3),
                pl.col("stock_qt").sum().round(3),
            ]
        )

        fig_scatter = px.scatter(
            df_cat,
            x="turnover",
            y="margin",
            size="stock_qt",
            color="category",
            hover_name="category",
            title="Matriz: Giro vs. Margem (por Categoria)",
            labels={
                "turnover": "Giro de Estoque",
                "margin": "Margem (%)",
                "category": "Categoria",
                "stock_qt": "Qty Estoque",
            },
        )
        # Adiciona linhas de referência para quadrantes
        fig_scatter.add_hline(
            y=df_cat["margin"].mean(),
            line_dash="dot",
            annotation_text="Margem Média",
            line_color="red",
        )
        fig_scatter.add_vline(
            x=df_cat["turnover"].mean(),
            line_dash="dot",
            annotation_text="Giro Médio",
            line_color="blue",
        )

        st.plotly_chart(
            apply_layout(fig_scatter, title_x=0.05), use_container_width=True
        )

    with col_right:
        # Gráfico 2: Top 10 Categorias com maior tempo de venda (Shelf Life)
        df_aging = (
            df_products.group_by("category")
            .agg(pl.col("days_to_sell").mean().round(1))
            .sort("days_to_sell", descending=True)
            .head(10)
        )

        fig_aging = px.bar(
            df_aging,
            x="days_to_sell",
            y="category",
            orientation="h",
            title="Top 10: Dias em Estoque",
            color="days_to_sell",
            color_continuous_scale="Reds",
            labels={"days_to_sell": "Dias até Vender", "category": "Categoria"},
        )
        st.plotly_chart(
            apply_layout(
                fig_aging,
                title_x=0.05,
            ),
            use_container_width=True,
        )

    st.divider()

    # 4. Tabela de Detalhes (Stock Out Risk)
    st.write("**⚠️ Itens com Baixo Giro e Alta Margem (Oportunidade de Promoção)**")

    # Giro baixo (< média) e Margem alta (> média)
    avg_turnover = row["avg_turnover"]
    avg_margin = row["avg_margin"]

    df_deadstock = (
        df_products.filter(
            (pl.col("turnover") < avg_turnover)
            & (pl.col("margin") > avg_margin)
            & (pl.col("stock_qt") > 0)
        )
        .select(["product_name", "category", "stock_qt", "turnover", "margin"])
        .sort("turnover")
        .head(10)
        .to_pandas()
    )

    st.dataframe(
        df_deadstock.style.format({"turnover": "{:.2f}x", "margin": "{:.1f}%"}),
        use_container_width=True,
        hide_index=True,
        column_config={
            "product_name": "Produto",
            "category": "Categoria",
            "stock_qt": "Qty Estoque",
            "turnover": "Turnover",
            "margin": "Margem",
        },
    )


def _render_logistics_tab(fetch_data: Callable) -> None:
    st.subheader("Eficiência Logística e Perdas Operacionais")

    # 1. Fetch de Dados - Unindo Performance de Envio e Perdas Financeiras
    df_log = fetch_data("""
        WITH shipping_metrics AS (
            SELECT
                category,
                AVG(avg_shipping_days)::FLOAT as avg_shipping_days,
                AVG(return_rate_pct)::FLOAT as return_rate
            FROM metrics.products_performance
            GROUP BY 1
        ),
        daily_loss_metrics AS (
            SELECT
                AVG(cancellation_rate)::FLOAT as avg_cancel_rate,
                AVG(logistic_loss)::FLOAT as avg_logistic_loss
            FROM metrics.sales_daily
        )
        SELECT * FROM shipping_metrics CROSS JOIN daily_loss_metrics
    """)

    if df_log.is_empty():
        st.warning("Dados logísticos não encontrados.")
        return

    # 2. KPIs de Cabeçalho (Agregação via Polars)
    kpis = df_log.select(
        [
            pl.col("avg_shipping_days").mean().alias("avg_lead_time"),
            pl.col("return_rate").mean().alias("avg_return"),
            pl.col("avg_cancel_rate").mean().alias("avg_cancel"),
            pl.col("avg_logistic_loss")
            .first()
            .alias("avg_loss"),  # Cross join repete o valor
        ]
    ).row(0, named=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lead Time Médio (Envio)", f"{kpis['avg_lead_time']:.1f} Dias")
    c2.metric("Taxa de Devolução", f"{kpis['avg_return']:.1f}%")
    c3.metric("Taxa de Cancelamento", f"{kpis['avg_cancel']:.1f}%")
    c4.metric("Custo Devolução Médio", fmt_brl(kpis["avg_loss"]))

    st.divider()

    # 3. Análise de Eficiência por Categoria (Scatter Plot)
    # Relaciona tempo de despacho com taxa de devolução
    fig_dispatch = px.scatter(
        df_log,
        x="avg_shipping_days",
        y="return_rate",
        text="category",
        size="avg_shipping_days",
        color="return_rate",
        title="SLA: Tempo de Envio vs. Taxa de Devolução",
        labels={
            "avg_shipping_days": "Dias para Envio",
            "return_rate": "Devolução (%)",
        },
        color_continuous_scale="Reds",
    )
    st.plotly_chart(apply_layout(fig_dispatch), use_container_width=True)

    st.divider()

    col_left, col_mid, col_right = st.columns(3)

    with col_left:
        st.write("**📊 Status Operacional por Categoria**")

        # Classificação de risco
        df_risk = (
            df_log.with_columns(
                pl.when(pl.col("avg_shipping_days") > 3.5)  # noqa: PLR2004
                .then(pl.lit("🚨 Crítico"))
                .when(pl.col("avg_shipping_days") > 2.5)  # noqa: PLR2004
                .then(pl.lit("⚠️ Alerta"))
                .otherwise(pl.lit("✅ Estável"))
                .alias("Status SLA")
            )
            .select(["category", "avg_shipping_days", "return_rate", "Status SLA"])
            .sort("avg_shipping_days", descending=True)
        )

        st.dataframe(
            df_risk.to_pandas(),
            column_config={
                "avg_shipping_days": st.column_config.NumberColumn(
                    "Dias para Envio", format="%.2f d"
                ),
                "return_rate": st.column_config.NumberColumn(
                    "Taxa de Devolução", format="%.2f%%"
                ),
                "category": "Categoria",
            },
            use_container_width=True,
            hide_index=True,
        )

    with col_mid:
        df_geo_cancel = fetch_data("""
            SELECT
            country,
            ROUND(AVG(cancellation_rate), 2)::FLOAT as avg_cancel
            FROM metrics.sales_daily
            GROUP BY 1 ORDER BY 2 DESC
        """)

        fig_geo = px.bar(
            df_geo_cancel,
            x="avg_cancel",
            y="country",
            orientation="h",
            title="Taxa de Cancelamento por País",
            color="avg_cancel",
            color_continuous_scale="Reds",
        )
        st.plotly_chart(apply_layout(fig_geo), use_container_width=True)

    with col_right:
        # Ranking de Categorias por Lead Time (Top 10 mais lentas)
        df_slowest = df_log.sort("avg_shipping_days", descending=True).head(10)
        fig_slow = px.bar(
            df_slowest,
            x="avg_shipping_days",
            y="category",
            orientation="h",
            title="Top 10 Categorias: Maior Lead Time de Envio",
            labels={"avg_shipping_days": "Média de Dias"},
            color="avg_shipping_days",
            color_continuous_scale="YlOrRd",
        )
        st.plotly_chart(apply_layout(fig_slow), use_container_width=True)

    st.divider()

    df_loss_time = fetch_data("""
        SELECT
        date,
        SUM(logistic_loss) as return_cost
        FROM metrics.sales_daily
        GROUP BY 1
        ORDER BY 1
        """)

    fig_loss = px.line(
        df_loss_time,
        x="date",
        y="return_cost",
        title="Tendência de Custo com Devoluções (R$)",
        labels={"return_cost": "Custo Retorno", "date": "Data"},
    )
    st.plotly_chart(apply_layout(fig_loss), use_container_width=True)


def _render_geo_tab(fetch_data: Callable) -> None:
    st.subheader("Geolocalização com Pydeck")

    # 1. Busca de Dados (DCs e Pedidos)
    # TODO: Criar métricas de geolocalização
    df_geo = fetch_data("""
        SELECT
        u.id as user_id,
        dc.id as dc_id,
        dc.name as dc_name,
        dc.latitude as dc_lat,
        dc.longitude as dc_lon,
        u.latitude as user_lat,
        u.longitude as user_lon,
        SUM(oi.sale_price) as revenue
        FROM raw_data.order_items oi
        JOIN raw_data.products p ON oi.product_id = p.id
        JOIN raw_data.distribution_centers dc ON p.distribution_center_id = dc.id
        JOIN raw_data.users u ON oi.user_id = u.id
        WHERE u.latitude IS NOT NULL AND u.longitude IS NOT NULL
        GROUP BY 1, 2, 3;
    """)  # noqa: F841
