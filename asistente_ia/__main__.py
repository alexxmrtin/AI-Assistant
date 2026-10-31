# Punto de entrada: se ejecuta con `python -m asistente_ia`.
# Abre una conversación en la terminal. Para salir, escribe "salir" o deja la línea vacía.

from asistente_ia.grafo import crear_grafo
from asistente_ia.llm import crear_llm


def main() -> None:
    print('Hola, soy el Asistente IA. Escribe tu pregunta ("salir" para terminar).')

    modelo = crear_llm("fast")
    grafo = crear_grafo(modelo)

    # thread_id identifica la conversación. Todas las preguntas con el mismo thread_id
    # comparten memoria.
    configuracion = {"configurable": {"thread_id": "terminal"}}

    while True:
        pregunta = input("\nTú: ")

        if pregunta.strip() == "" or pregunta.strip() == "salir":
            print("¡Hasta luego!")
            return

        estado_final = grafo.invoke({"pregunta": pregunta}, configuracion)
        print("Asistente:", estado_final["respuesta"])


if __name__ == "__main__":
    main()
