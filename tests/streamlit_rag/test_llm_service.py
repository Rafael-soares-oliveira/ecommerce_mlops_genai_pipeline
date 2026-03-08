from unittest.mock import MagicMock

import pytest
import requests
from pytest_mock import MockerFixture

from rag_config.llm_service import (
    LLMRequestConfig,
    _run_inference,
    batch_translate,
    extract_sql,
    fix_sql_error,
    generate_executive_summary,
    generate_sql_from_prompt,
    get_llm_stats,
    translate_to_english,
)


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Limpa o cache LRU da função de tradução antes de cada teste."""
    translate_to_english.cache_clear()


@pytest.fixture
def mock_successful_response(mocker: MockerFixture) -> MagicMock:
    """Mock genérico para uma resposta de sucesso do requests.post."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = {"response": "mocked_response"}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ==========================================
# Testes para extract_sql
# ==========================================
def test_extract_sql_success() -> None:
    """Testa a extração correta de um bloco de código SQL via Regex."""
    raw_output = (
        "Aqui está a query solicitada:\n```sql\nSELECT * FROM users;\n```\nBoa sorte!"
    )
    expected = "SELECT * FROM users;"

    assert extract_sql(raw_output) == expected


def test_extract_sql_case_insensitive() -> None:
    """Testa se a extração ignora case do marcador ```SQL."""
    raw_output = "```SQL\nSELECT 1;\n```"
    expected = "SELECT 1;"

    assert extract_sql(raw_output) == expected


def test_extract_sql_no_block() -> None:
    """Testa o comportamento quando o modelo não retorna um bloco markdown."""
    raw_output = "SELECT id FROM tabela"

    # Sem bloco markdown, deve retornar o texto original limpo (strip)
    assert extract_sql(raw_output) == "SELECT id FROM tabela"


# ==========================================
# Testes para _run_inference
# ==========================================
def test_run_inference_success(
    mocker: MockerFixture, mock_successful_response: MagicMock
) -> None:
    """Testa a execução normal de inferência."""
    mock_post = mocker.patch(
        "rag_config.llm_service.requests.post", return_value=mock_successful_response
    )

    result = _run_inference("Teste prompt", extract_sql_block=False)

    assert result == "mocked_response"
    mock_post.assert_called_once()

    # Verifica parâmetros da requisição
    called_args, called_kwargs = mock_post.call_args
    payload = called_kwargs["json"]
    assert payload["prompt"] == "Teste prompt"
    assert "system" in payload
    assert "options" in payload


