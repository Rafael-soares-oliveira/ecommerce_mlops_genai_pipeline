import os

import streamlit as st
from sentence_transformers import SentenceTransformer

# Configurações de página
st.set_page_config(page_title="TheLook RAG", layout="wide")


# Função cacheada para carregar o modelo
@st.cache_resource
def load_embedding_model(model_name: str, device: str) -> SentenceTransformer:
    # O modelo será buscado em /app/model_cache automaticamente por causa do HF_HOME
    st.info(f"Carregando modelo {model_name} para a RAM...")

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
