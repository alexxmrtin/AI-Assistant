import asyncio

from langchain_core.messages import AIMessage, ToolMessage

from asistente_ia.grafo import crear_grafo
from asistente_ia.telegram_bot import (
    TEXTO_PROPUESTA_CADUCADA,
    crear_manejador,
    crear_manejador_de_botones,
)
from tests.llm_falso import LLMFalso
from tests.test_aprobacion import crear_herramientas, propuesta_de_correo


class UsuarioFalso:
    def __init__(self, id_usuario):
        self.id = id_usuario


class ChatFalso:
    def __init__(self, id_chat):
        self.id = id_chat


class MensajeFalso:
    def __init__(self, texto):
        self.text = texto
        self.respuestas_enviadas = []

        self.teclados_enviados = []

    async def reply_text(self, texto, reply_markup=None):
        self.respuestas_enviadas.append(texto)
        self.teclados_enviados.append(reply_markup)


class UpdateFalso:
    def __init__(self, id_usuario, texto):
        self.effective_user = UsuarioFalso(id_usuario)
        self.effective_chat = ChatFalso(id_usuario)
        self.message = MensajeFalso(texto)


class BotonFalso:
    # Imita la pulsación de un botón (callback_query). message es el mensaje que llevaba los botones
    def __init__(self, datos, mensaje):
        self.data = datos
        self.message = mensaje
        self.contestado = False
        self.botones_quitados = False

    async def answer(self):
        self.contestado = True

    async def edit_message_reply_markup(self, reply_markup=None):
        self.botones_quitados = True


class UpdateDeBotonFalso:
    def __init__(self, id_usuario, datos, mensaje):
        self.effective_user = UsuarioFalso(id_usuario)
        self.effective_chat = ChatFalso(111)
        self.callback_query = BotonFalso(datos, mensaje)


def test_responde_al_usuario_permitido():
    modelo_falso = LLMFalso([AIMessage(content="Hola, Alejandro.")])
    grafo = crear_grafo(modelo_falso, [])
    responder = crear_manejador(grafo, "111")

    update = UpdateFalso(111, "Hola")
    asyncio.run(responder(update, None))

    assert update.message.respuestas_enviadas == ["Hola, Alejandro."]


def test_ignora_a_otros_usuarios():
    modelo_falso = LLMFalso([AIMessage(content="No debería llegar aquí.")])
    grafo = crear_grafo(modelo_falso, [])
    responder = crear_manejador(grafo, "111")

    update = UpdateFalso(999, "Dime qué tiene Alejandro mañana")
    asyncio.run(responder(update, None))

    assert update.message.respuestas_enviadas == []
    assert modelo_falso.conversaciones_recibidas == []


def pedir_accion_por_telegram(grafo):
    # Escribe una acción al bot y devuelve el mensaje que contestó el bot, con su teclado
    responder = crear_manejador(grafo, "111")
    update = UpdateFalso(111, "Responde a Laura que el viernes me va bien")
    asyncio.run(responder(update, None))
    return update.message


def datos_del_boton(mensaje, posicion):
    # posicion 0 es Aprobar y 1 es Rechazar (la primera fila del teclado)
    teclado = mensaje.teclados_enviados[0]
    return teclado.inline_keyboard[0][posicion].callback_data


def test_una_accion_llega_con_botones():
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), crear_herramientas())

    mensaje = pedir_accion_por_telegram(grafo)

    assert "create_draft" in mensaje.respuestas_enviadas[0]
    assert "laura.gomez@gmail.com" in mensaje.respuestas_enviadas[0]
    assert datos_del_boton(mensaje, 0).startswith("aprobar:")
    assert datos_del_boton(mensaje, 1).startswith("rechazar:")


def test_pulsar_aprobar_envia_el_correo():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])
    mensaje = pedir_accion_por_telegram(grafo)

    pulsar_boton = crear_manejador_de_botones(grafo, "111")
    update = UpdateDeBotonFalso(111, datos_del_boton(mensaje, 0), mensaje)
    asyncio.run(pulsar_boton(update, None))

    assert enviar_borrador.llamadas == [{"id_borrador": "borrador-123"}]
    assert update.callback_query.contestado is True
    assert update.callback_query.botones_quitados is True
    assert mensaje.respuestas_enviadas[-1] == "Hecho: he enviado el correo a laura.gomez@gmail.com."


def test_pulsar_rechazar_no_envia_nada():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])
    mensaje = pedir_accion_por_telegram(grafo)

    pulsar_boton = crear_manejador_de_botones(grafo, "111")
    asyncio.run(pulsar_boton(UpdateDeBotonFalso(111, datos_del_boton(mensaje, 1), mensaje), None))

    assert enviar_borrador.llamadas == []


def test_otro_usuario_no_puede_aprobar():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    grafo = crear_grafo(LLMFalso([propuesta_de_correo()], ["accion"]), [buscar, crear_borrador, enviar_borrador])
    mensaje = pedir_accion_por_telegram(grafo)

    pulsar_boton = crear_manejador_de_botones(grafo, "111")
    asyncio.run(pulsar_boton(UpdateDeBotonFalso(999, datos_del_boton(mensaje, 0), mensaje), None))

    assert enviar_borrador.llamadas == []


def test_un_boton_viejo_no_hace_nada():
    buscar, crear_borrador, enviar_borrador = crear_herramientas()
    respuestas = [propuesta_de_correo(), AIMessage(content="Hola.")]
    grafo = crear_grafo(LLMFalso(respuestas, ["accion", "consulta"]), [buscar, crear_borrador, enviar_borrador])
    mensaje = pedir_accion_por_telegram(grafo)

    # Antes de pulsar el botón escribes otra cosa: la propuesta pendiente se descarta
    responder = crear_manejador(grafo, "111")
    asyncio.run(responder(UpdateFalso(111, "Hola"), None))

    pulsar_boton = crear_manejador_de_botones(grafo, "111")
    asyncio.run(pulsar_boton(UpdateDeBotonFalso(111, datos_del_boton(mensaje, 0), mensaje), None))

    assert enviar_borrador.llamadas == []
    assert mensaje.respuestas_enviadas[-1] == TEXTO_PROPUESTA_CADUCADA

    # La propuesta descartada quedó cerrada (con su ToolMessage), así la conversación sigue en orden
    estado = asyncio.run(grafo.aget_state({"configurable": {"thread_id": "111"}}))
    ids_contestados = []
    for mensaje_del_historial in estado.values["messages"]:
        if isinstance(mensaje_del_historial, ToolMessage):
            ids_contestados.append(mensaje_del_historial.tool_call_id)
    assert "llamada-1" in ids_contestados
