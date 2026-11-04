# Evals es basicamente un "examen" para el asistente de verdad.

# Se ejecuta con: python -m asistente_ia.evals

# Cada caso es una pregunta sobre la agenda o la bandeja de prueba y lo que la respuesta debe cumplir.
# Hay tres tipos de casos, consultas del calendario, consultas del correo y acciones (en estas se mira la propuesta, no se ejecuta nada).
# Al final sale una tabla con los aciertos de cada tipo y la nota total, por ejemplo "27/30 (90 %)". Si cambias el prompt, el modelo o el proveedor, vuelves a pasarlas y sabes con números si ha mejorado o empeorado.

# Gasta tokens reales

import asyncio
from datetime import date

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.grafo import crear_grafo
from asistente_ia.llm import crear_llm
from asistente_ia.trazas import crear_callbacks

# La agenda de prueba es de la semana del lunes 2 de noviembre de 2026
FECHA_DE_LA_AGENDA = date(2026, 11, 2)


# Cada caso de consulta tiene:
#   pregunta              -> lo que le preguntamos
#   debe_contener         -> palabras que tienen que aparecer todas en la respuesta
#   debe_contener_alguna  -> de esta lista, tiene que aparecer al menos una palabra
#   debe_usar_herramienta -> True si tiene que usar alguna herramienta (calendario o correo), False si no
CASOS_CALENDARIO = [
    {
        "pregunta": "¿Qué tengo el jueves?",
        "debe_contener": ["tfg", "gimnasio"],
        "debe_contener_alguna": [],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Tengo algo mañana?",
        "debe_contener": ["dentista"],
        "debe_contener_alguna": [],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿A qué hora empieza hoy la clase de Redes?",
        "debe_contener": [],
        "debe_contener_alguna": ["9:00", "09:00", "las 9", "las nueve"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Qué tengo el sábado?",
        "debe_contener": [],
        "debe_contener_alguna": ["no tienes", "nada", "ningún", "libre"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Qué día es la cena con Laura?",
        "debe_contener": [],
        "debe_contener_alguna": ["viernes", "6 de noviembre", "2026-11-06"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Cuántos eventos tengo esta semana?",
        "debe_contener": [],
        "debe_contener_alguna": ["5", "cinco"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿A qué hora acaba el gimnasio el jueves?",
        "debe_contener": [],
        "debe_contener_alguna": ["20:30", "8:30"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Tengo algo el domingo 8?",
        "debe_contener": [],
        "debe_contener_alguna": ["no tienes", "nada", "ningún", "libre"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Qué es Python?",
        "debe_contener": ["programación"],
        "debe_contener_alguna": [],
        "debe_usar_herramienta": False,
    },
    {
        "pregunta": "Hola, ¿qué tal?",
        "debe_contener": [],
        "debe_contener_alguna": [],
        "debe_usar_herramienta": False,
    },
]

# Consultas sobre la bandeja de prueba (ver mcp_correo.py)
CASOS_CORREO = [
    {
        "pregunta": "¿Tengo algún correo de Laura?",
        "debe_contener": [],
        "debe_contener_alguna": ["cena", "cenar", "quedamos", "fotos"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Cuándo termina el plazo de matrícula del TFG?",
        "debe_contener": [],
        "debe_contener_alguna": ["15 de noviembre", "15/11", "2026-11-15", "día 15"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Qué tengo que llevar a la reunión con mi tutor?",
        "debe_contener": [],
        "debe_contener_alguna": ["índice", "indice"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Cuánto me han cobrado del gimnasio este mes?",
        "debe_contener": [],
        "debe_contener_alguna": ["39,90", "39.90"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Cuándo me llega el pedido de Amazon?",
        "debe_contener": [],
        "debe_contener_alguna": ["martes", "3 de noviembre", "2026-11-03", "mañana"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Me ha llegado algún aviso de GitHub?",
        "debe_contener": [],
        "debe_contener_alguna": ["falló", "fallado", "failed", "error", "fallo"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿A qué teléfono llamo si no puedo ir al dentista?",
        "debe_contener": [],
        "debe_contener_alguna": ["958 000 000", "958000000"],
        "debe_usar_herramienta": True,
    },
    {
        "pregunta": "¿Quién me ha escrito sobre la reunión del TFG?",
        "debe_contener": ["carlos"],
        "debe_contener_alguna": [],
        "debe_usar_herramienta": True,
    },
]

# Cada caso de acción tiene:
#   pregunta              -> lo que le pedimos
#   debe_proponer         -> la herramienta que tiene que proponer (y por tanto pedir aprobación)
#   datos_deben_contener  -> textos que tienen que aparecer en los datos de la propuesta (direcciones, ids, fechas, horas)
# La agenda de prueba tiene los eventos e1 (Clase de Redes), e2 (Dentista), e3 (Reunión del TFG), e4 (Gimnasio) y e5 (Cena con Laura)
CASOS_ACCION = [
    {
        "pregunta": "Responde a Laura que el viernes me va genial para cenar",
        "debe_proponer": "create_draft",
        "datos_deben_contener": ["laura.gomez@gmail.com", "c1"],
    },
    {
        "pregunta": "Escribe a Carlos Ruiz para decirle que llevaré el índice a la reunión",
        "debe_proponer": "create_draft",
        "datos_deben_contener": ["carlos.ruiz@ugr.es"],
    },
    {
        "pregunta": "Manda un correo a secretaria@etsiit.ugr.es preguntando si se puede ampliar el plazo del TFG",
        "debe_proponer": "create_draft",
        "datos_deben_contener": ["secretaria@etsiit.ugr.es"],
    },
    {
        "pregunta": "Contesta al correo de la clínica dental diciendo que el martes no puedo ir",
        "debe_proponer": "create_draft",
        "datos_deben_contener": ["citas@clinicasonrisa.es", "c7"],
    },
    {
        "pregunta": "Responde al correo de las fotos de Laura dándole las gracias",
        "debe_proponer": "create_draft",
        "datos_deben_contener": ["laura.gomez@gmail.com", "c8"],
    },
    {
        "pregunta": "Crea un evento 'Entregar matrícula TFG' el 10 de noviembre de 12:00 a 13:00",
        "debe_proponer": "create_event",
        "datos_deben_contener": ["2026-11-10", "12:00", "13:00"],
    },
    {
        "pregunta": "Apúntame pádel el sábado de 11:00 a 12:30",
        "debe_proponer": "create_event",
        "datos_deben_contener": ["2026-11-07", "11:00", "12:30"],
    },
    {
        "pregunta": "Mueve el dentista al miércoles a la misma hora",
        "debe_proponer": "move_event",
        "datos_deben_contener": ["e2", "2026-11-04", "17:30", "18:00"],
    },
    {
        "pregunta": "Pasa el gimnasio del jueves al viernes de 18:00 a 19:30",
        "debe_proponer": "move_event",
        "datos_deben_contener": ["e4", "2026-11-06", "18:00", "19:30"],
    },
    {
        "pregunta": "Retrasa una hora la cena con Laura",
        "debe_proponer": "move_event",
        "datos_deben_contener": ["e5", "22:00"],
    },
    {
        "pregunta": "Borra la clase de Redes de hoy",
        "debe_proponer": "delete_event",
        "datos_deben_contener": ["e1"],
    },
    {
        "pregunta": "Cancela la reunión del TFG",
        "debe_proponer": "delete_event",
        "datos_deben_contener": ["e3"],
    },
]


def corregir(caso, respuesta, uso_herramienta):
    # Devuelve la lista de fallos del caso. Si está vacía, el caso está aprobado.
    fallos = []
    respuesta_en_minusculas = respuesta.lower()

    for palabra in caso["debe_contener"]:
        if palabra not in respuesta_en_minusculas:
            fallos.append("falta '" + palabra + "'")

    if len(caso["debe_contener_alguna"]) > 0:
        encontrada = False
        for palabra in caso["debe_contener_alguna"]:
            if palabra in respuesta_en_minusculas:
                encontrada = True
        if not encontrada:
            fallos.append("no aparece ninguna de " + str(caso["debe_contener_alguna"]))

    if caso["debe_usar_herramienta"] and not uso_herramienta:
        fallos.append("no usó ninguna herramienta")
    if not caso["debe_usar_herramienta"] and uso_herramienta:
        fallos.append("usó herramientas sin necesidad")

    return fallos


# Corrige un caso de acción mirando la propuesta (lo que el grafo enseña antes de pedir aprobación). Devuelve la lista de fallos
def corregir_accion(caso, propuesta):
    if propuesta is None:
        return ["no propuso ninguna acción (no pidió aprobación)"]

    fallos = []
    if propuesta["herramienta"] != caso["debe_proponer"]:
        fallos.append("propuso " + propuesta["herramienta"] + " en vez de " + caso["debe_proponer"])

    # str() convierte el diccionario de argumentos en texto, así buscamos cada dato sin importar en qué campo esté
    datos_en_minusculas = str(propuesta["argumentos"]).lower()
    for dato in caso["datos_deben_contener"]:
        if dato.lower() not in datos_en_minusculas:
            fallos.append("en los datos falta '" + dato + "'")

    return fallos


# Hace una pregunta en su propia conversación (thread_id distinto), para que no recuerde las preguntas anteriores
async def preguntar(grafo, pregunta, nombre_de_la_conversacion):
    configuracion = {
        "configurable": {"thread_id": nombre_de_la_conversacion},
        "callbacks": crear_callbacks(),
    }
    estado_final = await grafo.ainvoke({"pregunta": pregunta}, configuracion)
    return estado_final, configuracion


# Pasa un caso de consulta. Devuelve su lista de fallos y lo que respondió (para enseñarlo si falla)
async def pasar_consulta(grafo, caso, nombre_de_la_conversacion):
    estado_final, configuracion = await preguntar(grafo, caso["pregunta"], nombre_de_la_conversacion)

    # Si el modelo confunde la consulta con una acción, el grafo se para a pedir aprobación. Lo reanudamos con un "no" y lo apuntamos como fallo
    pidio_aprobacion = False
    if "__interrupt__" in estado_final:
        pidio_aprobacion = True
        estado_final = await grafo.ainvoke(Command(resume=False), configuracion)

    # se uso la herramienta? Si en la conversación hay algún ToolMessage, sí
    uso_herramienta = False
    for mensaje in estado_final["messages"]:
        if isinstance(mensaje, ToolMessage):
            uso_herramienta = True

    respuesta = str(estado_final["respuesta"])
    fallos = corregir(caso, respuesta, uso_herramienta)
    if pidio_aprobacion:
        fallos.append("pidió aprobación y era una consulta")
    return fallos, "Respuesta: " + respuesta


# Pasa un caso de acción. Devuelve su lista de fallos y la propuesta o la respuesta (para enseñarla si falla). Nunca se aprueba nada, solo miramos la propuesta
async def pasar_accion(grafo, caso, nombre_de_la_conversacion):
    estado_final, configuracion = await preguntar(grafo, caso["pregunta"], nombre_de_la_conversacion)

    if "__interrupt__" in estado_final:
        propuesta = estado_final["__interrupt__"][0].value
        detalle = "Propuesta: " + str(propuesta)
        # Contestamos que no, para cerrar la propuesta. En las evals no se ejecuta ninguna acción
        await grafo.ainvoke(Command(resume=False), configuracion)
    else:
        propuesta = None
        detalle = "Respuesta: " + str(estado_final["respuesta"])

    fallos = corregir_accion(caso, propuesta)
    return fallos, detalle


# Pasa una lista de casos y devuelve cuántos aprueba
async def pasar_casos(grafo, casos, tipo):
    aprobados = 0
    numero = 0
    for caso in casos:
        numero = numero + 1
        nombre_de_la_conversacion = "eval-" + tipo + "-" + str(numero)

        if tipo == "accion":
            fallos, detalle = await pasar_accion(grafo, caso, nombre_de_la_conversacion)
        else:
            fallos, detalle = await pasar_consulta(grafo, caso, nombre_de_la_conversacion)

        if len(fallos) == 0:
            aprobados = aprobados + 1
            print("✓", tipo, numero, caso["pregunta"])
        else:
            print("✗", tipo, numero, caso["pregunta"])
            print("    Fallos:", fallos)
            print("    " + detalle)
    return aprobados


def escribir_fila(nombre, aprobados, total):
    porcentaje = round(aprobados * 100 / total)
    # ljust(26) rellena el nombre con espacios hasta 26 letras, así los números quedan en columna
    print("  " + nombre.ljust(26) + str(aprobados) + "/" + str(total) + " (" + str(porcentaje) + " %)")


async def main():
    # Agregamos una nueva key a el diccionario de cliente_mcp.py, basicamente forzamos que el servidor del calendario sea la demo y no google
    SERVIDORES["calendar"]["env"] = {"CALENDAR_BACKEND": "demo"}
    # Lo mismo con el correo: las evals siempre usan la bandeja de prueba, nunca tu Gmail.
    SERVIDORES["correo"]["env"] = {"CORREO_BACKEND": "demo"}

    modelo = crear_llm("fast")
    herramientas = await cargar_herramientas_mcp()
    grafo = crear_grafo(modelo, herramientas, FECHA_DE_LA_AGENDA)

    aprobados_calendario = await pasar_casos(grafo, CASOS_CALENDARIO, "calendario")
    aprobados_correo = await pasar_casos(grafo, CASOS_CORREO, "correo")
    aprobados_accion = await pasar_casos(grafo, CASOS_ACCION, "accion")

    aprobados = aprobados_calendario + aprobados_correo + aprobados_accion
    total = len(CASOS_CALENDARIO) + len(CASOS_CORREO) + len(CASOS_ACCION)

    print()
    print("Aciertos por tipo de caso:")
    escribir_fila("Consultas del calendario", aprobados_calendario, len(CASOS_CALENDARIO))
    escribir_fila("Consultas del correo", aprobados_correo, len(CASOS_CORREO))
    escribir_fila("Acciones (propuestas)", aprobados_accion, len(CASOS_ACCION))
    escribir_fila("Total", aprobados, total)


if __name__ == "__main__":
    asyncio.run(main())
