import asyncio

from langchain_core.messages import AIMessage

from asistente_ia.grafo import crear_grafo
from asistente_ia.telegram_bot import crear_manejador
from tests.llm_falso import LLMFalso


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

    async def reply_text(self, texto):
        self.respuestas_enviadas.append(texto)


class UpdateFalso:
    def __init__(self, id_usuario, texto):
        self.effective_user = UsuarioFalso(id_usuario)
        self.effective_chat = ChatFalso(id_usuario)
        self.message = MensajeFalso(texto)


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
