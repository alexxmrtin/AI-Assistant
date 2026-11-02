import pytest

from asistente_ia.config import Settings
from asistente_ia.llm import crear_llm, nombre_modelo


def test_modelo_por_defecto_segun_proveedor():
    settings = Settings(_env_file=None, llm_provider="ollama")
    assert nombre_modelo("fast", settings) == "qwen3:8b"


def test_la_variable_de_entorno_manda_sobre_el_defecto():
    settings = Settings(_env_file=None, llm_provider="ollama", llm_model_fast="llama3.1:8b")
    assert nombre_modelo("fast", settings) == "llama3.1:8b"


def test_proveedor_desconocido_da_error():
    settings = Settings(_env_file=None, llm_provider="openai")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        crear_llm("fast", settings)


def test_crea_el_modelo_del_proveedor_elegido():
    settings = Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key="sk-falsa")
    assert type(crear_llm("fast", settings)).__name__ == "ChatAnthropic"
