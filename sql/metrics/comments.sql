-- COHORT RETENTION
COMMENT ON TABLE metrics.cohort_retention IS 'Análise de retenção de clientes por safra (cohort) e país. Use para analisar o engajamento ao longo dos meses.';
COMMENT ON COLUMN metrics.cohort_retention.month_number IS 'Mês de vida da safra (0 é o mês da primeira compra, 1 é o mês seguinte, etc).';
COMMENT ON COLUMN metrics.cohort_retention.retention_rate IS 'Taxa percentual de retenção (0 a 100).';

-- CUSTOMER RFM
COMMENT ON TABLE metrics.customer_rfm_ltv IS 'Métricas de RFM (Recency, Frequency, Monetary) e segmentação de clientes. Use para análises de LTV, churn e valor do cliente.';
COMMENT ON COLUMN metrics.customer_rfm_ltv.customer_segment IS 'Segmentação de negócio (ex: Champions, At Risk, Hibernating).';
COMMENT ON COLUMN metrics.customer_rfm_ltv.ltv_value IS 'Lifetime Value (Receita total do cliente).';

-- DAILY SALES
COMMENT ON TABLE metrics.sales_daily IS 'Métricas financeiras e logísticas agregadas por dia e país. Use para analisar GMV, receita, lucro bruto e taxas de conversão/perda.';
COMMENT ON COLUMN metrics.sales_daily.gmv IS 'Volume Bruto de Mercadorias (vendas brutas). Exclui apenas pedidos cancelados.';
COMMENT ON COLUMN metrics.sales_daily.net_revenue IS 'Receita Líquida real. Exclui pedidos cancelados e devolvidos.';
COMMENT ON COLUMN metrics.sales_daily.gross_profit_realistic IS 'Lucro bruto considerando descontos de perdas logísticas (10% sobre o custo de devoluções).';

-- PRODUCT PERFORMANCE
COMMENT ON TABLE metrics.products_performance IS 'Visão consolidada de performance: une vendas (margem, devolução, ticket médio) e inventário (giro, tempo de venda e estoque atual).';

COMMENT ON COLUMN metrics.products_performance.inventory_turnover IS 'Giro de estoque: Razão entre itens vendidos e estoque atual. Valores altos indicam alta rotatividade.';
COMMENT ON COLUMN metrics.products_performance.avg_days_to_sell IS 'Média de dias que um item levou em estoque antes de ser vendido (histórico).';
COMMENT ON COLUMN metrics.products_performance.days_since_last_sale IS 'Dias decorridos desde a última venda realizada deste produto.';
COMMENT ON COLUMN metrics.products_performance.avg_margin_pct IS 'Margem de lucro média calculada como ((Preço de Venda - Custo) / Preço de Venda) * 100.';

-- SALES FUNNEL
COMMENT ON TABLE metrics.sales_funnel IS 'Métricas de funil de conversão agregadas por ano. Acompanha a jornada do usuário desde a visualização até a compra e taxas de abandono.';
COMMENT ON COLUMN metrics.sales_funnel.abandon_cart IS 'Taxa de abandono de carrinho (%). Usuários que adicionaram ao carrinho mas não compraram.';
COMMENT ON COLUMN metrics.sales_funnel.drop_off IS 'Taxa de desistência (%). Usuários que viram um produto mas não adicionaram ao carrinho.';

-- SESSION CONVERSION
COMMENT ON TABLE metrics.session_conversion IS 'Métricas de conversão de vendas agrupadas por tempo de duração da sessão do usuário.';
COMMENT ON COLUMN metrics.session_conversion.session_duration_bucket IS 'Faixa de tempo da sessão (0-1 min, 1-5 min, 5-10 min, 10+ min).';
COMMENT ON COLUMN metrics.session_conversion.conversion_rate IS 'Taxa de conversão em % de sessões que resultaram em compra.';

-- TRAFFIC SOURCE PERFORMANCE
COMMENT ON TABLE metrics.traffic_source_performance IS 'Métricas de aquisição e conversão de marketing agrupadas por origem de tráfego.';
COMMENT ON COLUMN metrics.traffic_source_performance.user_conversion_rate IS 'Percentual de usuários cadastrados no canal que realizaram pelo menos uma compra.';
COMMENT ON COLUMN metrics.traffic_source_performance.avg_ticket IS 'Ticket médio por item comprado pelos usuários deste canal.';
