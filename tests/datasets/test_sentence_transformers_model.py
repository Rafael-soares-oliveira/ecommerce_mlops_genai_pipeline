from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis.datasets.sentence_transformers_model import (
    _MODEL_CACHE,
    SentenceTransformerDataset,
)


@pytest.fixture(autouse=True)
def clear_model_cache() -> Generator[None]:
    """
    Fixture com autouse=True executa automaticamente em todos os testes desta classe.
    Garante que o dicionário global inicie vazio e seja limpo ao final.
    """
    _MODEL_CACHE.clear()  # Pré-teste: Limpa o cache
    yield  # O teste executa aqui
    _MODEL_CACHE.clear()  # Pós-teste: Limpa o cache novamente


@pytest.fixture
def dataset() -> SentenceTransformerDataset:
    """Fixture para instanciar o dataset padrão de teste."""
    return SentenceTransformerDataset(model_name="all-MiniLM-L6-v2", device="cpu")


class TestSentenceTransformerDataset:
    def test_describe(self, dataset: SentenceTransformerDataset) -> None:
        """Testa se o describe retorna os parâmetros corretos."""
        desc = dataset._describe()
        assert desc == {"model_name": "all-MiniLM-L6-v2", "device": "cpu"}

    def test_save_raises_error(self, dataset: SentenceTransformerDataset) -> None:
        """Garante que o método save levanta NotImplementedError."""
        with pytest.raises(NotImplementedError, match="apenas para leitura"):
            dataset._save(data="modelo_fake")

    def test_load_caching_logic(
        self, mocker: MockerFixture, dataset: SentenceTransformerDataset
    ) -> None:
        """Testa se o modelo é carregado apenas uma vez (lógica de cache)."""
        # Mock da classe SentenceTransformer no local onde o dataset a importa
        mock_st_class = mocker.patch(
            "thelook_ecommerce_analysis.datasets.sentence_transformers_model.SentenceTransformer",
            return_value=mocker.Mock(),
        )

        # 1ª chamada ao load: deve instanciar o modelo
        model_1 = dataset._load()
        assert mock_st_class.call_count == 1
        mock_st_class.assert_called_once_with("all-MiniLM-L6-v2", device="cpu")

        # 2ª chamada ao load: deve retornar o cache (não chama o construtor de novo)
        model_2 = dataset._load()
        assert mock_st_class.call_count == 1
        assert model_1 is model_2  # Verifica se é exatamente o mesmo objeto na memória

    def test_multiple_models_in_cache(self, mocker: MockerFixture) -> None:
        """Garante que modelos diferentes criam chaves distintas no cache global."""
        mock_st_class = mocker.patch(
            "thelook_ecommerce_analysis.datasets.sentence_transformers_model.SentenceTransformer",
            return_value=MagicMock(),
        )

        # Instanciar dois datasets apontando para modelos diferentes
        ds_a = SentenceTransformerDataset(model_name="modelo-A", device="cpu")
        ds_b = SentenceTransformerDataset(model_name="modelo-B", device="cuda")

        ds_a._load()
        ds_b._load()

        assert mock_st_class.call_count == 2, (
            "O construtor deveria ter sido chamado duas vezes."
        )
        assert "modelo-A" in _MODEL_CACHE, "modelo-A deveria existir em 'MODEL_CACHE'"
        assert "modelo-B" in _MODEL_CACHE, "modelo-B deveria existir em 'MODEL_CACHE'"
