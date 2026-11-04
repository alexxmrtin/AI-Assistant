import asyncio

from langchain_core.messages import AIMessage

from asistente_ia.grafo import INSTRUCCIONES_DE_PROPUESTA, crear_grafo
from tests.llm_falso import LLMFalso


def preguntar(modelo_falso, pregunta):
    grafo = crear_grafo(modelo_falso, [])
    configuracion = {"configurable": {"thread_id": "test-route"}}
    return asyncio.run(grafo.ainvoke({"pregunta": pregunta}, configuracion))


def test_una_accion_va_a_propose_y_no_al_agente():
    modelo_falso = LLMFalso([AIMessage(content="¿A quién se lo envío?")], ["accion"])

    estado_final = preguntar(modelo_falso, "Responde a Laura que el viernes me va bien")

    # El modelo solo recibe una llamada, y es la de propose (lleva sus instrucciones)
    assert estado_final["intencion"] == "accion"
    assert len(modelo_falso.conversaciones_recibidas) == 1
    instrucciones = modelo_falso.conversaciones_recibidas[0][0].content
    assert INSTRUCCIONES_DE_PROPUESTA in instrucciones


def test_una_consulta_va_al_agente():
    modelo_falso = LLMFalso([AIMessage(content="El jueves tienes gimnasio.")], ["consulta"])

    estado_final = preguntar(modelo_falso, "¿Qué tengo el jueves?")

    assert estado_final["intencion"] == "consulta"
    assert estado_final["respuesta"] == "El jueves tienes gimnasio."


def test_accion_con_tilde_tambien_cuenta():
    modelo_falso = LLMFalso([AIMessage(content="¿Qué evento?")], ["Acción"])
    estado_final = preguntar(modelo_falso, "Borra el dentista")
    assert estado_final["intencion"] == "accion"


def test_una_intencion_desconocida_se_trata_como_consulta():
    modelo_falso = LLMFalso([AIMessage(content="Hola.")], ["saludo"])
    estado_final = preguntar(modelo_falso, "Hola")
    assert estado_final["intencion"] == "consulta"


def test_si_el_modelo_no_rellena_la_ficha_se_trata_como_consulta():
    modelo_falso = LLMFalso([AIMessage(content="Hola.")], [None])
    estado_final = preguntar(modelo_falso, "Hola")
    assert estado_final["intencion"] == "consulta"
