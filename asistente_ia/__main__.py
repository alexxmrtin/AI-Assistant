# Punto de entrada: se ejecuta con `python -m asistente_ia`.
# Abre una conversación en la terminal. Para salir, escribe "salir" o deja la línea vacía.

import asyncio

from asistente_ia.cliente_mcp import cargar_herramientas_mcp
from asistente_ia.grafo import crear_grafo
from asistente_ia.llm import crear_llm
from asistente_ia.trazas import crear_callbacks


# async def,main usa await para cargar las herramientas y para ejecutar el grafo.
async def main() -> None:
    print('Hola, soy el Asistente IA. Escribe tu pregunta ("salir" para terminar).')

    modelo = crear_llm("fast")
    herramientas = await cargar_herramientas_mcp()
    grafo = crear_grafo(modelo, herramientas)


    # Diccionario con dos configuraciones que acompañara a cada pregunta
    # thread_id identifica la conversación. Todas las preguntas con el mismo thread_id comparten memoria y callbacks recibe los avisos de cada paso del grafo y los envía a Langfuse.(es un diccionario porque cada thread_id es una conversacion)
    configuracion = {
        "configurable": {"thread_id": "terminal"},
        "callbacks": crear_callbacks(),
    }

    while True:
        pregunta = input("\nTú: ")

        if pregunta.strip() == "" or pregunta.strip() == "salir":
            print("¡Hasta luego!")
            return

        estado_final = await grafo.ainvoke({"pregunta": pregunta}, configuracion) # Ejecuta el grafo entero con la pregunta y la configuracion

        print("Asistente:", estado_final["respuesta"]) # Devuelve el estado final del grafo, nos quedamos con la respuesta final (estado_final tiene messages,pregunta y respuesta)


if __name__ == "__main__":
    # asyncio.run arranca main (que es async) y espera a que termine.
    asyncio.run(main())
