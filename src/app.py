import os
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer  # noqa: TC004


# Configurações de página
st.set_page_config(page_title="TheLook RAG", layout="wide")


# Função cacheada para carregar o modelo
@st.cache_resource
def load_embedding_model(model_name: str, device: str) -> SentenceTransformer:
    # O modelo será buscado em /app/model_cache automaticamente por causa do HF_HOME
    st.info(f"Carregando modelo {model_name} para a RAM...")
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    return SentenceTransformer(model_name, device=device)


# --- UI ---
st.title("TheLook eCommerce - RAG & Analytics")

# Sidebar com status
with st.sidebar:
    st.header("Configurações")
    # Pegando variáveis de ambiente ou definindo defaults
    model_name = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # Carrega o modelo (na primeira vez demora, depois é instantâneo)
    model = load_embedding_model(model_name, device="cpu")

    st.success("🤖 Modelo de Embedding pronto!")
    st.success("🐘 Conectado ao Postgres")

st.write("Interface pronta para receber consultas via RAG.")
