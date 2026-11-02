# Evals: un "examen" para el asistente de verdad.
#
# Se ejecuta con: python -m asistente_ia.evals
#
# Cada caso es una pregunta sobre la agenda de prueba y lo que la respuesta debe cumplir.
# Al final sale una nota, por ejemplo "9/10 (90 %)". Si cambias el prompt, el modelo o el
# proveedor, vuelves a pasarlas y sabes con números si ha mejorado o empeorado.
#
# Gasta tokens reales

import asyncio
from datetime import date

from langchain_core.messages import ToolMessage

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.grafo import crear_grafo
from asistente_ia.llm import crear_llm
from asistente_ia.trazas import crear_callbacks

# La agenda de prueba es de la semana del lunes 2 de noviembre de 2026
FECHA_DE_LA_AGENDA = date(2026, 11, 2)


# Cada caso tiene:
#   pregunta              -> lo que le preguntamos
#   debe_contener         -> palabras que tienen que aparecer todas en la respuesta
#   debe_contener_alguna  -> de esta lista, tiene que aparecer al menos una palabra
#   debe_usar_herramienta -> True si tiene que consultar el calendario, False si no
CASOS = [
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
        fallos.append("no consultó el calendario")
    if not caso["debe_usar_herramienta"] and uso_herramienta:
        fallos.append("consultó el calendario sin necesidad")

    return fallos


async def main():
    # Agregamos una nueva key a el diccionario de cliente_mcp.py, basicamente forzamos que el servidor del calendario sea la demo y no google
    SERVIDORES["calendar"]["env"] = {"CALENDAR_BACKEND": "demo"}

    modelo = crear_llm("fast")
    herramientas = await cargar_herramientas_mcp()
    grafo = crear_grafo(modelo, herramientas, FECHA_DE_LA_AGENDA)

    aprobados = 0
    numero = 0

    for caso in CASOS:
        numero = numero + 1

        # Cada caso en su propia conversación (thread_id distinto), para que no recuerde las preguntas anteriores.
        configuracion = {
            "configurable": {"thread_id": "eval-" + str(numero)},
            "callbacks": crear_callbacks(),
        }
        estado_final = await grafo.ainvoke({"pregunta": caso["pregunta"]}, configuracion)

        # se uso la herramienta? Si en la conversación hay algún ToolMessage, sí
        uso_herramienta = False
        for mensaje in estado_final["messages"]:
            if isinstance(mensaje, ToolMessage):
                uso_herramienta = True

        respuesta = str(estado_final["respuesta"])
        fallos = corregir(caso, respuesta, uso_herramienta)

        if len(fallos) == 0:
            aprobados = aprobados + 1
            print("✓", numero, caso["pregunta"])
        else:
            print("✗", numero, caso["pregunta"])
            print("    Fallos:", fallos)
            print("    Respuesta:", respuesta)

    porcentaje = round(aprobados * 100 / len(CASOS))
    print()
    print("Nota:", str(aprobados) + "/" + str(len(CASOS)), "(" + str(porcentaje) + " %)")


if __name__ == "__main__":
    asyncio.run(main())
