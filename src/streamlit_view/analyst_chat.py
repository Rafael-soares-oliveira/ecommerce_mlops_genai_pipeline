import re
import traceback

import numpy as np
import pandas as pd
import pyarrow as pa
import streamlit as st
from ibis.backends.postgres import Backend

from rag_config.llm_service import (
    fix_sql_error,
    generate_sql_from_prompt,
    translate_to_english,
)
from rag_config.semantic_router import InMemorySemanticRouter
from rag_config.sql_executor import execute_and_validate_sql


# ======================================
# Chart Rendering
# ======================================
def _get_dataframe_columns(pa_table: pa.Table) -> tuple[pd.DataFrame, list, list]:
    """Extract numeric and categorical columns."""
    df = pa_table.to_pandas()
    df = df.apply(lambda x: pd.to_numeric(x, errors="ignore"))
    num_cols = df.select_dtypes(include=["number", "float", "int"]).columns.tolist()
    cat_cols = df.select_dtypes(
        include=["object", "category", "string", "datetime"]
    ).columns.tolist()
    return df, num_cols, cat_cols


def _render_single_metric(df: pd.DataFrame, num_cols: list) -> None:
    """Render a single metric value."""
    st.metric(
        label=num_cols[0].replace("_", " ").title(),
        value=f"{df.iloc[0, 0]:,.2f}",
    )


def _render_time_or_category_chart(
    df: pd.DataFrame, cat_cols: list, num_cols: list
) -> None:
    """Render line or bar chart based on categorical column type."""
    index_col = cat_cols[0]
    chart_data = df.set_index(index_col)[num_cols]
    chart_func = st.line_chart if df[index_col].dtype.kind in "Mm" else st.bar_chart
    chart_func(chart_data)


def render_heuristic_chart(pa_table: pa.Table) -> None:
    """Intelligently render chart based on data structure."""
    if pa_table.num_rows == 0:
        st.warning("Query não retornou dados.")
        return

    df, num_cols, cat_cols = _get_dataframe_columns(pa_table)

    if not num_cols:
        st.info("Nenhuma coluna numérica para visualizar.")
        return

    if len(df) == 1 and len(num_cols) == 1 and len(df.columns) == 1:
        _render_single_metric(df, num_cols)
    elif cat_cols and num_cols:
        _render_time_or_category_chart(df, cat_cols, num_cols)
    elif len(num_cols) >= 2:  # noqa: PLR2004
        st.scatter_chart(df.set_index(num_cols[0])[num_cols[1:]])


# ======================================
# SQL Generation & Execution
# ======================================
def _retrieve_and_prepare_context(
    router: InMemorySemanticRouter, translated_prompt: str
) -> str:
    """Retrieve table context and return full context string."""
    with st.status("Mapeando tabelas...", expanded=True) as status:
        context_str = router.retrieve_context(translated_prompt, top_k=6)
        used_tables = re.findall(r"--- Tabela: (.*?) ---", context_str)

        if used_tables:
            st.write("**Arquivos de Contexto (YAML) selecionados:**")
            for table in used_tables:
                st.caption(f"📄 `{table}.yaml`")
        else:
            st.warning("Nenhum contexto de tabela encontrado.")

        status.update(label="✅ Contexto recuperado.", expanded=False)

    return f"GOLDEN RULES: Use schema.table format.\n\nCONTEXTS:\n{context_str}"


def _build_history_context() -> str:
    """Build context from previous messages."""
    if len(st.session_state.messages) >= 3:  # noqa: PLR2004
        last_sql = st.session_state.messages[-2].get("sql", "")
        last_user = st.session_state.messages[-3].get("content", "")
        if last_sql:
            return f"Previous Question: {last_user}\nPrevious SQL:\n{last_sql}\n\n"
    return ""


def _generate_sql_query(translated_prompt: str, full_context: str) -> str:
    """Generate SQL query with history context."""
    with st.status("Traduzindo pergunta para SQL...", expanded=True) as status:
        prompt_with_history = (
            f"{_build_history_context()}Current Question: {translated_prompt}"
        )
        sql_query = generate_sql_from_prompt(prompt_with_history, full_context)
        st.write("**Query Gerada:**")
        st.code(sql_query, language="sql")
        status.update(label="✅ Query SQL escrita.", expanded=False)
    return sql_query


