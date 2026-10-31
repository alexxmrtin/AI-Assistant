#   START → ingest → agent → (¿pide herramientas?) → tools → agent → ... → respond → END
#
# Cada caja es un nodo: una función que recibe el estado y devuelve lo que cambia.

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from asistente_ia.herramientas import list_events

HERRAMIENTAS = {
    "list_events": list_events,
}

INSTRUCCIONES = "Eres un asistente personal. Hoy es lunes 2 de noviembre de 2026."


# El estado es la información que viaja de un nodo a otro.Creamos una clase que hereda de la clase MessagesState que importamos.
# IMPORTANTE, MessagesState no es una clase normal, es un TypeDict, basicamente es un tipado del diccionario que vamos a crear usando esta clase.Mira la linea 95, langraph crea por nosotros un diccionario usando esta clase como plantilla de lo que debe tener el diccionario
# MessagesState ya trae el campo "messages" (la conversación). Le añadimos dos más.
class Estado(MessagesState):
    pregunta: str  # lo que escribe la persona, tal cual
    respuesta: str  # el texto final que se le muestra



def crear_grafo(modelo):
    # Recibimos el modelo desde fuera y le bindeamos las herramientas (bind_tools() recibe una lista, aunque sea una se debe poner la lista)
    modelo_con_herramientas = modelo.bind_tools([list_events])


    # ----------------------------------------------------------------
    # Definimos Nodos

    # Convierte la pregunta en un HumanMessage y la añade a la conversación.
    def ingest(estado):
        pregunta_limpia = estado["pregunta"].strip()
        return {"messages": [HumanMessage(pregunta_limpia)]}


    # Llama al modelo con las instrucciones y toda la conversación.
    # Las instrucciones no se guardan en el estado: se añaden en cada llamada.
    def agent(estado):

        # Creamos una lista con la primera posicion con la instruccion del sistema, y despues metemos todos los mensajes de la conversacion, tanto los HumanMessage,como AIMessage como ToolMessage en el mismo orden como ocurrieron para que el llm tenga todo el contexto.
        mensajes = [SystemMessage(INSTRUCCIONES)]
        for mensaje in estado["messages"]:
            mensajes.append(mensaje)

        respuesta = modelo_con_herramientas.invoke(mensajes)

        return {"messages": [respuesta]} # Solo devolvemos la respuesta del llm


    def tools(estado):
        # Ejecuta las herramientas que pidió el modelo en su último mensaje. Sabemos que el AIMessage esta en la ultima posicion por como esta construido el grapho, es decir, la secuencia de pasos que sigue
        ultimo_mensaje = estado["messages"][-1]
        mensajes_con_resultados = []

        for llamada in ultimo_mensaje.tool_calls:
            # Ejemplo de lo que hay en `llamada`:
            # {
            #     "name": "list_events",
            #     "args": {"fecha_inicio": "2026-11-05", "fecha_fin": "2026-11-05"},
            #     "id": "toolu_01AbC...",
            # }
            print("El modelo pide:", llamada["name"], "con", llamada["args"])

            herramienta = HERRAMIENTAS[llamada["name"]]
            resultado = herramienta.invoke(llamada["args"])
            print("Resultado de la herramienta:", resultado)

            # tool_call_id indica a qué petición responde este resultado.
            mensaje = ToolMessage(content=str(resultado), tool_call_id=llamada["id"])
            mensajes_con_resultados.append(mensaje)

        return {"messages": mensajes_con_resultados}

    def respond(estado):
        # El último mensaje es la respuesta final del modelo: guardamos su texto.
        ultimo_mensaje = estado["messages"][-1]
        return {"respuesta": ultimo_mensaje.content}

    def siguiente_paso(estado):
        # Se ejecuta después de agent y decide a qué nodo ir.
        ultimo_mensaje = estado["messages"][-1]
        if len(ultimo_mensaje.tool_calls) > 0:
            return "tools"
        else:
            return "respond"

    # -------------------------------------------------------------------
    # Montamos el grafo: primero los nodos, después las flechas

    grafo = StateGraph(Estado)
    grafo.add_node("ingest", ingest)
    grafo.add_node("agent", agent)
    grafo.add_node("tools", tools)
    grafo.add_node("respond", respond)

    grafo.add_edge(START, "ingest")
    grafo.add_edge("ingest", "agent")
    grafo.add_conditional_edges("agent", siguiente_paso)  # a "tools" o a "respond"
    grafo.add_edge("tools", "agent")  # después de ejecutar, el modelo vuelve a pensar,esto con el anterior genera un bucle donde se pueden pedir herramientas hasta que se consiga la respuesta
    grafo.add_edge("respond", END)

    # -------------------------------------------------------------------
    # El checkpointer guarda el estado de cada conversación. Así, en la siguiente pregunta,
    # el grafo recuerda lo que se habló antes. InMemorySaver lo guarda en memoria, de modo
    # que se pierde al cerrar el programa, en un futuro lo guardaremos en una base de datos o usare REDIS.
    memoria = InMemorySaver()
    return grafo.compile(checkpointer=memoria)
