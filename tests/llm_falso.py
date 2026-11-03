from asistente_ia.grafo import Clasificacion, PropuestaDeAccion


class LLMFalso:
    def __init__(self, respuestas_preparadas, intenciones_preparadas=None, propuestas_preparadas=None):
        self.respuestas_preparadas = respuestas_preparadas

        # Lo que contestará el nodo route. Si no se preparan, todo es "consulta".
        if intenciones_preparadas is None:
            self.intenciones_preparadas = []
        else:
            self.intenciones_preparadas = intenciones_preparadas

        # Lo que contestará el nodo propose. Si no se preparan, siempre propone borrar el dentista.
        if propuestas_preparadas is None:
            self.propuestas_preparadas = []
        else:
            self.propuestas_preparadas = propuestas_preparadas

        self.conversaciones_recibidas = []

    def bind_tools(self, herramientas):
        return self

    def with_structured_output(self, esquema):
        # El grafo pide dos fichas distintas: devolvemos el falso que corresponde a cada una
        if esquema == Clasificacion:
            return ClasificadorFalso(self.intenciones_preparadas)
        else:
            return ProponedorFalso(self.propuestas_preparadas)

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


class ProponedorFalso:
    def __init__(self, propuestas_preparadas):
        self.propuestas_preparadas = propuestas_preparadas

    async def ainvoke(self, mensajes):
        if len(self.propuestas_preparadas) == 0:
            return PropuestaDeAccion(accion="borrar evento", detalles="Dentista del jueves a las 17:00")

        # Una propuesta preparada es una PropuestaDeAccion, o None para simular un modelo que no rellena la ficha.
        return self.propuestas_preparadas.pop(0)
