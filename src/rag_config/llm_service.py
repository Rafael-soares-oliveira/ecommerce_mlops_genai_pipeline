import logging
import os
import re
import time
from functools import lru_cache

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# =====================================
# Configurações
# =====================================
OLLAMA_HOST_API = os.getenv("OLLAMA_HOST_API", "http://ollama:11434/api/generate")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")

# Timeouts (seconds)
TRANSLATION_TIMEOUT = int(os.getenv("TRANSLATION_TIMEOUT", "10"))
INFERENCE_TIMEOUT = int(os.getenv("INFERENCE_TIMEOUT", "60"))
SUMMARY_TIMEOUT = int(os.getenv("SUMMARY_TIMEOUT", "120"))

# =====================================
# SYSTEM PROMPTS
# =====================================
TRANSLATOR_SYSTEM_PROMPT = """You are a direct translator. Translate the following Portuguese question into English. Provide ONLY the exact English translation. No quotes, no markdown, no explanations."""

SYSTEM_PROMPT = """You are an expert Data Engineer and PostgreSQL specialist.
Your ONLY mission is to translate natural language business questions into valid, optimized, and secure SQL queries.

CRITICAL RULES:
1. Output ONLY the valid SQL code inside a ```sql ``` block. No explanations, no greetings.
2. NEVER hallucinate tables or columns, check the context files.
3. MANDATORY: ALWAYS use fully qualified table names with their schemas. NEVER use just the table name.
4. CRITICAL: PyArrow crashes with Decimal types. You MUST cast any AVG(), SUM(), or division results to ::FLOAT (e.g., AVG(net_revenue)::FLOAT). NEVER output raw NUMERIC or DECIMAL.
5. Optimize for performance: use appropriate indexes, limit result sets when possible, avoid full table scans.
6. NEVER guess join columns. You MUST use ONLY the exact column names explicitly provided in the table schemas for your JOIN ON conditions.
"""

SUMMARY_SYSTEM_PROMPT = """Act as a senior data analyst. Analyze the e-commerce data provided below, representing yesterday's and the day before's sales performance, and generate a concise Executive Summary by country, with conclusion and recommendation, following these guidelines:
    1. IMPORTANT: Answer entirely in Brazilian Portuguese.
    2. Performance Highlights: Compare GMV and Net Revenue (net_revenue) values between the two days. Indicate whether there was percentage growth or decline.
    3. Financial Health: Analyze Realistic Gross Profit (gross_profit_realistic) and the impact of Logistics Loss (logistc_loss).
    4. Operational Efficiency: Evaluate cancellation rates (cancellation_rate) and return rates (returns_rate). Identify if any country has unusual metrics.
    5. Actionable Insights: Point out the main opportunity or the most critical risk observed in the comparison of these two days.
"""


# =====================================
# LLM REQUEST
# =====================================
class LLMRequestConfig:
    """Configuration for different types of LLM requests."""

    TRANSLATION = {
        "temperature": 0.0,
        "num_ctx": 512,
        "top_p": 0.1,
        "repeat_penalty": 1.0,
    }

    INFERENCE = {
        "temperature": 0.0,
        "num_ctx": 4096,
        "top_p": 0.1,
        "repeat_penalty": 1.15,
    }

    SUMMARY = {
        "temperature": 0.3,
        "num_ctx": 2048,
        "top_p": 0.1,
        "repeat_penalty": 1.1,
    }


def extract_sql(raw_output: str) -> str:
    """
    Extrai a query SQL do bloco de formatação Markdown gerado pelo LLM.

    Args:
        raw_output (str): Texto bruto retornado pelo modelo.

    Returns:
        str: A query SQL limpa, ou o texto original.
    """
    sql_match = re.search(
        r"```sql\s*(.*?)\s*```", raw_output, re.DOTALL | re.IGNORECASE
    )
    if sql_match:
        sql = sql_match.group(1).strip()
        logger.debug(f"Extracted SQL: {len(sql)} chars")
        return sql

    logger.warning("Bloco SQL não encontrado. Retornando saída bruta.")
    return raw_output.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
    ),
    reraise=True,
)
def _run_inference(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
    config: dict | None = None,
    timeout: int = INFERENCE_TIMEOUT,
    extract_sql_block: bool = False,
) -> str:
    """
    Método interno para centralizar as chamadas ao Ollama.

    Args:
        prompt (str): Prompt de usuário formatado.
        system_prompt (str): System Context.
        config (dict): Configuração da requisição.
        timeout (int): Timeout da requisição.

    Returns:
        str: Resposta da LLM.

    Raises:
        RuntimeError: Se a comunicação com LLM falhar.
    """
    if config is None:
        config = LLMRequestConfig.INFERENCE

    payload = {
        "model": MODEL_NAME,
        "system": system_prompt,
        "prompt": prompt,
        "stream": False,
        "options": config,
    }

    start_time = time.time()
    logger.info(f"Iniciando inferência (timeout configurado: {timeout}s)...")

    response = requests.post(OLLAMA_HOST_API, json=payload, timeout=timeout)
    response.raise_for_status()

    try:
        raw_response = response.json().get("response", "")
    except ValueError as e:
        raise RuntimeError("Falha ao decodificar JSON da resposta da LLM.") from e

    latency = time.time() - start_time

    if extract_sql_block:
        result = extract_sql(raw_response)
    else:
        result = raw_response.strip()

    logger.info(f"Inferência concluída em {latency:.2f}s ({len(result)} caracteres.")
    return result


