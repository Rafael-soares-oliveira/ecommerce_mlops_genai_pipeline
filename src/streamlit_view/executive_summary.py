from typing import TYPE_CHECKING

import pyarrow as pa
from ibis.backends.postgres import Backend

if TYPE_CHECKING:
    import pandas as pd

import streamlit as st

from rag_config.llm_service import (
    generate_executive_summary,
)
from rag_config.sql_executor import execute_and_validate_sql

# TODO: Query usada para teste, corrigir para utilizar CURRENT DATE
PROMPT_SUMMARY_SQL = """
SELECT * FROM metrics.sales_daily
WHERE date BETWEEN '2026-01-20' AND '2026-01-21'
"""


# ======================================
# Geração de Resumo
# ======================================
def _generate_summary_data(con: Backend) -> pa.Table | None:
    """
    Busca dados para a geração do resumo com autocorreção.

    Args:
        con: Conexão com banco de dados,

    Returns:
        pa.Table: Tabela PyArrow com resumo ou None se falhar.
    """
    with st.status("Extraindo dados do PostgreSQL...", expanded=True) as status:
        try:
            st.write("▶️ Executando query analítica...")
            pa_table, stats = execute_and_validate_sql(PROMPT_SUMMARY_SQL, con)

            st.write(f"✅ {stats}")
            status.update(
                label="Dados extraídos com sucesso!", state="complete", expanded=False
            )
            return pa_table

        except Exception as e:
            status.update(label="Falha na extração de dados.", state="error")
            st.error(f"Erro ao consultar o banco: {e}")
            return None


def _write_summary_section(title: str, content: str) -> None:
    """Gera a seção do resumo com estilo."""
    st.markdown(f"## {title}")
    st.markdown(content)
    st.divider()


# ======================================
# Renderizar Página
# ======================================
def render_executive_summary_page(con: Backend) -> None:
    """
    Renderiza a página de resumo executivo diário.

    Args:
        con: Conexão ativa com o banco de dados.
        router: Instância do roteador semântico para contexto RAG.
    """
    st.title("📝 Resumo Diário Executivo")
    st.markdown(
        "Geração automática de insights comparando os dados de ontem com dois dias atrás."
    )

    # Botões de Controle
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Gerar Resumo", type="primary", use_container_width=True):
            st.session_state["start_summary_generation"] = True

    with col2:
        if st.button("Limpar Tela", use_container_width=True):
            st.session_state["start_summary_generation"] = False
            st.rerun()

    with col3:
        show_raw = st.checkbox("Mostrar dados brutos", value=False)

    st.markdown("---")

    if not st.session_state.get("start_summary_generation", False):
        st.info(
            "Clique em 'Gerar Resumo' para começar a análise. Isso pode levar alguns segundos."
        )
        return

    # 1. Extração dos dados
    pa_table = _generate_summary_data(con)

    if pa_table is None:
        st.stop()

    df: pd.DataFrame = pa_table.to_pandas()

    if df.empty:
        st.warning("Query não retornou dado algum. Não é possível gerar um resumo.")
        st.stop()

    # 2. Gerar resumo
    with st.spinner("IA escrevendo o resumo executivo..."):
        try:
            data_md: str = df.to_string(index=False)
            summary_text: str = generate_executive_summary(data_md)
        except Exception as e:
            st.error(f"Erro gerando o resumo: {e}")
            st.stop()

    # Mostrar resultados
    st.success("✅ Resumo gerado com sucesso!")

    st.markdown("### Insights da IA")
    st.info(summary_text, icon="🤖")

    # Mostrar query usada
    with st.expander("🔍 Ver Query SQL Utilizada"):
        st.code(PROMPT_SUMMARY_SQL, language="sql")

    # Mostrar dados brutos
    if show_raw:
        st.markdown("---")
        st.markdown("### 🗃️ Dados Extraídos")
        col1, col2 = st.columns([3, 1])

        with col1:
            st.dataframe(df, use_container_width=True, hide_index=True)

        with col2:
            st.caption("**Estatísticas da Tabela:**")
            st.write(f"- Linhas: **{len(df)}**")
            st.write(f"- Colunas: **{len(df.columns)}**")
            st.write(f"Memória: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
