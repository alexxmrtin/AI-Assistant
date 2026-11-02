import asyncio

from asistente_ia.__main__ import main
from tests.llm_falso import LLMFalso


def test_main_saluda_y_sale(capsys, monkeypatch):
    def input_falso(texto):
        return "salir"

    def crear_llm_falso(tipo):
        return LLMFalso([])

    monkeypatch.setattr("builtins.input", input_falso)
    monkeypatch.setattr("asistente_ia.__main__.crear_llm", crear_llm_falso)

    asyncio.run(main())

    salida = capsys.readouterr().out
    assert "Asistente IA" in salida
    assert "Hasta luego" in salida
