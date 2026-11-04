from asistente_ia.grafo import Clasificacion


class LLMFalso:
    def __init__(self, respuestas_preparadas, intenciones_preparadas=None):
        self.respuestas_preparadas = respuestas_preparadas

        # Lo que contestará el nodo route. Si no se preparan, todo es "consulta".
        if intenciones_preparadas is None:
            self.intenciones_preparadas = []
        else:
            self.intenciones_preparadas = intenciones_preparadas

        self.conversaciones_recibidas = []
        self.herramientas_recibidas = []

    def bind_tools(self, herramientas):
        # Apuntamos los nombres de las herramientas que recibe, para comprobar que el agente no recibe las de escritura
        nombres = []
        for herramienta in herramientas:
            nombres.append(herramienta.name)
        self.herramientas_recibidas.append(nombres)
        return self

    def with_structured_output(self, esquema):
        return ClasificadorFalso(self.intenciones_preparadas)

    def invoke(self, mensajes):
        copia_de_los_mensajes = list(mensajes)
        self.conversaciones_recibidas.append(copia_de_los_mensajes)

        siguiente_respuesta = self.respuestas_preparadas.pop(0)
        return siguiente_respuesta

    async def ainvoke(self, mensajes):
        return self.invoke(mensajes)


class ClasificadorFalso:
    def __init__(self, intenciones_preparadas):
        self.intenciones_preparadas = intenciones_preparadas

    async def ainvoke(self, mensajes):
        if len(self.intenciones_preparadas) == 0:
            intencion = "consulta"
        else:
            intencion = self.intenciones_preparadas.pop(0)

        # None simula un modelo que no rellena la ficha.
        if intencion is None:
            return None

        return Clasificacion(intencion=intencion, motivo="clasificación preparada para el test")


class HerramientaFalsa:
    # Imita una herramienta MCP: tiene nombre, apunta con qué datos la llaman y devuelve un texto preparado con la misma forma que las de verdad
    def __init__(self, nombre, respuesta):
        self.name = nombre
        self.respuesta = respuesta
        self.llamadas = []

    async def ainvoke(self, argumentos):
        self.llamadas.append(argumentos)
        return [{"type": "text", "text": self.respuesta}]