def _execute_sql_with_retry(
    sql_query: str, con: Backend, full_context: str, translated_prompt: str
) -> tuple[pa.Table | None, str]:
    """Execute SQL with auto-correction on failure."""
    for attempt in range(1, 4):
        try:
            with st.status(
                f"Executando no banco (tentativa {attempt}/3)...", expanded=True
            ) as status:
                st.write("**Executando a query:**")
                st.code(sql_query, language="sql")
                pa_table, stats = execute_and_validate_sql(sql_query, con)
                status.update(label=f"✅ {stats}", expanded=False)
                return pa_table, sql_query

        except Exception as e:
            if attempt == 3:  # noqa: PLR2004
                error_msg = "❌ A query falhou permanentemente após 3 tentativas."
                st.error(error_msg)
                return None, sql_query

            with st.status(
                f"🛠️ Autocorreção do erro (tentativa {attempt})...", expanded=True
            ) as status:
                st.warning(f"Erro:\n`{e}`")
                st.write("Reescrevendo a query...")
                sql_query = fix_sql_error(
                    translated_prompt, sql_query, str(e), full_context
                )
                st.write("**Nova Query Gerada:**")
                st.code(sql_query, language="sql")
                status.update(
                    label="✅ Erro corrigido, tentando novamente...", expanded=False
                )

    return None, sql_query


def _handle_cached_result(cached_result: dict) -> tuple[pa.Table, str, bool]:
    """Handle cache hit scenario."""
    st.success("⚡ Cache Hit! Carregando dados instantaneamente da RAM.")
    return cached_result["dataframe"], cached_result["sql"], True


# ======================================
# UI Components
# ======================================
def _display_results(pa_table: pa.Table, sql_query: str) -> None:
    """Display results and cache metrics."""
    st.markdown("### Resultados")
    render_heuristic_chart(pa_table)

    col1, col2 = st.columns([3, 1])
    with col1:
        with st.expander("🔍 Ver SQL Executado"):
            st.code(sql_query, language="sql")
    with col2:
        with st.expander("📊 Métricas de Cache"):
            stats = st.session_state.cache.get_stats()
            st.metric("Taxa de Acerto (Hit Rate)", f"{stats['hit_rate']:.1f}%")
            st.write(f"- Hits: **{stats['hits']}**\n- Misses: **{stats['misses']}**")


def _display_message_history() -> None:
    """Render all previous messages with data and SQL."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("data") is not None:
                render_heuristic_chart(msg["data"])
            if msg.get("sql"):
                with st.expander("Ver SQL Executado"):
                    st.code(msg["sql"], language="sql")


# ======================================
# AI Response Processing
# ======================================
def _process_ai_response(
    prompt: str, con: Backend, router: InMemorySemanticRouter
) -> None:
    """Process user prompt and generate AI response with SQL."""
    with st.spinner("⏳ Analisando e processando query..."):
        try:
            with st.status("Preparando Agente...", expanded=False) as status:
                translated_prompt = translate_to_english(prompt)
                status.update(label="✅ Tradução concluída.")

            query_vec = np.array(
                router.embedder.encode(translated_prompt, convert_to_numpy=True)
            )
            cached_result = st.session_state.cache.check_cache(query_vec)

            if cached_result:
                pa_table, sql_query, _ = _handle_cached_result(cached_result)
            else:
                full_context = _retrieve_and_prepare_context(router, translated_prompt)
                sql_query = _generate_sql_query(translated_prompt, full_context)
                pa_table, sql_query = _execute_sql_with_retry(
                    sql_query, con, full_context, translated_prompt
                )

                if pa_table is not None:
                    st.session_state.cache.add_to_cache(query_vec, pa_table, sql_query)
                else:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": "❌ Falha ao executar query."}
                    )
                    return

            _display_results(pa_table, sql_query)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "Aqui estão os resultados da sua consulta:",
                    "sql": sql_query,
                    "data": pa_table,
                }
            )

        except Exception as e:
            error_msg = f"Erro Crítico no RAG: {e}"
            st.error(error_msg)
            st.code(traceback.format_exc(), language="python")
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )


# ======================================
# Main Chatbot Page
# ======================================
def render_chatbot_page(con: Backend, router: InMemorySemanticRouter) -> None:
    """Render the main RAG chatbot interface."""
    st.title("🤖 Agente Analítico RAG")
    st.markdown(
        "Faça perguntas sobre os dados. Eu irei gerar uma query SQL e te mostrar os resultados."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "processing" not in st.session_state:
        st.session_state.processing = False

    _display_message_history()

    # Prevent input while processing
    is_processing = st.session_state.get("processing", False)

    if is_processing:
        st.info("⏳ Processando sua pergunta... Por favor aguarde.")
    elif prompt := st.chat_input("Ex: Qual o faturamento bruto total no último mês?"):
        st.session_state.processing = True
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            _process_ai_response(prompt, con, router)

        st.session_state.processing = False
        st.rerun()
