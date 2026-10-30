# Punto de entrada: se ejecuta con `python -m asistente_ia`.

import sys

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from asistente_ia.herramientas import list_events
from asistente_ia.llm import crear_llm


def main() -> None:
    # Sin argumentos solo saluda.
    if len(sys.argv) < 2:
        print('Hola, soy el Asistente IA. Pregúntame algo: python -m asistente_ia "tu pregunta"')
        return

    # Todo lo que va después de `python -m asistente_ia` es la pregunta.
    palabras = sys.argv[1:]
    pregunta = " ".join(palabras)

    # 1. Creamos el modelo y le damos las herramientas. bind_tools no la ejecuta: solo le dice al
    #    modelo que existe, para qué sirve y qué parámetros tiene.
    modelo = crear_llm("fast")
    modelo_con_herramientas = modelo.bind_tools([list_events])

    # El modelo no sabe qué día es hoy, así que se lo decimos. Usamos una fecha fija
    # porque la agenda de prueba es de esa semana.
    mensajes = [
        SystemMessage("Eres un asistente personal. Hoy es lunes 2 de noviembre de 2026."),
        HumanMessage(pregunta),
    ]

    # 2. Llamamos al modelo (recuerda que le hemos bindeado las herramientas cuando lo hemos creado)
    respuesta = modelo_con_herramientas.invoke(mensajes)
    mensajes.append(respuesta) # Agrega a la lista un mensaje de tipo AIMessage()

    if len(respuesta.tool_calls) == 0:
        print("El modelo ha respondido sin usar herramientas:")
        print(respuesta.content)
        return

    # 3. El modelo ha pedido herramientas. Las ejecutamos nosotros, una a una.
        # Ejemplo de lo que hay en `llamada`:
        # {
        #     "name": "list_events",
        #     "args": {"fecha_inicio": "2026-11-05", "fecha_fin": "2026-11-05"},
        #     "id": "toolu_01AbC...",
        # }

    for llamada in respuesta.tool_calls:

        print("El modelo pide:", llamada["name"], "con", llamada["args"])

        resultado = list_events.invoke(llamada["args"])
        print("Resultado de la herramienta:", resultado)

        # Le devolvemos el resultado. tool_call_id indica a qué petición responde.
        mensaje_con_resultado = ToolMessage(content=str(resultado), tool_call_id=llamada["id"])
        mensajes.append(mensaje_con_resultado) # Se crea un mensaje de tipo ToolMessage()

    # 4. Segunda llamada: con los resultados, el modelo escribe la respuesta final.

    #    En este punto `mensajes` tiene 4 mensajes, por ejemplo:
    #    [
    #        SystemMessage("Eres un asistente personal. Hoy es lunes 2 de noviembre de 2026."),
    #        HumanMessage("¿Qué tengo el jueves?"),
    #        AIMessage(tool_calls=[list_events con fecha_inicio y fecha_fin 2026-11-05]),
    #        ToolMessage("[Reunión del TFG 10:00-11:00, Gimnasio 19:00-20:30]"),
    #    ]
    #    Si el modelo hubiera pedido dos herramientas, habría dos ToolMessage.
    
    respuesta_final = modelo_con_herramientas.invoke(mensajes)
    print()
    print("Respuesta final:")
    print(respuesta_final.content)


if __name__ == "__main__":
    main()
