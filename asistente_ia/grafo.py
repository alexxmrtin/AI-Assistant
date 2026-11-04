#   START → ingest → route → (¿consulta o acción?)
#                              consulta → agent → (¿pide herramientas?) → tools → agent → ... → respond → END
#                              accion   → propose ⇄ tools (si necesita leer algo antes de proponer)
#                                         propose → prepare → approval_gate → (¿sí o no?) → execute → END
#                                                                                         → reject  → END
#
# Cada caja es un nodo: una función que recibe el estado y devuelve lo que cambia.

import json
from datetime import date

from langchain_core.exceptions import OutputParserException  # no se pudo leer al modelo
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field, ValidationError

DIAS_DE_LA_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def crear_instrucciones(fecha):
    # Las instrucciones del sistema, con la fecha de hoy para que el modelo sepa qué día es "mañana" o "el jueves"

    # weekday() da el día de la semana como número: 0 es lunes y 6 es domingo.
    nombre_del_dia = DIAS_DE_LA_SEMANA[fecha.weekday()]
    # month va de 1 a 12 y la lista empieza en la posición 0, por eso restamos 1.
    nombre_del_mes = MESES[fecha.month - 1]

    fecha_en_texto = nombre_del_dia + " " + str(fecha.day) + " de " + nombre_del_mes
    fecha_en_texto = fecha_en_texto + " de " + str(fecha.year)

    # isoformat() da la fecha como "2026-11-02", el formato que usa list_events.
    return "Eres un asistente personal. Hoy es " + fecha_en_texto + " (" + fecha.isoformat() + ")."


# Se llama al final de cada propuesta (aprobada, rechazada o con error). Añade la respuesta (ToolMessage) a la herramienta que pidió el modelo en propose, si no, en el siguiente mensaje el modelo daría error. Así además recuerda qué pasó con su propuesta
def cerrar_propuesta(estado, texto):
    # El último mensaje es la propuesta del modelo: approval_gate y prepare no añaden mensajes
    ultimo_mensaje = estado["messages"][-1]

    mensajes = []
    for llamada in ultimo_mensaje.tool_calls:
        mensajes.append(ToolMessage(content=texto, tool_call_id=llamada["id"]))
    mensajes.append(AIMessage(texto))

    return {"messages": mensajes, "respuesta": texto}


# El estado es la información que viaja de un nodo a otro.Creamos una clase que hereda de la clase MessagesState que importamos.
# IMPORTANTE, MessagesState no es una clase normal, es un TypeDict, basicamente es un tipado del diccionario que vamos a crear usando esta clase.Mira la linea 95, langraph crea por nosotros un diccionario usando esta clase como plantilla de lo que debe tener el diccionario
# MessagesState ya trae el campo "messages" (la conversación). Le añadimos dos más.
class Estado(MessagesState):
    pregunta: str  # lo que escribe la persona, tal cual
    respuesta: str  # el texto final que se le muestra
    intencion: str  # "consulta" o "accion", la decide el nodo route
    propuesta: dict  # la herramienta que propone el modelo y sus datos: {"herramienta": ..., "argumentos": {...}}, o None si no propone nada
    aprobada: bool  # True si la persona dijo que sí en approval_gate


# Salida estructurada, en vez de pedirle al modelo un texto libre ("creo que es una consulta porque..."), le pedimos que rellene esta ficha con dos campos fijos
# BaseModel es la clase de Pydantic, lo uso en sttings
class Clasificacion(BaseModel):
    intencion: str = Field(
        description=(
            "'consulta' si la persona quiere saber algo, que leas algo (su agenda, sus correos) o solo charlar. "
            "'accion' si quiere que cambies algo en su cuenta: enviar o responder un correo, o crear, mover o borrar un evento."
        )
    )
    motivo: str = Field(description="Una frase corta que explique por qué has elegido esa intención.")




# ----------------------------------------------------------------

INSTRUCCIONES_DE_CLASIFICACION = (
    "Eres el clasificador de un asistente personal con acceso a la agenda y al correo de la persona. "
    "Lee su mensaje y decide si es una consulta o una acción. "
    "Ante la duda, elige 'consulta': es lo seguro, porque no cambia nada."
)

