class LLMFalso:
    def __init__(self, respuestas_preparadas):
        self.respuestas_preparadas = respuestas_preparadas

        self.conversaciones_recibidas = []

    def bind_tools(self, herramientas):
        return self

    def invoke(self, mensajes):
        copia_de_los_mensajes = list(mensajes)
        self.conversaciones_recibidas.append(copia_de_los_mensajes)

        siguiente_respuesta = self.respuestas_preparadas.pop(0)
        return siguiente_respuesta

    async def ainvoke(self, mensajes):
        return self.invoke(mensajes)
