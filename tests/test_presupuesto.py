import asyncio

from langchain_core.messages import AIMessage

from asistente_ia.grafo import INSTRUCCIONES_DE_RESUMEN, crear_grafo
from tests.llm_falso import HerramientaFalsa, LLMFalso

CONFIGURACION = {"configurable": {"thread_id": "test-presupuesto"}}


def preguntar(grafo, pregunta):
    return asyncio.run(grafo.ainvoke({"pregunta": pregunta}, CONFIGURACION))


def test_una_conversacion_corta_no_se_resume():
    modelo_falso = LLMFalso([AIMessage("Hola")])
    grafo = crear_grafo(modelo_falso, [])

    estado = preguntar(grafo, "Hola")

    # Solo una llamada al modelo, la del agente. Ningún resumen
    assert len(modelo_falso.conversaciones_recibidas) == 1
    assert "resumen" not in estado


def test_una_conversacion_larga_resume_lo_antiguo():
    # La primera pregunta usa una herramienta, para comprobar que su petición y su resultado se resumen juntos
    llamada = {"name": "list_events", "args": {"fecha_inicio": "2026-11-05", "fecha_fin": "2026-11-05"}, "id": "llamada-1"}
    respuestas = [
        AIMessage(content="", tool_calls=[llamada]),
        AIMessage("El jueves tienes dentista a las 10:00."),
        AIMessage("Respuesta 2"),
        AIMessage("Respuesta 3"),
        AIMessage("La persona preguntó por el jueves y tiene dentista a las 10:00."),  # el resumen
        AIMessage("Respuesta 4"),
    ]
    modelo_falso = LLMFalso(respuestas)
    agenda = HerramientaFalsa("list_events", "Dentista, 2026-11-05 de 10:00 a 11:00")

    # Un presupuesto muy pequeño para que se pase enseguida
    grafo = crear_grafo(modelo_falso, [agenda], presupuesto_de_tokens=50)

    preguntar(grafo, "¿Qué tengo el jueves?")
    preguntar(grafo, "Pregunta 2")
    preguntar(grafo, "Pregunta 3")
    estado = preguntar(grafo, "Pregunta 4")

    # La llamada del resumen es la penúltima, recibe las instrucciones de resumen y la parte antigua como texto
    llamada_del_resumen = modelo_falso.conversaciones_recibidas[-2]
    assert llamada_del_resumen[0].content == INSTRUCCIONES_DE_RESUMEN
    assert "Persona, ¿Qué tengo el jueves?" in llamada_del_resumen[1].content
    assert "Resultado de la herramienta, Dentista" in llamada_del_resumen[1].content
    assert "Pregunta 2" not in llamada_del_resumen[1].content

    # La parte antigua ya no está en el estado, la conversación empieza en la pregunta 2
    assert estado["resumen"] == "La persona preguntó por el jueves y tiene dentista a las 10:00."
    assert estado["messages"][0].content == "Pregunta 2"
    assert len(estado["messages"]) == 6

    # El agente recibe el resumen dentro de las instrucciones del sistema
    llamada_del_agente = modelo_falso.conversaciones_recibidas[-1]
    assert "tiene dentista a las 10:00" in llamada_del_agente[0].content
    assert llamada_del_agente[1].content == "Pregunta 2"


def test_el_resumen_nuevo_incluye_el_anterior():
    respuestas = [
        AIMessage("Respuesta 1"),
        AIMessage("Respuesta 2"),
        AIMessage("Respuesta 3"),
        AIMessage("Resumen A"),
        AIMessage("Respuesta 4"),
        AIMessage("Resumen B"),
        AIMessage("Respuesta 5"),
    ]
    modelo_falso = LLMFalso(respuestas)
    grafo = crear_grafo(modelo_falso, [], presupuesto_de_tokens=20)

    for numero in range(1, 6):
        estado = preguntar(grafo, "Pregunta " + str(numero))

    # Al resumir por segunda vez, el texto empieza por el resumen anterior y solo añade la pregunta 2
    llamada_del_resumen = modelo_falso.conversaciones_recibidas[-2]
    assert llamada_del_resumen[1].content.startswith("Resumen anterior, Resumen A")
    assert "Pregunta 2" in llamada_del_resumen[1].content
    assert "Pregunta 1" not in llamada_del_resumen[1].content
    assert estado["resumen"] == "Resumen B"
    assert estado["messages"][0].content == "Pregunta 3"