def test_run_inference_with_sql_extraction(mocker: MockerFixture) -> None:
    """Testa inferência forçando a extração de SQL."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = {"response": "```sql\nSELECT *;\n```"}
    mock_resp.raise_for_status.return_value = None
    mocker.patch("rag_config.llm_service.requests.post", return_value=mock_resp)

    result = _run_inference("prompt", extract_sql_block=True)

    assert result == "SELECT *;"


def test_run_inference_json_decode_error(mocker: MockerFixture) -> None:
    """Testa erro de fallback ao decodificar JSON quebrado."""
    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    mocker.patch("rag_config.llm_service.requests.post", return_value=mock_resp)

    with pytest.raises(
        RuntimeError, match="Falha ao decodificar JSON da resposta da LLM."
    ):
        _run_inference("prompt")


def test_run_inference_retry_on_timeout(mocker: MockerFixture) -> None:
    """Testa se o tenacity está aplicando retries corretamente para Timeouts."""
    mocker.patch("time.sleep")  # Previne lentidão real durante os testes

    # Configura o post para lançar Timeout em todas as tentativas
    mock_post = mocker.patch(
        "rag_config.llm_service.requests.post",
        side_effect=requests.exceptions.Timeout("Connection timed out"),
    )

    # Com reraise=True no decorador, a exceção original é repassada após esgotar as tentativas
    with pytest.raises(requests.exceptions.Timeout, match="Connection timed out"):
        _run_inference("prompt")

    assert mock_post.call_count == 3


# ==========================================
# Testes para translate_to_english
# ==========================================
def test_translate_to_english_success_and_cache(
    mocker: MockerFixture, mock_successful_response: MagicMock
) -> None:
    """Testa a tradução e a eficiência do lru_cache."""
    mock_post = mocker.patch(
        "rag_config.llm_service.requests.post", return_value=mock_successful_response
    )

    # Chamada 1
    res1 = translate_to_english("Qual o lucro?")
    # Chamada 2 (Idêntica)
    res2 = translate_to_english("Qual o lucro?")

    assert res1 == "mocked_response"
    assert res2 == "mocked_response"

    # A requisição POST real só deve acontecer uma vez graças ao lru_cache
    mock_post.assert_called_once()


def test_translate_to_english_http_error(mocker: MockerFixture) -> None:
    """Testa comportamento perante erro HTTP explícito (ex: 404/500)."""
    mocker.patch("time.sleep")
    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )
    mocker.patch("rag_config.llm_service.requests.post", return_value=mock_resp)

    # Erros HTTP (diferente de Timeout/Connection) não disparam retry por padrão neste decorador
    with pytest.raises(requests.exceptions.HTTPError):
        translate_to_english("Qual a receita?")


# ==========================================
# Testes para Wrappers de LLM
# ==========================================
def test_generate_sql_from_prompt(mocker: MockerFixture) -> None:
    """Testa a geração de SQL com injeção de contexto."""
    mock_inference = mocker.patch(
        "rag_config.llm_service._run_inference", return_value="SELECT 1"
    )

    result = generate_sql_from_prompt(
        question="Minha pergunta", context_str="Schema info"
    )

    assert result == "SELECT 1"
    mock_inference.assert_called_once()

    # Verifica se os argumentos passados para _run_inference estão corretos
    args, kwargs = mock_inference.call_args
    prompt_sent = args[0]

    assert "Schema info" in prompt_sent
    assert "Minha pergunta" in prompt_sent
    assert kwargs["extract_sql_block"] is True
    assert kwargs["config"] == LLMRequestConfig.INFERENCE


def test_fix_sql_error(mocker: MockerFixture) -> None:
    """Testa a montagem de prompt para autocorreção do LLM."""
    mock_inference = mocker.patch(
        "rag_config.llm_service._run_inference", return_value="SELECT CORRIGIDO"
    )

    result = fix_sql_error(
        question="q",
        invalid_sql="SELECT ERRO",
        error_msg="Syntax Error",
        context_str="ctx",
    )

    assert result == "SELECT CORRIGIDO"
    args, _ = mock_inference.call_args
    prompt_sent = args[0]

    assert "Syntax Error" in prompt_sent
    assert "SELECT ERRO" in prompt_sent
    assert "ctx" in prompt_sent


def test_generate_executive_summary(mocker: MockerFixture) -> None:
    """Testa a geração de summary sem extração SQL."""
    mock_inference = mocker.patch(
        "rag_config.llm_service._run_inference", return_value="Resumo executivo"
    )

    result = generate_executive_summary("Dados: 123")

    assert result == "Resumo executivo"
    mock_inference.assert_called_once()

    args, kwargs = mock_inference.call_args
    assert "Dados: 123" in args[0]
    assert kwargs["extract_sql_block"] is False
    assert kwargs["config"] == LLMRequestConfig.SUMMARY


# ==========================================
# Testes Diversos (Batch e Stats)
# ==========================================
def test_batch_translate(mocker: MockerFixture) -> None:
    """Testa a tradução em lote chamando a função base iterativamente."""
    mocker.patch(
        "rag_config.llm_service.translate_to_english",
        side_effect=["Trans 1", "Trans 2"],
    )

    result = batch_translate(["Pergunta 1", "Pergunta 2"])

    assert result == ["Trans 1", "Trans 2"]
    assert len(result) == 2


def test_get_llm_stats(
    mocker: MockerFixture, mock_successful_response: MagicMock
) -> None:
    """Testa a obtenção das estatísticas e estado do cache."""
    # Preenche o cache com 1 miss e 1 hit
    mock_post = mocker.patch(
        "rag_config.llm_service.requests.post", return_value=mock_successful_response
    )

    translate_to_english("Nova pergunta")  # Miss (faz a requisição)
    translate_to_english("Nova pergunta")  # Hit (usa o cache)

    # Verifica se a requisição real foi feita apenas uma vez
    mock_post.assert_called_once()

    stats = get_llm_stats()

    assert "model" in stats
    assert "endpoint" in stats
    assert stats["translation_cache_hits"] >= 1
    assert stats["translation_cache_misses"] >= 1
    assert stats["translation_cache_size"] >= 1
