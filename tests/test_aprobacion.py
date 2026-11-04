import asyncio

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from asistente_ia.grafo import TEXTO_ACCION_RECHAZADA, TEXTO_ESCRITURA_NO_PERMITIDA, crear_grafo
from tests.llm_falso import HerramientaFalsa, LLMFalso

CONFIGURACION = {"configurable": {"thread_id": "test-aprobacion"}}

DATOS_DEL_CORREO = {
    "para": "laura.gomez@gmail.com",
    "asunto": "Re: ¿Quedamos esta semana?",
    "texto": "¡El viernes me va genial!",
    "responder_a": "c1",
}


def propuesta_de_correo():
    # Lo que contesta el modelo en propose: una llamada a create_draft con los datos del correo
    llamada = {"name": "create_draft", "args": DATOS_DEL_CORREO, "id": "llamada-1"}
    return AIMessage(content="", tool_calls=[llamada])


def crear_herramientas():
    buscar = HerramientaFalsa("search_emails", "c1: Laura Gómez <laura.gomez@gmail.com>")
    crear_borrador = HerramientaFalsa("create_draft", "borrador-123")
    enviar_borrador = HerramientaFalsa("send_draft", "Enviado")
    return [buscar, crear_borrador, enviar_borrador]


def pedir_accion(grafo):
    return asyncio.run(grafo.ainvoke({"pregunta": "Responde a Laura que el viernes me va bien"}, CONFIGURACION))


def test_el_agente_no_recibe_las_herramientas_de_escritura():
    modelo_falso = LLMFalso([])
    crear_grafo(modelo_falso, crear_herramientas())

    # Primera llamada a bind_tools: la del agente. Segunda: la de propose
    assert modelo_falso.herramientas_recibidas[0] == ["search_emails"]
    assert modelo_falso.herramientas_recibidas[1] == ["search_emails", "create_draft"]


def test_crea_el_borrador_y_se_para_antes_de_enviarlo():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])

    estado = pedir_accion(grafo)

    propuesta = estado["__interrupt__"][0].value
    assert propuesta["herramienta"] == "create_draft"
    assert propuesta["argumentos"] == DATOS_DEL_CORREO
    assert propuesta["id_borrador"] == "borrador-123"
    assert crear_borrador.llamadas == [DATOS_DEL_CORREO]
    assert enviar_borrador.llamadas == []


def test_si_apruebas_se_envia_el_borrador():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])
    pedir_accion(grafo)

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=True), CONFIGURACION))

    assert enviar_borrador.llamadas == [{"id_borrador": "borrador-123"}]
    assert estado_final["respuesta"] == "Hecho: he enviado el correo a laura.gomez@gmail.com."


def test_si_rechazas_no_se_envia():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])
    pedir_accion(grafo)

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=False), CONFIGURACION))

    assert enviar_borrador.llamadas == []
    assert estado_final["respuesta"] == TEXTO_ACCION_RECHAZADA


def test_cualquier_cosa_que_no_sea_true_es_un_no():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])
    pedir_accion(grafo)

    asyncio.run(grafo.ainvoke(Command(resume="sí"), CONFIGURACION))

    assert enviar_borrador.llamadas == []


def test_la_conversacion_queda_cerrada_con_el_resultado():
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), crear_herramientas())
    pedir_accion(grafo)

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=False), CONFIGURACION))

    # Después de la propuesta va su resultado (ToolMessage) y la respuesta final, para que la siguiente pregunta no falle
    mensajes = estado_final["messages"]
    assert isinstance(mensajes[-2], ToolMessage)
    assert mensajes[-2].tool_call_id == "llamada-1"
    assert mensajes[-1].content == TEXTO_ACCION_RECHAZADA


def test_puede_buscar_antes_de_proponer():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    llamada_de_busqueda = {"name": "search_emails", "args": {"texto": "laura"}, "id": "llamada-0"}
    respuestas = [AIMessage(content="", tool_calls=[llamada_de_busqueda]), propuesta_de_correo()]
    grafo = crear_grafo(LLMFalso(respuestas, ["accion"]), [buscar, crear_borrador, enviar_borrador])

    estado = pedir_accion(grafo)

    assert buscar.llamadas == [{"texto": "laura"}]
    assert "__interrupt__" in estado


