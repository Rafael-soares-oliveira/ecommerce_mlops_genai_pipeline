import pytest
from kedro.pipeline import Pipeline

from thelook_ecommerce_analysis.pipelines.data_embeddings.pipeline import (
    create_pipeline,
)


class TestDataEmbeddingsPipeline:
    """Suíte de testes para validar a estrutura do DAG do pipeline de embeddings."""

    @pytest.fixture
    def pipeline(self) -> Pipeline:
        """Fixture que cria o pipeline uma vez para ser usado em todos os testes."""
        return create_pipeline()

    def test_pipeline_creation_and_node_count(self, pipeline: Pipeline) -> None:
        """Garante que o pipeline seja instanciado e contenha todos os nós."""
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.nodes) == 8, "O pipeline deveria conter exatamente 8 nós."

    def test_pipeline_tags(self, pipeline: Pipeline) -> None:
        """Valida se o filtro por tags retorna a quantidade correta de nós.
        Isso garante que comandos como 'kedro run --tags=geo' funcionem no terminal.
        """
        # Nós com a tag "embedding" (Products + Geo Search = 6 nós)
        embedding_pipeline = pipeline.only_nodes_with_tags("embedding")
        assert len(embedding_pipeline.nodes) == 6

        # Nós com a tag "products" (3 nós)
        products_pipeline = pipeline.only_nodes_with_tags("products")
        assert len(products_pipeline.nodes) == 3

        # Nós com a tag "users" (3 nós)
        users_pipeline = pipeline.only_nodes_with_tags("users")
        assert len(users_pipeline.nodes) == 3

        # Nós com a tag "geo" (Map Hotspot + User Logistics = 2 nós)
        geo_pipeline = pipeline.only_nodes_with_tags("geo")
        assert len(geo_pipeline.nodes) == 2

    def test_pipeline_products_connections(self, pipeline: Pipeline) -> None:
        """Garante que o output de um nó seja o input do próximo para Products."""
        # Seleciona o nó de preparação de produtos pelo nome
        prepare_node = next(
            n for n in pipeline.nodes if n.name == "prepare_products_chunks_node"
        )
        # O nó precisa consumir o catálogo e a flag do nó anterior
        assert "primary_products" in prepare_node.inputs
        assert "products_embedding_complete_flag" in prepare_node.inputs
        assert "prepared_products" in prepare_node.outputs

        # Seleciona o nó de geração de embeddings
        generate_node = next(
            n for n in pipeline.nodes if n.name == "generate_products_embeddings_node"
        )
        # Garante que ele consome o "prepared_products" do nó anterior
        assert "prepared_products" in generate_node.inputs
        assert "embedding_model" in generate_node.inputs

    def test_pipeline_users_connections(self, pipeline: Pipeline) -> None:
        """Garante a amarração de inputs e outputs críticos do pipeline de Users (Geo Search)."""
        prepare_node = next(
            n for n in pipeline.nodes if n.name == "prepare_users_chunks_node"
        )

        assert "primary_users" in prepare_node.inputs
        assert "primary_order_items" in prepare_node.inputs
        assert "vector_geo_search_embedding_complete_flag" in prepare_node.inputs

        # Valida se o output final da vetorização está com o nome correto para o catálogo
        generate_node = next(
            n for n in pipeline.nodes if n.name == "generate_users_embeddings_node"
        )
        assert "fct_vector_geo_search_embeddings" in generate_node.outputs
