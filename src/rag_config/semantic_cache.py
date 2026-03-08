import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from rag_config.semantic_router import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Representa uma única entrada de cache com metadados."""

    embedding: np.ndarray
    dataframe: Any
    sql: str
    timestamp: float = field(default_factory=time.time)
    access_count: int = field(default=0)

    def is_expired(self, ttl: int) -> bool:
        """Verifica se excedeu o tempo de vida útil."""
        return (time.time() - self.timestamp) > ttl

    def access(self) -> None:
        """Registra acesso e atualiza data/hora."""
        self.access_count += 1
        self.timestamp = time.time()


class SemanticCache:
    """
    Gerencia o cache de perguntas e resultados em memória por sessão.

    Utiliza similaridade de cosseno para evitar reprocessamento de perguntas semanticamente próximas à última consulta realizada.

    Args:
        threshold (float, optional): Limiar de similaridade para considerar um cache hit (0.0 a 1.0). Padrão 0.90.
        max_history (int, optional): Número máximo de interações mantidas no histórico. Padrão 10.
        ttl_seconds (int): Time-to-live (Tempo de vida útil) para entradas de cache.
    """

    def __init__(
        self, threshold: float = 0.90, max_history: int = 10, ttl_seconds: int = 3600
    ):
        self.threshold = threshold
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        self.history: list[CacheEntry] = []
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def check_cache(self, query_vec: np.ndarray) -> dict[str, Any] | None:
        """
        Verifica se a pergunta atual é semanticamente idêntica à última.

        Args:
            query_vec (np.ndarray): O vetor (embedding) da pergunta atual.

        Returns:
            dict[str, Any] | None: Dicionário com os dados cacheados ('embedding', 'dataframe', 'sql') em caso de hit, ou None para miss.
        """
        # Limpa entradas expiradas
        self._cleanup_expired()

        if not self.history:
            self._stats["misses"] += 1
            return None

        # Compara apenas com a última pergunta feita
        last_entry = self.history[-1]
        similarity = cosine_similarity(query_vec, last_entry.embedding)

        if similarity >= self.threshold:
            # Marca como acessado
            last_entry.access()
            self._stats["hits"] += 1

            logger.info(
                f"Cache Hit! Similaridade: {similarity:.3f} | "
                f"Hits: {self._stats['hits']} | Misses: {self._stats['misses']}"
            )
            return {
                "embedding": last_entry.embedding,
                "dataframe": last_entry.dataframe,
                "sql": last_entry.sql,
                "similarity": similarity,
            }

        self._stats["misses"] += 1

        logger.info(
            f"Cache Miss. Similaridade: {similarity:.3f} (Abaixo de {self.threshold})"
        )
        return None

    def add_to_cache(self, query_vec: np.ndarray, dataframe: Any, sql: str) -> None:
        """
        Salva o vetor da pergunta, a query gerada e os dados (PyArrow) no cache (FIFO).

        Args:
            query_vec (np.ndarray): O vetor (embedding) da pergunta processada.
            dataframe (Any): Dados resultantes da execução da query (ex: Pandas, PyArrow).
            sql (str): A query SQL gerada associada à pergunta.
        """
        entry = CacheEntry(embedding=query_vec, dataframe=dataframe, sql=sql)

        self.history.append(entry)

        # Impede que o histórico cresça infinitamente e consuma muita RAM
        while len(self.history) > self.max_history:
            evictions = self.history.pop(0)
            self._stats["evictions"] += 1
            logger.info(
                f"Entrada de cache removida (acessada {evictions.access_count} vezes)"
            )

    def _cleanup_expired(self) -> None:
        """Remove entradas expiradas do cache."""
        initial_size = len(self.history)
        self.history = [
            entry for entry in self.history if not entry.is_expired(self.ttl_seconds)
        ]

        evictions = initial_size - len(self.history)
        if evictions > 0:
            self._stats["evictions"] += evictions
            logger.info(f"Limpeza de {evictions} entradas expiradas.")

    def get_stats(self) -> dict[str, Any]:
        """Obtém estatísticas do cache para monitoramento."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests * 100 if total_requests > 0 else 0.0
        )

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": hit_rate,
            "entries": len(self.history),
            "total_requests": total_requests,
        }

    def clear(self) -> None:
        """Limpa todo o cache."""
        self.history.clear()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
        logger.info("Cache limpo.")
