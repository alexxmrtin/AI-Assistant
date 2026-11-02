import asyncio
from datetime import date

from langchain_core.messages import AIMessage, ToolMessage

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.grafo import crear_grafo, crear_instrucciones
from tests.llm_falso import LLMFalso

CONFIGURACION = {"configurable": {"thread_id": "test"}}

HERRAMIENTAS = asyncio.run(cargar_herramientas_mcp())


def test_el_modelo_pide_la_herramienta_y_despues_responde(monkeypatch):
    monkeypatch.setitem(SERVIDORES["calendar"], "env", {"CALENDAR_BACKEND": "demo"})
    herramientas = asyncio.run(cargar_herramientas_mcp())

    peticion_de_herramienta = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "list_events",
                "args": {"fecha_inicio": "2026-11-05", "fecha_fin": "2026-11-05"},
                "id": "llamada_1",
            }
        ],
    )
    respuesta_final = AIMessage(content="El jueves tienes la reunión del TFG y gimnasio.")
    modelo_falso = LLMFalso([peticion_de_herramienta, respuesta_final])

    grafo = crear_grafo(modelo_falso, herramientas)
    tarea_pendiente = grafo.ainvoke({"pregunta": "¿Qué tengo el jueves?"}, CONFIGURACION)
    estado_final = asyncio.run(tarea_pendiente)

    assert estado_final["respuesta"] == "El jueves tienes la reunión del TFG y gimnasio."

    segunda_conversacion = modelo_falso.conversaciones_recibidas[1]
    assert len(segunda_conversacion) == 4
    assert isinstance(segunda_conversacion[3], ToolMessage)
    assert "Reunión del TFG" in str(segunda_conversacion[3].content)


def test_si_no_pide_herramientas_responde_directamente():
    respuesta_directa = AIMessage(content="Python es un lenguaje de programación.")
    modelo_falso = LLMFalso([respuesta_directa])

    grafo = crear_grafo(modelo_falso, HERRAMIENTAS)
    tarea_pendiente = grafo.ainvoke({"pregunta": "¿Qué es Python?"}, CONFIGURACION)
    estado_final = asyncio.run(tarea_pendiente)

    assert estado_final["respuesta"] == "Python es un lenguaje de programación."
    assert len(modelo_falso.conversaciones_recibidas) == 1


def test_el_grafo_recuerda_la_conversacion():
    modelo_falso = LLMFalso(
        [
            AIMessage(content="Me llamo Asistente IA."),
            AIMessage(content="Me has preguntado cómo me llamo."),
        ]
    )
    grafo = crear_grafo(modelo_falso, HERRAMIENTAS)

    primera = grafo.ainvoke({"pregunta": "¿Cómo te llamas?"}, CONFIGURACION)
    asyncio.run(primera)
    segunda = grafo.ainvoke({"pregunta": "¿Qué te he preguntado antes?"}, CONFIGURACION)
    asyncio.run(segunda)

    segunda_conversacion = modelo_falso.conversaciones_recibidas[1]
    assert len(segunda_conversacion) == 4
    assert segunda_conversacion[1].content == "¿Cómo te llamas?"


def test_las_instrucciones_llevan_la_fecha():
    instrucciones = crear_instrucciones(date(2026, 11, 5))
    assert "jueves 5 de noviembre de 2026" in instrucciones
    assert "2026-11-05" in instrucciones


def test_con_fecha_fija_el_modelo_recibe_esa_fecha():
    modelo_falso = LLMFalso([AIMessage(content="Hoy es lunes.")])
    grafo = crear_grafo(modelo_falso, HERRAMIENTAS, date(2026, 11, 2))

    tarea_pendiente = grafo.ainvoke({"pregunta": "¿Qué día es hoy?"}, CONFIGURACION)
    asyncio.run(tarea_pendiente)

    instrucciones_recibidas = modelo_falso.conversaciones_recibidas[0][0].content
    assert "lunes 2 de noviembre de 2026" in instrucciones_recibidas
