import asyncio

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from asistente_ia.config import settings
from asistente_ia.grafo import crear_grafo
from asistente_ia.memoria import abrir_memoria
from tests.llm_falso import LLMFalso


def test_sin_database_url_la_memoria_va_a_la_ram(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "")
    memoria = asyncio.run(abrir_memoria())
    assert isinstance(memoria, InMemorySaver)


def test_el_grafo_guarda_la_conversacion_en_la_memoria_que_le_pasan():
    memoria = InMemorySaver()
    modelo_falso = LLMFalso([AIMessage(content="Hola.")])
    grafo = crear_grafo(modelo_falso, [], memoria=memoria)

    configuracion = {"configurable": {"thread_id": "test-memoria"}}
    asyncio.run(grafo.ainvoke({"pregunta": "Hola"}, configuracion))

    guardado = memoria.get(configuracion)
    assert guardado is not None
    assert guardado["channel_values"]["respuesta"] == "Hola."
