from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pytest_mock import MockerFixture

from rag_config.semantic_router import (
    InMemorySemanticRouter,
    _get_embedding_cached,
    cosine_similarity,
)


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Limpa o cache LRU global antes de cada teste."""
    _get_embedding_cached.cache_clear()


@pytest.fixture
def mock_embedder(mocker: MockerFixture) -> Any:
    """Mock do SentenceTransformer para evitar downloads durante o teste."""
    mock_model = mocker.patch("rag_config.semantic_router.SentenceTransformer")
    mock_instance = mock_model.return_value
    mock_instance.encode.return_value = np.array(
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32
    )
    return mock_instance


@pytest.fixture
def dummy_yaml_dir(tmp_path: Path) -> str:
    """Cria um diretório temporário com arquivos YAML válidos e inválidos."""
    # YAML com description
    f1 = tmp_path / "table1.yaml"
    f1.write_text(
        "description: 'Resumo da tabela 1'\ncolumns:\n  - id", encoding="utf-8"
    )

    # YAML sem description
    f2 = tmp_path / "table2.yml"
    f2.write_text("columns:\n  - name", encoding="utf-8")

    # Arquivo ignorado
    f3 = tmp_path / "ignore.txt"
    f3.write_text("texto qualquer", encoding="utf-8")

    return str(tmp_path)


def test_cosine_similarity() -> None:
    """Testa o cálculo da similaridade do cosseno."""
    v1 = np.array([1.0, 0.0])
    v2 = np.array([1.0, 0.0])
    v3 = np.array([0.0, 1.0])
    v_zero = np.array([0.0, 0.0])

    assert cosine_similarity(v1, v2) == 1.0
    assert cosine_similarity(v1, v3) == 0.0
    assert cosine_similarity(v1, v_zero) == 0.0


def test_get_embedding_cached(mock_embedder: Any) -> None:
    """Testa se a função global faz o cache corretamente."""
    # Configura o mock para retornar um único vetor para textos isolados
    mock_embedder.encode.return_value = np.array([0.1, 0.2], dtype=np.float32)

    vec1 = _get_embedding_cached(mock_embedder, "teste")
    vec2 = _get_embedding_cached(mock_embedder, "teste")

    assert np.array_equal(vec1, vec2)
    # Deve chamar o encode apenas 1 vez devido ao @lru_cache
    mock_embedder.encode.assert_called_once()


def test_router_init_dir_not_found() -> None:
    """Testa a exceção gerada quando o diretório YAML não existe."""
    with pytest.raises(RuntimeError, match="Diretório de YAMLs não encontrado"):
        InMemorySemanticRouter(yaml_dir="/path/invalido/inexistente")


def test_router_init_empty_dir(tmp_path: Path, mock_embedder: Any) -> None:
    """Testa inicialização com diretório vazio (sem falha crítica, mas sem contextos)."""
    router = InMemorySemanticRouter(yaml_dir=str(tmp_path))
    assert len(router.contexts) == 0
    assert router.embeddings is None


def test_router_load_and_embed_success(dummy_yaml_dir: str, mock_embedder: Any) -> None:
    """Testa a carga correta dos arquivos YAML e geração de embeddings."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)

    assert len(router.contexts) == 2
    assert router.embeddings is not None
    assert router.embeddings.shape == (2, 3)

    # Verifica se extraiu a chave description ou usou o texto original
    contexts_content = [c["content"] for c in router.contexts]
    assert any("Resumo da tabela 1" in c for c in contexts_content)


def test_router_load_yaml_fallback(
    dummy_yaml_dir: str, mock_embedder: Any, mocker: MockerFixture
) -> None:
    """Testa fallback quando o yaml.safe_load falha (arquivo mal formatado)."""
    # Força exceção no parser YAML
    mocker.patch("yaml.safe_load", side_effect=Exception("YAML Error"))
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)

    # Ainda deve carregar 2 contextos com o texto completo
    assert len(router.contexts) == 2