@lru_cache(maxsize=64)
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
    ),
    reraise=True,
)
def translate_to_english(question: str) -> str:
    """
    Traduz a pergunta do usuário para inglês via modelo RAG.

    Args:
        question (str): Questão em português.

    Returns:
        str: English translation or original if translation fails.
    """
    payload = {
        "model": MODEL_NAME,
        "system": TRANSLATOR_SYSTEM_PROMPT,
        "prompt": question,
        "stream": False,
        "options": LLMRequestConfig.TRANSLATION,
    }

    # O parâmetro 'json=' já define o Header e faz o dumps automaticamente
    response = requests.post(OLLAMA_HOST_API, json=payload, timeout=TRANSLATION_TIMEOUT)

    # Garante que erros 4xx ou 5xx lancem uma exceção
    response.raise_for_status()

    result = response.json().get("response", "").strip()
    logger.debug(f"Traduzido: {question[:30]}... -> {result[:30]}...")
    return result


def generate_sql_from_prompt(question: str, context_str: str) -> str:
    """
    Gera SQL de uma pergunta em linguagem natural.

    Args:
        question (str): Pergunta em linguagem natural.
        context_str (str): Contexto das tabelas.

    Returns:
        str: Consulta SQL gerada.

    Raises:
        RuntimeError: Se falhar
    """
    prompt = f"Database Context:\n{context_str}\n\nUser Question:\n{question}"

    return _run_inference(
        prompt,
        system_prompt=SYSTEM_PROMPT,
        config=LLMRequestConfig.INFERENCE,
        timeout=INFERENCE_TIMEOUT,
        extract_sql_block=True,
    )


def fix_sql_error(
    question: str, invalid_sql: str, error_msg: str, context_str: str
) -> str:
    """
    Envia o erro SQL de volta ao LLM para autocorreção.

    Args:
        question (str): Pergunta original.
        invalid_sql (str): Query que gerou o erro.
        error_msg (str): Mensagem de erro retornada pelo banco.
        context_str (str): Contexto das tabelas.

    Returns:
        str: Nova consulta SQL corrigida.

    Raises:
        RuntimeError: Se a correção falhar
    """
    prompt = f"""
    Database Context:
    {context_str}

    The query you generated for the question "{question}" failed with the following error in PostgreSQL:
    {error_msg}

    Invalid Query:
    {invalid_sql}

    Correct the error and return ONLY the corrected SQL query within the ```sql``` block.
    """

    return _run_inference(
        prompt,
        system_prompt=SYSTEM_PROMPT,
        config=LLMRequestConfig.INFERENCE,
        timeout=INFERENCE_TIMEOUT,
        extract_sql_block=True,
    )


def generate_executive_summary(data_string: str) -> str:
    """
    Gera um resumo textual em linguagem natural a partir de dados tabulares (Data-to-Text).

    Args:
        data_string (str): Data tabular como string.

    Returns:
        str: Resumo em linguagem natural.

    Raises:
        RuntimeError: Se a geração falhar.
    """
    prompt = f"Analyze the following data and generate an executive summary.:\n\n{data_string}"

    return _run_inference(
        prompt,
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        config=LLMRequestConfig.SUMMARY,
        timeout=SUMMARY_TIMEOUT,
        extract_sql_block=False,
    )


def batch_translate(questions: list[str]) -> list[str]:
    """
    Traduz múltiplas questões. Usa cache para questões repetidas.

    Args:
        questions (list[str]): Questões para traduzir.

    Returns:
        list[str]: Questões traduzidas.
    """
    return [translate_to_english(q) for q in questions]


# ============================
# Monitoramento do LLM
# ============================
def get_llm_stats() -> dict:
    """Extraí estatísticas do serviço LLM."""
    cache_info = translate_to_english.cache_info()
    return {
        "model": MODEL_NAME,
        "endpoint": OLLAMA_HOST_API,
        "translation_cache_hits": cache_info.hits,
        "translation_cache_misses": cache_info.misses,
        "translation_cache_size": cache_info.currsize,
    }
