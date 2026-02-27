from thelook_ecommerce_analysis.pipelines.data_metrics.pipeline import create_pipeline


def test_create_pipeline():
    # Cria a instância do pipeline
    pipeline = create_pipeline()

    # 1. Valida a quantidade de nós (deve bater com a métrica de dicionários em metrics_config)
    assert len(pipeline.nodes) == 7

    # 2. Extrai propriedades para validação
    all_inputs = {inp for node in pipeline.nodes for inp in node.inputs}
    all_outputs = {out for node in pipeline.nodes for out in node.outputs}
    node_names = {node.name for node in pipeline.nodes}

    # 3. Valida se os inputs e parâmetros esperados estão presentes
    assert "primary_order_items" in all_inputs
    assert "params:metrics.returns_cost" in all_inputs
    assert "params:metrics.cohort_limit" in all_inputs

    # 4. Valida se as saídas (tabelas) foram mapeadas corretamente
    assert "metrics_sales_daily" in all_outputs
    assert "metrics_sales_funnel" in all_outputs

    # 5. Valida os nomes dinâmicos atribuídos aos nós
    assert "node_metrics_sales_daily" in node_names
    assert "node_metrics_cohort_retention" in node_names