INSTRUCCIONES_DE_PROPUESTA = (
    "La persona te ha pedido una acción. Propónla llamando a UNA herramienta que cambie algo "
    "(create_draft, create_event, move_event o delete_event): no se ejecutará hasta que la persona la apruebe. "
    "Si te faltan datos, usa antes las herramientas de lectura (por ejemplo search_emails para saber la dirección "
    "o el id del correo al que respondes, o list_events para saber el id del evento que hay que mover o borrar). "
    "Si aun así falta algo que solo sabe la persona, no llames a ninguna herramienta y pregúntaselo."
)

# Herramientas que cambian algo en tu cuenta. El agente nunca las recibe y el nodo tools se niega a ejecutarlas
HERRAMIENTAS_DE_ESCRITURA = ["create_draft", "send_draft", "create_event", "move_event", "delete_event"]

# De ellas, las que el modelo puede proponer en propose. send_draft no esta,solo la usa execute después de tu sí
HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER = ["create_draft", "create_event", "move_event", "delete_event"]

# Respuesta fija cuando dices que no
TEXTO_ACCION_RECHAZADA = "Vale, no lo hago. Si había un borrador, se queda guardado por si quieres usarlo."

# Lo que recibe el modelo si pide una herramienta de escritura fuera de propose
TEXTO_ESCRITURA_NO_PERMITIDA = "No permitido: esta herramienta solo se usa después de que la persona apruebe una propuesta."



# fecha_fija, solo para evals y tests, que usan la agenda de prueba (semana del 2 de noviembre de 2026). Si no se pasa, el asistente usa la fecha real de cada día.
# memoria - dónde se guardan las conversaciones (ver memoria.py). Si no se pasa, se guardan en RAM, como en los tests.
def crear_grafo(modelo, herramientas, fecha_fija=None, memoria=None):
    # Recibimos el modelo y las herramientas desde fuera. Las herramientas vienen de los
    # servidores MCP (ver cliente_mcp.py) y son una lista.
    # Separamos las herramientas en dos listas: las de lectura (las puede usar el agente) y las que el modelo puede proponer (solo en propose)
    herramientas_de_lectura = []
    herramientas_para_proponer = []
    for herramienta in herramientas:
        if herramienta.name in HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER:
            herramientas_para_proponer.append(herramienta)
        if herramienta.name not in HERRAMIENTAS_DE_ESCRITURA:
            herramientas_de_lectura.append(herramienta)

    # Le bindeamos al modelo solo las de lectura (bind_tools() recibe una lista). Así el agente ni siquiera sabe que existen las de escritura
    modelo_con_herramientas = modelo.bind_tools(herramientas_de_lectura)

    # En propose el modelo ve las de lectura (para buscar lo que le falte) y las que puede proponer. Las puede PEDIR, pero quien decide si se ejecutan es el grafo, no él
    modelo_para_proponer = modelo.bind_tools(herramientas_de_lectura + herramientas_para_proponer)

