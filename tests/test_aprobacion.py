import asyncio

from langgraph.types import Command

from asistente_ia.grafo import (
    TEXTO_ACCION_RECHAZADA,
    TEXTO_PROPUESTA_NO_ENTENDIDA,
    PropuestaDeAccion,
    crear_grafo,
)
from asistente_ia.telegram_bot import TEXTO_ACCIONES_SOLO_EN_TERMINAL, crear_manejador
from tests.llm_falso import LLMFalso
from tests.test_telegram_bot import UpdateFalso

CONFIGURACION = {"configurable": {"thread_id": "test-aprobacion"}}


def pedir_accion(grafo):
    return asyncio.run(grafo.ainvoke({"pregunta": "Borra el dentista del jueves"}, CONFIGURACION))


def test_el_grafo_se_para_con_la_propuesta():
    grafo = crear_grafo(LLMFalso([], ["accion"]), [])

    estado = pedir_accion(grafo)

    assert estado["__interrupt__"][0].value == {"accion": "borrar evento", "detalles": "Dentista del jueves a las 17:00"}
    assert "respuesta" not in estado


def test_si_apruebas_se_ejecuta():
    grafo = crear_grafo(LLMFalso([], ["accion"]), [])
    pedir_accion(grafo)

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=True), CONFIGURACION))

    assert estado_final["aprobada"] is True
    assert estado_final["respuesta"].startswith("Hecho (de prueba")
    assert "__interrupt__" not in estado_final


def test_si_rechazas_no_se_ejecuta():
    grafo = crear_grafo(LLMFalso([], ["accion"]), [])
    pedir_accion(grafo)

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=False), CONFIGURACION))

    assert estado_final["aprobada"] is False
    assert estado_final["respuesta"] == TEXTO_ACCION_RECHAZADA


def test_cualquier_cosa_que_no_sea_true_es_un_no():
    grafo = crear_grafo(LLMFalso([], ["accion"]), [])
    pedir_accion(grafo)

    estado_final = asyncio.run(grafo.ainvoke(Command(resume="sí"), CONFIGURACION))

    assert estado_final["respuesta"] == TEXTO_ACCION_RECHAZADA


def test_si_no_hay_propuesta_no_pide_aprobacion():
    grafo = crear_grafo(LLMFalso([], ["accion"], [None]), [])

    estado_final = pedir_accion(grafo)

    assert "__interrupt__" not in estado_final
    assert estado_final["respuesta"] == TEXTO_PROPUESTA_NO_ENTENDIDA


def test_la_propuesta_preparada_llega_a_la_aprobacion():
    propuesta = PropuestaDeAccion(accion="enviar correo", detalles="A Laura: el viernes me va bien")
    grafo = crear_grafo(LLMFalso([], ["accion"], [propuesta]), [])

    estado = pedir_accion(grafo)

    assert estado["__interrupt__"][0].value["accion"] == "enviar correo"


def test_telegram_rechaza_las_acciones_de_momento():
    grafo = crear_grafo(LLMFalso([], ["accion"]), [])
    responder = crear_manejador(grafo, "111")

    update = UpdateFalso(111, "Borra el dentista del jueves")
    asyncio.run(responder(update, None))

    assert update.message.respuestas_enviadas == [TEXTO_ACCIONES_SOLO_EN_TERMINAL]
    # El grafo no se ha quedado parado: terminó por el camino del "no"
    estado = asyncio.run(grafo.aget_state({"configurable": {"thread_id": "111"}}))
    assert estado.values["aprobada"] is False
    assert len(estado.next) == 0
