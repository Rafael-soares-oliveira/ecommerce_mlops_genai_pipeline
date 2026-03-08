import logging
import os
from functools import lru_cache

import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Calcula a similaridade de cosseno entre dois vetores.

    Fórmula:
        $$\\cos(\\theta) = \\frac{\\mathbf{v_1} \\cdot \\mathbf{v_2}}{\\|\\mathbf{v_1}\\| \\|\\mathbf{v_2}\\|}$$


    Args:
        v1 (np.ndarray): O primeiro vetor.
        v2 (np.ndarray): O segundo vetor.

    Returns:
        float: O valor da similaridade de cosseno, variando de -1.0 a 1.0. Retorna 0.0 se a norma de qualquer um dos vetores for zero.
    """
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)

    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0

    return float(np.dot(v1, v2) / (norm_v1 * norm_v2))


@lru_cache(maxsize=256)
def _get_embedding_cached(model: SentenceTransformer, text: str) -> np.ndarray:
    """Função pura e global para cachear embeddings. O cache é vinculado aos argumentos, não à instância da classe."""
    return np.array(model.encode(text, convert_to_numpy=True), dtype=np.float32)


class InMemorySemanticRouter:
    """
    Carrega arquivos YAML, vetoriza seus resumos e mantém na RAM (Zero-I/O).

    Ideal para ser instanciado com @st.cache_resource no Streamlit para recuperação rápida de contexto em aplicações de NLP.
    """

    def __init__(
        self,
        yaml_dir: str,
        model_name: str = "all-MiniLM-L6-v2",
        rag_model: str = "qwen2.5-coder:3b",
    ):
        """
        Inicializa o roteador e carrega os documentos na memória.

        Args:
            yaml_dir (str): Caminho para o diretório contendo os arquivos .yml ou .yaml.
            model_name (str, optional): Nome do modelo SentenceTransformer a ser utilizado. O padrão é 'all-MiniLM-L6-v2'.
            rag_model (str, optional): Nome do modelo RAG a ser utilizado. O padrão é 'qwen2.5-coder:3b'
        """
        self.yaml_dir = yaml_dir
        self.model_name = model_name
        self.embedder = SentenceTransformer(model_name)
        self.rag_model = rag_model

        self.contexts: list[dict[str, str]] = []
        self.embeddings: np.ndarray | None = None
        self._context_cache = {}

        self._load_and_embed()

    def _load_and_embed(self) -> None:
        """
        Lê os arquivos YAMLs do disco, extrai o conteúdo e gera os embeddings na inicialização.

        Tenta extrair o valor da chave 'description' do YAML para vetorizar.
        Caso a chave não exista ou o YAML seja inválido, vetoriza o texto completo do arquivo.
        """
        if not os.path.exists(self.yaml_dir):
            error_msg = f"Diretório de YAMLs não encontrado: {self.yaml_dir}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        yaml_files = [
            f for f in os.listdir(self.yaml_dir) if f.endswith((".yml", ".yaml"))
        ]

        if not yaml_files:
            logger.warning(f"No YAML files found in {self.yaml_dir}")
            return

        texts_to_embed = []

        for filename in yaml_files:
            filepath = os.path.join(self.yaml_dir, filename)

            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()

                    # Extrai 'description' para vetorizar ou usa todo o texto
                    try:
                        parsed = yaml.safe_load(content)
                        text_to_embed = parsed.get("description", content)
                    except Exception:
                        text_to_embed = content

                    self.contexts.append(
                        {
                            "table_name": filename.replace(".yaml", "").replace(
                                ".yml", ""
                            ),
                            "content": content,
                        }
                    )
                    texts_to_embed.append(text_to_embed)

            except Exception as e:
                logger.warning(f"Falhou ao carregar {filename}: {e}")
                continue

        # Incorpora todas as descrições em batch de uma só vez
        if texts_to_embed:
            logger.info(f"Batch embedding {len(texts_to_embed)} arquivos YAML...")
            embeddings_list = self.embedder.encode(
                texts_to_embed, convert_to_numpy=True, show_progress_bar=False
            )
            self.embeddings = np.array(embeddings_list, dtype=np.float32)

            logger.info(f"Foram carregados {len(self.contexts)} Schemas/YAMLs na RAM.")

    def _cached_encode(self, text: str) -> np.ndarray:
        """
        Chama a função global com cache LRU.

        Args:
            text (str): Texto para codificar.

        Returns:
            np.ndarray: Embedding Vector
        """
        return _get_embedding_cached(self.embedder, text)

    def retrieve_context(
        self, question: str, top_k: int = 2, min_similarity: float = 0.0
    ) -> str:
        """
        Recupera os contextos YAMLs mais semanticamente relevantes a pergunta.

        Args:
            question (str): A pergunta de busca utilizada para comparar com os resumos.
            top_k (int, optional): Quantidade máxima de contextos a retornar. O padrão é 2.
            min_similarity (float): Similaridade mínima. Padrão 0.0.

        Returns:
            str: Uma string única contendo os blocos de texto dos YAMLs mais relevantes, separados por cabeçalhos com os nomes das tabelas.
        """
        if self.embeddings is None or len(self.embeddings) == 0:
            logger.warning("Nenhum contexto carregado no Semantic Router.")
            return "Nenhum contexto de tabela disponível."

        query_vec = self._cached_encode(question)

        # Calcula similaridade de forma vetorizada com numpy
        similarities = np.dot(self.embeddings, query_vec) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec)
        )

        # Obtém os índices dos top_k mais relevantes
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        # Filtra pela similaridade mínima
        blocks = []
        for idx in top_indices:
            if similarities[idx] < min_similarity:
                continue

            table = self.contexts[idx]["table_name"]
            yaml_data = self.contexts[idx]["content"]
            sim_score = float(similarities[idx])

            blocks.append(
                f"--- Tabela: {table} (Relevância: {sim_score:.2f}) ---\n{yaml_data}"
            )

        result = "\n\n".join(blocks)

        logger.debug(
            f"Retornado {len(blocks)} contextos | Top similaridade: {similarities[top_indices[0]]:.3f}"
        )

        return result if blocks else "Nenhum contexto relevante encontrado."

    def retrieve_context_batch(
        self, questions: list[str], top_k: int = 2, min_similarity: float = 0.0
    ) -> list[str]:
        """
        Retorna contexto para múltiplas questões em lote (vetorizada).

        Args:
            questions (list[str]): Lista de queries.
            top_k (int): Número de contextos por questão.
            min_similarity (float): Similaridade mínima. Padrão 0.0.

        Returns:
            list[str]: Lista de blocos YAML concatenados.
        """
        if self.embeddings is None:
            return ["Nenhum contexto disponível."] * len(questions)

        # Codificar em lote todas as questões
        query_vecs = np.stack([self._cached_encode(q) for q in questions])

        results = []
        # Normalização para similaridade de cosseno em lote
        norm_embeddings = self.embeddings / np.linalg.norm(
            self.embeddings, axis=1, keepdims=True
        )
        norm_queries = query_vecs / np.linalg.norm(query_vecs, axis=1, keepdims=True)

        # Matriz de similaridade: (num_queries x num_contexts)
        all_similarities = np.dot(norm_queries, norm_embeddings.T)
        for similarities in all_similarities:
            top_indices = np.argsort(similarities)[-top_k:][::-1]

            blocks = []
            for idx in top_indices:
                if similarities[idx] < min_similarity:
                    continue

                table = self.contexts[idx]["table_name"]
                yaml_data = self.contexts[idx]["content"]
                blocks.append(f"--- Table: {table} ---\n{yaml_data}")

            results.append(
                "\n\n".join(blocks) if blocks else "Nenhum contexto encontrado."
            )

        return results

    def get_all_contexts(self) -> str:
        """
        Carrega todos os contextos concatenados.

        Returns:
            str: Todos os blocos YAML concatenados.
        """
        blocks = [
            f"--- Table: {ctx['table_name']} ---\n{ctx['content']}"
            for ctx in self.contexts
        ]
        return "\n\n".join(blocks)

    def get_stats(self) -> dict:
        """Extraí as estatísticas do Router para monitoramento."""
        return {
            "num_contexts": len(self.contexts),
            "embedding_shape": self.embeddings.shape
            if self.embeddings is not None
            else None,
            "model": self.model_name,
            "rag_model": self.rag_model,
            "cache_size": _get_embedding_cached.cache_info().currsize,
            "cache_hits": _get_embedding_cached.cache_info().hits,
        }
