import pytest
from kedro.pipeline import Pipeline

from thelook_ecommerce_analysis.pipelines.data_processing import create_pipeline


class TestDataProcessingPipeline:
    """Suíte de testes para a topologia do pipeline do Kedro."""

    @pytest.fixture
    def pipeline(self) -> Pipeline:
        """Retorna a instância do pipeline instanciada."""
        return create_pipeline()

    def test_pipeline_instance(self, pipeline: Pipeline) -> None:
        """Garante que o pipeline de data processing instância todos os nós corretamente."""
        assert isinstance(pipeline, Pipeline), "Deveria ser um Pipeline"
        assert len(pipeline.nodes) == 6, (
            "O pipeline deveria ter exatamente 6 nós de processamento"
        )

    def test_pipeline_dependencies(self, pipeline: Pipeline) -> None:
        """Valida se as dependências do DAG estão corretamente interligadas. Crucial para garantir que nós filhos executem após os nós pais."""
        all_outputs = set(pipeline.all_outputs())
        all_inputs = set(pipeline.all_inputs())
        expected_outputs = {
            "primary_users",
            "primary_orders",
            "primary_order_items",
        }
        expected_inputs = {"primary_users", "primary_distribution_centers"}
        missing_outputs = expected_outputs - all_outputs
        missing_inputs = expected_inputs - all_inputs

        assert not missing_outputs, (
            f"Dataset primário não gerado. Faltando: {missing_outputs}"
        )

        assert not missing_inputs, (
            f"Datasets primários não importados. Faltando: {missing_inputs}"
        )

    def test_node_names_are_mapped_correctly(self, pipeline: Pipeline) -> None:
        """Garante que os metadados dos nós foram preservados."""
        node_names = [node.name for node in pipeline.nodes]

        assert "data_processing.process_users_table_node" in node_names, (
            "process_users_table_node deveria estar registrado como node"
        )
        assert "data_processing.process_inventory_items_table_node" in node_names, (
            "process_inventory_items_table_node deveria estar registrado como node"
        )