def test_router_load_file_exception(
    dummy_yaml_dir: str, mock_embedder: Any, mocker: MockerFixture
) -> None:
    """Testa continuação (continue) em caso de erro de leitura de arquivo."""
    mocker.patch("builtins.open", side_effect=PermissionError("Acesso negado"))
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)

    # Não deve subir exceção principal, apenas ignorar o arquivo problemático
    assert len(router.contexts) == 0


def test_retrieve_context_no_data(dummy_yaml_dir: str, mock_embedder: Any) -> None:
    """Testa a recuperação sem contextos carregados."""
    # Força contextos vazios
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)
    router.embeddings = None

    res = router.retrieve_context("pergunta")
    assert res == "Nenhum contexto de tabela disponível."


def test_retrieve_context_success(
    dummy_yaml_dir: str, mock_embedder: Any, mocker: MockerFixture
) -> None:
    """Testa a recuperação de contexto baseada na similaridade."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)

    # Mock _cached_encode para retornar vetor específico
    mock_query_vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    mocker.patch.object(router, "_cached_encode", return_value=mock_query_vec)

    # mock dot e norm para controlar a similaridade calculada (forçar > 0.5)
    mocker.patch("numpy.dot", return_value=np.array([0.8, 0.4]))
    mocker.patch("numpy.linalg.norm", return_value=1.0)

    # Top 1 com similaridade 0.8
    result = router.retrieve_context("pergunta", top_k=1, min_similarity=0.5)

    assert "Relevância:" in result
    assert "Tabela:" in result


def test_retrieve_context_below_threshold(
    dummy_yaml_dir: str, mock_embedder: Any, mocker: MockerFixture
) -> None:
    """Testa retorno quando nenhuma similaridade atinge o mínimo (threshold)."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)
    mocker.patch.object(
        router, "_cached_encode", return_value=np.array([0.1, 0.2, 0.3])
    )

    # Força similaridades baíxas
    mocker.patch("numpy.dot", return_value=np.array([0.1, 0.2]))
    mocker.patch("numpy.linalg.norm", return_value=1.0)

    result = router.retrieve_context("pergunta", top_k=2, min_similarity=0.9)
    assert result == "Nenhum contexto relevante encontrado."


def test_retrieve_context_batch_no_data(
    dummy_yaml_dir: str, mock_embedder: Any
) -> None:
    """Testa recuperação em batch quando não há embeddings."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)
    router.embeddings = None

    res = router.retrieve_context_batch(["p1", "p2"])
    assert res == ["Nenhum contexto disponível.", "Nenhum contexto disponível."]


def test_retrieve_context_batch_success(
    dummy_yaml_dir: str, mock_embedder: Any, mocker: MockerFixture
) -> None:
    """Testa recuperação em lote lidando com o fluxo do código original corrigido."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)

    mocker.patch.object(
        router, "_cached_encode", return_value=np.array([0.1, 0.2, 0.3])
    )

    fake_argsort_output = np.array([0, 1])
    mocker.patch(
        "rag_config.semantic_router.np.argsort", return_value=fake_argsort_output
    )

    results = router.retrieve_context_batch(["pergunta_1"], top_k=1, min_similarity=0.0)

    assert len(results) == 1
    assert "--- Table:" in results[0]


def test_get_all_contexts(dummy_yaml_dir: str, mock_embedder: Any) -> None:
    """Testa obtenção de todos os textos concatenados."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)
    full_text = router.get_all_contexts()

    assert "--- Table: table1 ---" in full_text
    assert "--- Table: table2 ---" in full_text


def test_get_stats(dummy_yaml_dir: str, mock_embedder: Any) -> None:
    """Testa emissão de estatísticas do router."""
    router = InMemorySemanticRouter(yaml_dir=dummy_yaml_dir)

    # Força o cache a ter pelo menos 1 item para stats
    router._cached_encode("dummy")

    stats = router.get_stats()

    assert stats["num_contexts"] == 2
    assert stats["embedding_shape"] == (2, 3)
    assert stats["model"] == "all-MiniLM-L6-v2"
    assert stats["rag_model"] == "qwen2.5-coder:3b"
    assert "cache_size" in stats
    assert "cache_hits" in stats
