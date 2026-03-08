import logging
import time

import polars as pl
import streamlit as st
from ibis.backends.postgres import Backend

# Import de inicialização (Lógica de Backend)
from rag_config.factory import CacheConfig, get_db_client, init_router
from rag_config.semantic_cache import SemanticCache
from rag_config.semantic_router import InMemorySemanticRouter
from streamlit_view.analyst_chat import render_chatbot_page

# Import das páginas modulares (Camada de View)
from streamlit_view.executive_summary import render_executive_summary_page
from streamlit_view.metrics_dashboard import render_metrics_page

logger = logging.getLogger(__name__)


# ======================================
# Configuração da Página
# ======================================
def _configure_page() -> None:
    """Configurações da página do Streamlit."""
    st.set_page_config(
        page_title="TheLook Analytics",
        layout="wide",
        page_icon="📊",
        initial_sidebar_state="expanded",
    )

    # Custom CSS
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"] { font-size: 1.5rem; }
        [data-testid="stMetricLabel"] { font-size: 0.8rem; }
        .streamlit-container { max-width: 100%; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================================
# Inicialização
# ======================================
def _initialize_session_state() -> None:
    """Inicializa a sessão com cache e router."""
    # Cache
    if "cache" not in st.session_state:
        st.session_state.cache = SemanticCache(
            threshold=CacheConfig.SEMANTIC_CACHE_THRESHOLD,
            max_history=CacheConfig.SEMANTIC_CACHE_MAX_HISTORY,
            ttl_seconds=CacheConfig.QUERY_CACHE_TTL,
        )
        logger.info("Semantic Cache inicializado.")

    # Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = []
        logger.info("Chat history inicializado.")

    # Performance tracking
    if "perf_metrics" not in st.session_state:
        st.session_state.perf_metrics = {
            "page_loads": 0,
            "queries_executed": 0,
            "total_time": 0,
        }


# ======================================
# Recuperação de Dados com Cache
# ======================================
@st.cache_data(
    ttl=CacheConfig.QUERY_CACHE_TTL,
    show_spinner=False,
)
def fetch_data(sql_query: str) -> pl.DataFrame:
    """
    Executa SQL via Ibis e retorna um DataFrame Polars.

    Args:
        sql_query (str): Query SQL para executar.

    Returns:
        pl.DataFrame: Resultados da Query.
    """
    try:
        start_time = time.time()
        con = get_db_client()

        # Executa a query
        result = con.sql(sql_query)

        # Converte PyArrow para Polars
        df = pl.from_arrow(result.to_pyarrow())

        # Converte Series para DataFrame se necessário
        if isinstance(df, pl.Series):
            df = df.to_frame()

        # Log Metrics
        duration_ms = (time.time() - start_time) * 1000
        st.session_state.perf_metrics["queries_executed"] += 1
        st.session_state.perf_metrics["total_time"] += duration_ms

        logger.info(
            f"Query executada: {len(df)} linhas x {len(df.columns)} colunas em {duration_ms:.0f}ms"
        )

        return df

    except Exception as e:
        logger.error(f"Execução da query falhou: {e}")
        st.error(f"Erro na execução da query: {e}")
        return pl.DataFrame()


# ======================================
# Sidebar
# ======================================
def _render_sidebar(con: Backend, router: InMemorySemanticRouter) -> str:
    """
    Renderiza a barra lateral de navegação e monitoramento.

    Args:
        con: Conexão do banco de dados.
        router: Semantic Router.

    Returns:
        str: Nome da página selecionada.
    """
    st.sidebar.title("Navegação")

    page = st.sidebar.radio(
        "Selecione a página:",
        ["Resumo Diário", "Métricas", "Chatbot Analítico"],
        index=0,
    )

    st.sidebar.divider()

    # Indicadores de Status
    col1, col2 = st.sidebar.columns(2)

    with col1:
        st.sidebar.success("DB Conectado")

    with col2:
        st.sidebar.info("v1.0")

    st.sidebar.caption("Thelook Analytics Engine")

    st.sidebar.divider()

    # Monitoramento de performance
    with st.sidebar.expander("Performance"):
        metrics = st.session_state.perf_metrics
        st.metric("Page Loads", metrics["page_loads"])
        st.metric("Queries Executed", metrics["queries_executed"])

        if metrics["queries_executed"] > 0:
            avg_time = metrics["total_time"] / metrics["queries_executed"]
            st.metric("Avg Query Time", f"{avg_time:.0f}ms")

    # Monitoramento de Cache
    with st.sidebar.expander("Cache Status"):
        cache_stats = st.session_state.cache.get_stats()
        st.metric("Hit Rate", f"{cache_stats['hit_rate']:.1f}%")
        st.metric("Cache Entries", cache_stats["entries"])
        st.metric("Total Requests", cache_stats["total_requests"])

    # Monitoramento do Router
    with st.sidebar.expander("Router Stats"):
        router_stats = router.get_stats()
        st.metric("Contexts Loaded", router_stats["num_contexts"])
        st.metric("Model", router_stats["model"])
        st.metric("RAG Model", router_stats["rag_model"])

        if router_stats["cache_hits"] > 0:
            st.metric("Embedding Cache Hits", router_stats["cache_hits"])

    # Controles
    st.sidebar.divider()

    if st.sidebar.button("Clear All Caches", use_container_width=True):
        st.session_state.cache.clear()
        st.session_state.messages.clear()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("All caches cleared!")
        st.rerun()

    return page


# ======================================
# Orquestrador Principal
# ======================================
def main() -> None:
    """Orquestrador principal do Streamlit."""

    _configure_page()

    # Inicializar sessão
    _initialize_session_state()

    # Inicializar recursos
    logger.info("Iniciando recursos da aplicação...")

    con = get_db_client()
    router = init_router()

    # Sidebar e Seleção de página
    page = _render_sidebar(con, router)

    # Update Metrics
    st.session_state.perf_metrics["page_loads"] += 1

    # Page Routing
    if page == "Resumo Diário":
        render_executive_summary_page(con)

    elif page == "Métricas":
        render_metrics_page(fetch_data)

    elif page == "Chatbot Analítico":
        render_chatbot_page(con, router)

    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("Powered by Streamlit + LLM")

    with col2:
        st.caption("Analytics Engine v1.0")

    with col3:
        st.caption("PostgreSQL Backend")


if __name__ == "__main__":
    main()
