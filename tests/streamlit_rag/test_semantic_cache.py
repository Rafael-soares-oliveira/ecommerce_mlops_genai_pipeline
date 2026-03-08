from typing import Any

import numpy as np
import pytest
from pytest_mock import MockerFixture

from rag_config.semantic_cache import CacheEntry, SemanticCache


@pytest.fixture
def sample_embedding() -> np.ndarray:
    """Retorna um embedding de exemplo."""
    return np.array([0.1, 0.2, 0.3])


@pytest.fixture
def mock_cosine_similarity(mocker: MockerFixture) -> Any:
    """Mock para a função cosine_similarity importada no semantic_cache."""
    return mocker.patch("rag_config.semantic_cache.cosine_similarity")


def test_cache_entry_is_expired(
    mocker: MockerFixture, sample_embedding: np.ndarray
) -> None:
    """Testa se a entrada expira corretamente baseada no TTL."""
    mock_time = mocker.patch("rag_config.semantic_cache.time.time")

    # Define timestamp explícito para burlar o default_factory
    entry = CacheEntry(
        embedding=sample_embedding, dataframe="df", sql="SELECT 1", timestamp=100.0
    )

    # Avança o tempo simulado
    mock_time.return_value = 150.0

    assert entry.is_expired(ttl=40) is True
    assert entry.is_expired(ttl=60) is False


def test_cache_entry_access(
    mocker: MockerFixture, sample_embedding: np.ndarray
) -> None:
    """Testa a atualização do timestamp e contagem ao acessar a entrada."""
    mock_time = mocker.patch("rag_config.semantic_cache.time.time")
    mock_time.return_value = 200.0

    entry = CacheEntry(
        embedding=sample_embedding, dataframe="df", sql="SELECT 1", timestamp=100.0
    )
    assert entry.access_count == 0

    entry.access()

    assert entry.access_count == 1
    assert entry.timestamp == 200.0


def test_semantic_cache_add_and_evict(sample_embedding: np.ndarray) -> None:
    """Testa adição de itens e remoção por limite de max_history (FIFO)."""
    cache = SemanticCache(max_history=2)

    cache.add_to_cache(sample_embedding, "df1", "SELECT 1")
    cache.add_to_cache(sample_embedding, "df2", "SELECT 2")

    assert len(cache.history) == 2
    assert cache.history[0].sql == "SELECT 1"

    # Adicionar o 3º deve remover o 1º
    cache.add_to_cache(sample_embedding, "df3", "SELECT 3")

    assert len(cache.history) == 2
    assert cache.history[0].sql == "SELECT 2"
    assert cache.history[1].sql == "SELECT 3"
    assert cache._stats["evictions"] == 1


def test_semantic_cache_check_empty(sample_embedding: np.ndarray) -> None:
    """Testa a verificação de cache quando o histórico está vazio."""
    cache = SemanticCache()
    result = cache.check_cache(sample_embedding)

    assert result is None
    assert cache._stats["misses"] == 1


def test_semantic_cache_check_miss(
    mock_cosine_similarity: Any, sample_embedding: np.ndarray
) -> None:
    """Testa um cache miss por similaridade abaixo do threshold."""
    mock_cosine_similarity.return_value = 0.5
    cache = SemanticCache(threshold=0.9)
    cache.add_to_cache(sample_embedding, "df", "SELECT 1")

    # query_vec diferente, mas mock forçará similaridade 0.5
    query_vec = np.array([0.9, 0.8, 0.7])
    result = cache.check_cache(query_vec)

    assert result is None
    assert cache._stats["misses"] == 1
    assert cache._stats["hits"] == 0


def test_semantic_cache_check_hit(
    mock_cosine_similarity: Any, sample_embedding: np.ndarray
) -> None:
    """Testa um cache hit com similaridade acima do threshold."""
    mock_cosine_similarity.return_value = 0.95
    cache = SemanticCache(threshold=0.9)
    cache.add_to_cache(sample_embedding, "df_hit", "SELECT HIT")

    query_vec = np.array([0.11, 0.21, 0.31])
    result = cache.check_cache(query_vec)

    assert result is not None
    assert result["dataframe"] == "df_hit"
    assert result["sql"] == "SELECT HIT"
    assert result["similarity"] == 0.95
    assert cache._stats["hits"] == 1
    assert cache.history[-1].access_count == 1


def test_semantic_cache_cleanup_expired(
    mocker: MockerFixture, sample_embedding: np.ndarray
) -> None:
    """Testa a remoção de entradas expiradas antes da verificação."""
    mock_time = mocker.patch("rag_config.semantic_cache.time.time")

    cache = SemanticCache(ttl_seconds=50)

    cache.add_to_cache(sample_embedding, "df1", "SELECT 1")
    cache.history[-1].timestamp = 100.0  # Força o timestamp pós-criação

    cache.add_to_cache(sample_embedding, "df2", "SELECT 2")
    cache.history[-1].timestamp = 120.0  # Força o timestamp pós-criação

    mock_time.return_value = (
        160.0  # Tempo no momento do check. O primeiro expira (160 - 100 > 50)
    )

    # _cleanup_expired é chamado dentro de check_cache
    cache.check_cache(sample_embedding)

    assert len(cache.history) == 1
    assert cache.history[0].sql == "SELECT 2"
    assert cache._stats["evictions"] == 1


def test_semantic_cache_get_stats(sample_embedding: np.ndarray) -> None:
    """Testa o cálculo e retorno das estatísticas do cache."""
    cache = SemanticCache()
    cache._stats = {"hits": 8, "misses": 2, "evictions": 5}
    cache.add_to_cache(sample_embedding, "df", "SELECT 1")

    stats = cache.get_stats()

    assert stats["hits"] == 8
    assert stats["misses"] == 2
    assert stats["evictions"] == 5
    assert stats["hit_rate"] == 80.0
    assert stats["entries"] == 1
    assert stats["total_requests"] == 10


def test_semantic_cache_get_stats_zero_requests() -> None:
    """Testa estatísticas quando não houve requisições (evita DivByZero)."""
    cache = SemanticCache()
    stats = cache.get_stats()

    assert stats["hit_rate"] == 0.0
    assert stats["total_requests"] == 0


def test_semantic_cache_clear(sample_embedding: np.ndarray) -> None:
    """Testa a limpeza completa do cache e reset de métricas."""
    cache = SemanticCache()
    cache.add_to_cache(sample_embedding, "df", "SELECT 1")
    cache._stats["hits"] = 5

    cache.clear()

    assert len(cache.history) == 0
    assert cache._stats == {"hits": 0, "misses": 0, "evictions": 0}
