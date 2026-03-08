import logging
import os
from pathlib import Path
from typing import Any, cast

import streamlit as st
from ibis.backends import BaseBackend
from ibis.backends.postgres import Backend

from rag_config.semantic_router import InMemorySemanticRouter

logger = logging.getLogger(__name__)


class DatabasePool:
    """Gerencia a conexão PostgreSQL com iniciação em modo Lazy."""

    _instance = None
    _connection = None

    def __new__(cls) -> Any:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _create_connection() -> BaseBackend:
        """Cria uma única conexão com os parâmetros de ambiente."""
        try:
            con = Backend().connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.getenv("POSTGRES_PASSWORD", "admin_password"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "thelook_db"),
            )
            logger.info("Conexão com PostgreSQL estabelecida via Ibis.")
            return con
        except Exception as e:
            logger.error(f"Conexão com PostgreSQL falhou: {e}")
            raise


@st.cache_resource
def get_db_client() -> Backend:
    """Singleton da conexão para todo o app Streamlit."""
    return cast("Backend", DatabasePool._create_connection())


@st.cache_resource(show_spinner=False)
def init_router() -> InMemorySemanticRouter:
    """Inicializa o Roteador Semântico com os contextos YAML."""
    yaml_path = Path(__file__).parent.parent / "rag_config" / "context_yamls"

    if not os.path.exists(yaml_path):
        error_msg = f"🚨 Diretório de contextos não encontrada: {yaml_path}"
        logger.error(error_msg)
        st.error(error_msg)
        st.stop()

    logger.info("Inicializando Semantic Router...")

    return InMemorySemanticRouter(yaml_dir=str(yaml_path))


# =======================
# Configuração de Cache
# =======================


class CacheConfig:
    """Configuração centralizada de cache para o aplicativo."""

    # Query caching
    QUERY_CACHE_TTL = int(os.getenv("QUERY_CACHE_TTL", "3600"))  # 1 hora
    DATA_CACHE_TTL = int(os.getenv("DATA_CACHE_TTL", "1800"))  # 30 min

    # Geographic data caching
    GEO_CACHE_TTL = int(os.getenv("GEO_CACHE_TTL", "3600"))  # 1 hora

    # Semantic cache
    SEMANTIC_CACHE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.95"))
    SEMANTIC_CACHE_MAX_HISTORY = int(os.getenv("SEMANTIC_CACHE_MAX_HISTORY", "10"))

    @classmethod
    def log_config(cls) -> None:
        """Configuração do cache de logs para debug."""
        logger.info(
            f"Cache Config: Query={cls.QUERY_CACHE_TTL}s, "
            f"Data={cls.DATA_CACHE_TTL}s, Geo={cls.GEO_CACHE_TTL}s"
        )


# Configuração do log no import
CacheConfig.log_config()
