# Punto de entrada: se ejecuta con `python -m asistente_ia`.
# Abre una conversación en la terminal. Para salir, escribe "salir" o deja la línea vacía.

import asyncio

from langgraph.types import Command

from asistente_ia.cliente_mcp import cargar_herramientas_mcp
from asistente_ia.grafo import crear_grafo
from asistente_ia.llm import crear_llm
from asistente_ia.memoria import abrir_memoria
from asistente_ia.trazas import crear_callbacks


# async def,main usa await para cargar las herramientas y para ejecutar el grafo.
async def main() -> None:
    print('Hola, soy el Asistente IA. Escribe tu pregunta ("salir" para terminar).')

    modelo = crear_llm("fast")
    herramientas = await cargar_herramientas_mcp()
    memoria = await abrir_memoria() # obtenemos un objeto que usa el grafo para saber como comunicarse con postgres y pedir los datos necesarios
    grafo = crear_grafo(modelo, herramientas, memoria=memoria)


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

        # Si el grafo se ha parado en approval_gate, el resultado trae la clave "__interrupt__" con la propuesta. Mientras siga parado, le preguntamos a la persona y lo reanudamos.
        # "__interrupt__" es una lista (un grafo podría pararse en varios sitios a la vez). Nosotros solo tenemos uno, y .value es lo que le pasamos a interrupt()
        while "__interrupt__" in estado_final:
            propuesta = estado_final["__interrupt__"][0].value
            print("Quiero hacer esto:", propuesta["accion"], "-", propuesta["detalles"])

            decision = input("¿Apruebas? (s/n): ")
            if decision.strip().lower() == "s":
                aprobada = True
            else:
                aprobada = False

            # Command(resume=...) despierta al grafo donde se paró, importante si no empezaria de nuevo el blucle. resume=aprobada el entregaa el grafo la variable "aprobada"
            estado_final = await grafo.ainvoke(Command(resume=aprobada), configuracion)

        print("Asistente:", estado_final["respuesta"]) # Devuelve el estado final del grafo, nos quedamos con la respuesta final 


if __name__ == "__main__":
    # asyncio.run arranca main (que es async) y espera a que termine.
    asyncio.run(main())