# with_structured_output prepara una versión del modelo que, en vez de un mensaje, devuelve una ficha Clasificacion ya rellenada y comprobada por Pydantic. 
    # Por dentro usa el tool calling, le da al modelo una "herramienta" llamada Clasificacion y le obliga a usarla. Los argumentos que el modelo rellena son la ficha.
    clasificador = modelo.with_structured_output(Clasificacion)

    # Devuelve la fecha que usa el asistente como "hoy". La usan agent y propose. fecha_fija es una variable que usan los evals para que el agente crea que dia es hoy, el dia nos lo inventaremos
    def calcular_fecha_de_hoy():
        if fecha_fija is None:
            return date.today()
        else:
            return fecha_fija

    # Diccionario nombre -> herramienta, para encontrar la que pide el modelo en el nodo tools.
    # Ejemplo: {"list_events": <herramienta list_events>}
    herramientas_por_nombre = {}
    for herramienta in herramientas:
        herramientas_por_nombre[herramienta.name] = herramienta


    # ----------------------------------------------------------------
    # Definimos Nodos (el objeto estado lo crea langraph, es la "mochila" que se ha explicado arriba)

    # Convierte la pregunta en un HumanMessage y la añade a la conversación.
    def ingest(estado):
        pregunta_limpia = estado["pregunta"].strip()
        return {"messages": [HumanMessage(pregunta_limpia)]}


    # Decide si el mensaje es una consulta o una acción, para elegir el camino del grafo.
    async def route(estado):
        # Solo le pasamos el mensaje nuevo, no toda la conversación
        mensajes = [SystemMessage(INSTRUCCIONES_DE_CLASIFICACION), HumanMessage(estado["pregunta"])]

        # Si el modelo devuelve una ficha incompleta o con tipos incorrectos, Pydantic lanza ValidationError (o LangChain lanza OutputParserException si no puede ni leerla). En ese caso elegimos modo consulta
        try:
            clasificacion = await clasificador.ainvoke(mensajes)
        except (ValidationError, OutputParserException) as error:
            print("El modelo devolvió una clasificación no válida:", error)
            return {"intencion": "consulta"}

        # Si el modelo contesta con texto en vez de rellenar la ficha, llega None
        if clasificacion is None:
            print("El modelo no rellenó la clasificación")
            return {"intencion": "consulta"}

        # Pydantic garantiza que intencion es un texto, pero no que sea una de nuestras dos palabras. Lo comprobamos nosotros
        intencion = clasificacion.intencion.strip().lower()
        if intencion == "accion" or intencion == "acción":
            intencion = "accion"
        else:
            intencion = "consulta"

        print("Clasificación:", intencion, "-", clasificacion.motivo)
        return {"intencion": intencion}

    # Se ejecuta después de route y decide a qué nodo ir
    def siguiente_tras_route(estado):
        if estado["intencion"] == "accion":
            return "propose"
        else:
            return "agent"

    # Si la pregunta del usuario requiere de una accion por parte de el agente, se ejecuta este nodo. Si es una consulta se ejecuta directamente el nodo de agent.
    # La propuesta es una llamada a herramienta (tool calling), el modelo pide, por ejemplo, create_draft con sus datos. Pero aquí NO se ejecuta, solo se apunta
    async def propose(estado):
        # Le pasamos toda la conversación, por si la persona dice algo como "contéstale" refiriéndose a un correo del que hablabais antes
        instrucciones = crear_instrucciones(calcular_fecha_de_hoy()) + " " + INSTRUCCIONES_DE_PROPUESTA
        mensajes = [SystemMessage(instrucciones)]
        for mensaje in estado["messages"]:
            mensajes.append(mensaje)

        respuesta = await modelo_para_proponer.ainvoke(mensajes)

        # Buscamos, entre lo que pide el modelo, la primera herramienta que se puede proponer. Las de lectura las ejecutará el nodo tools
        propuesta = None
        for llamada in respuesta.tool_calls:
            if llamada["name"] in HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER and propuesta is None:
                propuesta = {"herramienta": llamada["name"], "argumentos": llamada["args"]}

        if propuesta is not None:
            print("Propuesta:", propuesta)

        # La respuesta del modelo se añade a la conversación. La propuesta se guarda aparte, como un diccionario normal, para que se guarde sin problemas en la memoria mientras el grafo espera tu respuesta
        return {"messages": [respuesta], "propuesta": propuesta}

    # Se ejecuta después de propose y decide a qué nodo ir
    def siguiente_tras_propose(estado):
        ultimo_mensaje = estado["messages"][-1]
        if estado["propuesta"] is not None:
            return "prepare"  # hay propuesta, la preparamos y pedimos aprobación
        elif len(ultimo_mensaje.tool_calls) > 0:
            return "tools"  # quiere leer algo antes de proponer (por ejemplo, buscar el correo de Laura)
        else:
            return "respond"  # no propone nada: te contesta con texto (por ejemplo, para preguntarte un dato)

    # Prepara, sin riesgo, lo que se pueda antes de preguntarte.
    # Para un correo crea el borrador, no se envía, pero así puedes verlo en Gmail tal cual saldría.
    # Para mover o borrar un evento, lee cómo es ahora, el modelo solo da un id y tú tienes que ver que evento vas a cambiar antes de aprobar
    async def prepare(estado):
        propuesta = estado["propuesta"]
        herramienta = propuesta["herramienta"]

        # Copiamos la propuesta y le iremos añadiendo datos (un campo del estado se sustituye entero, no se mezcla)
        propuesta_preparada = {
            "herramienta": herramienta,
            "argumentos": propuesta["argumentos"],
        }

        try:
            if herramienta == "create_draft":
                resultado = await herramientas_por_nombre["create_draft"].ainvoke(propuesta["argumentos"])
                # El resultado de una herramienta MCP es una lista de bloques de texto. create_draft devuelve solo el id del borrador, que está en el texto del primer bloque
                propuesta_preparada["id_borrador"] = resultado[0]["text"]
                print("Borrador creado:", propuesta_preparada["id_borrador"])

            if herramienta == "move_event" or herramienta == "delete_event":
                id_evento = propuesta["argumentos"]["id_evento"]
                resultado = await herramientas_por_nombre["get_event"].ainvoke({"id_evento": id_evento})

                # get_event devuelve el evento en JSON, json.loads lo convierte en un diccionario para poder mirar sus campos
                evento = json.loads(resultado[0]["text"])

                # Si el id no existe (por ejemplo, el modelo se lo ha inventado), paramos aquí
                if "error" in evento:
                    cambios = cerrar_propuesta(estado, "No he encontrado ese evento: " + evento["error"])
                    cambios["propuesta"] = None
                    return cambios

                propuesta_preparada["evento_actual"] = evento["titulo"] + ", " + evento["fecha"] + " de " + evento["inicio"] + " a " + evento["fin"]
        except Exception as error:
            # Si Google falla (por ejemplo, la sesión ha caducado), no seguimos, cerramos la propuesta contándote el error
            print("Error al preparar la propuesta:", error)
            cambios = cerrar_propuesta(estado, "No he podido preparar la acción: " + str(error))
            cambios["propuesta"] = None
            return cambios

        return {"propuesta": propuesta_preparada}

    # Si prepare ha fallado, la propuesta ya no existe y terminamos. Si no, pedimos aprobación
    def siguiente_tras_prepare(estado):
        if estado["propuesta"] is None:
            return END
        else:
            return "approval_gate"

    # Esto es el componente Human-in-the-loop del proyecto, el loop se para hasta que la persona confirme
    # interrupt() guarda el estado en la memoria (por eso hace falta el checkpointer) y corta la ejecución, ainvoke termina y devuelve la propuesta a quien llamó (el main).(mira el main)
    def approval_gate(estado):
        decision = interrupt(estado["propuesta"])

        # Solo un True exacto cuenta como sí. Cualquier otra cosa es no: ante la duda, no se hace nada
        if decision is True:
            return {"aprobada": True}
        else:
            return {"aprobada": False}

    def siguiente_tras_approval_gate(estado):
        if estado["aprobada"]:
            return "execute"
        else:
            return "reject"

    # El único nodo que hace cambios de verdad, y solo se llega a él pasando por approval_gate con un sí
    async def execute(estado):
        propuesta = estado["propuesta"]

        try:
            if propuesta["herramienta"] == "create_draft":
                # El borrador ya existe (lo creó prepare), solo falta enviarlo
                await herramientas_por_nombre["send_draft"].ainvoke({"id_borrador": propuesta["id_borrador"]})
                texto = "Hecho: he enviado el correo a " + propuesta["argumentos"]["para"] + "."
            else:
                # En el calendario, la herramienta propuesta es la que hace el cambio, la ejecutamos tal cual con sus argumentos. Devuelve una frase como "Evento creado: ..."
                resultado = await herramientas_por_nombre[propuesta["herramienta"]].ainvoke(propuesta["argumentos"])
                texto = "Hecho. " + resultado[0]["text"]
        except Exception as error:
            print("Error al ejecutar la acción:", error)
            texto = "No he podido hacerlo: " + str(error)

        print(texto)
        return cerrar_propuesta(estado, texto)

    # La persona dijo que no
    def reject(estado):
        return cerrar_propuesta(estado, TEXTO_ACCION_RECHAZADA)

    # Llama al modelo con las instrucciones y toda la conversación.
    # Las instrucciones no se guardan en el estado,se añaden en cada llamada.
    # async, el nodo es asíncrono porque espera la respuesta del modelo con await.
    async def agent(estado):

        # Creamos una lista con la primera posicion con la instruccion del sistema, y despues metemos todos los mensajes de la conversacion, tanto los HumanMessage,como AIMessage como ToolMessage en el mismo orden como ocurrieron para que el llm tenga todo el contexto.
        # La fecha se calcula en cada llamada: así el bot, que puede estar días encendido,siempre sabe qué día es.
        
        fecha_de_hoy = calcular_fecha_de_hoy()

        mensajes = [SystemMessage(crear_instrucciones(fecha_de_hoy))]
        for mensaje in estado["messages"]:
            mensajes.append(mensaje)

        # ainvoke es la versión async de invoke. await espera la respuesta del modelo, y
        # mientras tanto el programa puede atender otras cosas (por ejemplo, otro mensaje).
        respuesta = await modelo_con_herramientas.ainvoke(mensajes)

        return {"messages": [respuesta]} # Solo devolvemos la respuesta del llm , respuesta es un AIMessage, no hace falta convertirlo


    async def tools(estado):
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

            # Segunda barrera: aunque el modelo pida una herramienta de escritura (no la tiene, pero podría inventarse el nombre), aquí nunca se ejecuta
            if llamada["name"] in HERRAMIENTAS_DE_ESCRITURA:
                resultado = TEXTO_ESCRITURA_NO_PERMITIDA
            else:
                herramienta = herramientas_por_nombre[llamada["name"]]

                # Las herramientas MCP son asíncronas: await espera a que el servidor MCP
                # ejecute la herramienta y nos devuelva el resultado.
                resultado = await herramienta.ainvoke(llamada["args"])
            print("Resultado de la herramienta:", resultado)

            # tool_call_id indica a qué petición responde este resultado.
            # El resultado de una herramienta MCP es una lista de bloques de texto, el formato
            # que entienden todos los modelos, así que se lo pasamos tal cual.
            mensaje = ToolMessage(content=resultado, tool_call_id=llamada["id"])
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

    # tools lo usan agent y propose: después de leer, volvemos al que lo pidió
    def siguiente_tras_tools(estado):
        if estado["intencion"] == "accion":
            return "propose"
        else:
            return "agent"

    # -------------------------------------------------------------------
    # Montamos el grafo: primero los nodos, después las flechas

    grafo = StateGraph(Estado)
    grafo.add_node("ingest", ingest)
    grafo.add_node("route", route)
    grafo.add_node("propose", propose)
    grafo.add_node("prepare", prepare)
    grafo.add_node("approval_gate", approval_gate)
    grafo.add_node("execute", execute)
    grafo.add_node("reject", reject)
    grafo.add_node("agent", agent)
    grafo.add_node("tools", tools)
    grafo.add_node("respond", respond)

    grafo.add_edge(START, "ingest")
    grafo.add_edge("ingest", "route")
    grafo.add_conditional_edges("route", siguiente_tras_route)  # a "agent" o a "propose"
    grafo.add_conditional_edges("propose", siguiente_tras_propose)  # a "prepare", "tools" o "respond"
    grafo.add_conditional_edges("prepare", siguiente_tras_prepare)  # a "approval_gate" o a END
    grafo.add_conditional_edges("approval_gate", siguiente_tras_approval_gate)  # a "execute" o a "reject"
    grafo.add_edge("execute", END)
    grafo.add_edge("reject", END)
    grafo.add_conditional_edges("agent", siguiente_paso)  # a "tools" o a "respond"
    grafo.add_conditional_edges("tools", siguiente_tras_tools)  # vuelve a "agent" o a "propose": el modelo vuelve a pensar, y así se pueden pedir herramientas hasta tener lo necesario
    grafo.add_edge("respond", END)

    # -------------------------------------------------------------------
    # Creamos la memoria donde se guardará el estado de cada conversación, algo como:
    #
    # {
    #  "terminal": {"messages": [...todos los mensajes...], "pregunta": ..., "respuesta": ...},
    #  "otra-conversacion": {...},
    # }
    #
    # La clave ("terminal") es el thread_id que pasamos en el main.
    # Si no nos han pasado una memoria (por ejemplo, la de Postgres), usamos la RAM.
    if memoria is None:
        memoria = InMemorySaver()

    # .compile convierte el plano del grafo en algo que se puede invocar y le da la memoria. No ejecuta nada, el grafo se ejecuta en cada grafo.invoke().
    return grafo.compile(checkpointer=memoria)