def test_si_no_propone_nada_contesta_con_su_texto():
    grafo = crear_grafo(LLMFalso([AIMessage(content="¿Qué le digo a Laura?")], ["accion"]), crear_herramientas())

    estado_final = pedir_accion(grafo)

    assert "__interrupt__" not in estado_final
    assert estado_final["respuesta"] == "¿Qué le digo a Laura?"


def test_el_agente_no_puede_ejecutar_herramientas_de_escritura():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    # El agente (camino de consulta) se inventa una llamada a send_draft
    llamada = {"name": "send_draft", "args": {"id_borrador": "borrador-123"}, "id": "llamada-x"}
    respuestas = [AIMessage(content="", tool_calls=[llamada]), AIMessage(content="No puedo.")]
    grafo = crear_grafo(LLMFalso(respuestas), [buscar, crear_borrador, enviar_borrador])

    estado_final = asyncio.run(grafo.ainvoke({"pregunta": "Envía el borrador"}, CONFIGURACION))

    assert enviar_borrador.llamadas == []
    assert estado_final["messages"][-2].content == TEXTO_ESCRITURA_NO_PERMITIDA


def herramientas_del_calendario():
    leer = HerramientaFalsa("get_event", '{"id": "e2", "titulo": "Dentista", "fecha": "2026-11-03", "inicio": "17:30", "fin": "18:00"}')
    borrar = HerramientaFalsa("delete_event", "Evento borrado")
    crear = HerramientaFalsa("create_event", "Evento creado: Gimnasio el 2026-11-07 de 10:00 a 11:00")
    return [leer, borrar, crear]


def proponer(nombre, argumentos):
    llamada = {"name": nombre, "args": argumentos, "id": "llamada-1"}
    return AIMessage(content="", tool_calls=[llamada])


def test_antes_de_borrar_un_evento_te_muestra_cual_es():
    leer, borrar, crear = herramientas_del_calendario()
    respuestas = [proponer("delete_event", {"id_evento": "e2"})]
    grafo = crear_grafo(LLMFalso(respuestas, ["accion"]), [leer, borrar, crear])

    estado = asyncio.run(grafo.ainvoke({"pregunta": "Borra el dentista"}, CONFIGURACION))

    propuesta = estado["__interrupt__"][0].value
    assert propuesta["evento_actual"] == "Dentista, 2026-11-03 de 17:30 a 18:00"
    assert borrar.llamadas == []


def test_si_apruebas_se_borra_el_evento():
    leer, borrar, crear = herramientas_del_calendario()
    respuestas = [proponer("delete_event", {"id_evento": "e2"})]
    grafo = crear_grafo(LLMFalso(respuestas, ["accion"]), [leer, borrar, crear])
    asyncio.run(grafo.ainvoke({"pregunta": "Borra el dentista"}, CONFIGURACION))

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=True), CONFIGURACION))

    assert borrar.llamadas == [{"id_evento": "e2"}]
    assert estado_final["respuesta"] == "Hecho. Evento borrado"


def test_un_evento_inventado_no_llega_a_la_aprobacion():
    leer = HerramientaFalsa("get_event", '{"error": "No existe ningún evento con el id e99."}')
    borrar = HerramientaFalsa("delete_event", "Evento borrado")
    respuestas = [proponer("delete_event", {"id_evento": "e99"})]
    grafo = crear_grafo(LLMFalso(respuestas, ["accion"]), [leer, borrar])

    estado_final = asyncio.run(grafo.ainvoke({"pregunta": "Borra el evento e99"}, CONFIGURACION))

    assert "__interrupt__" not in estado_final
    assert estado_final["respuesta"].startswith("No he encontrado ese evento")
    assert borrar.llamadas == []


def test_crear_un_evento_no_necesita_preparar_nada():
    leer, borrar, crear = herramientas_del_calendario()
    datos = {"titulo": "Gimnasio", "fecha": "2026-11-07", "inicio": "10:00", "fin": "11:00"}
    grafo = crear_grafo(LLMFalso([proponer("create_event", datos)], ["accion"]), [leer, borrar, crear])
    estado = asyncio.run(grafo.ainvoke({"pregunta": "Apúntame al gimnasio el sábado a las 10"}, CONFIGURACION))
    assert estado["__interrupt__"][0].value == {"herramienta": "create_event", "argumentos": datos}

    estado_final = asyncio.run(grafo.ainvoke(Command(resume=True), CONFIGURACION))

    assert crear.llamadas == [datos]
    assert estado_final["respuesta"] == "Hecho. Evento creado: Gimnasio el 2026-11-07 de 10:00 a 11:00"
