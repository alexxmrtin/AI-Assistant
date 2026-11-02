# Bot de Telegram para hablar con el asistente desde el móvil en vez de tener que usar la terminal
# Es un programa diferente al que hay en main, usa el mismo grafo y el mismo MCP, pero es diferente, tiene su propio modelo (que es el mismo pero ejecutado en un programa diferente) 

# Se ejecuta con "python -m asistente_ia.telegram_bot"

# Usa "polling", el programa pregunta a Telegram cada poco si hay mensajes nuevos, así que funciona desde tu ordenador sin servidor público. Mientras esté en marcha, el bot responde; si lo paras, los mensajes esperan en Telegram hasta que lo vuelvas a arrancar.

import asyncio

#   Application    -> el bot en sí, se conecta a Telegram con el token y recoge los mensajes
#   MessageHandler -> une un tipo de mensaje con la función que lo atiende (responder)
#   filters        -> elige qué mensajes atender (aquí, filters.TEXT: los de texto)
from telegram.ext import Application, MessageHandler, filters

from asistente_ia.cliente_mcp import cargar_herramientas_mcp  # trae las herramientas MCP
from asistente_ia.config import settings  # la configuración del .env
from asistente_ia.grafo import crear_grafo  # monta el grafo del asistente
from asistente_ia.llm import crear_llm  # crea el modelo (Claude, Gemini u Ollama)
from asistente_ia.trazas import crear_callbacks  # las trazas de Langfuse


def crear_manejador(grafo, usuario_permitido):
    # Devuelve la función que se ejecuta con cada mensaje que llega al bot. Como los nodos en crear_grafo, la función de dentro "recuerda" el grafo y el usuario.

    # update trae el mensaje,quién lo envía, en qué chat y el texto, y context es un objeto con utilidades de la libreria (python-telegram-bot). Importante entender que es la libreria la que ejecuta la funcion y le da estas dos cosas de forma automatica.
    async def responder(update, context):
        id_usuario = str(update.effective_user.id)

        if id_usuario != usuario_permitido:
            print("Mensaje ignorado del usuario", id_usuario)
            return

        pregunta = update.message.text

        # Cada chat de Telegram es una conversación con su propia memoria, usamos el id del chat como thread_id.
        id_chat = str(update.effective_chat.id)
        configuracion = {
            "configurable": {"thread_id": id_chat},
            "callbacks": crear_callbacks(),
        }

        estado_final = await grafo.ainvoke({"pregunta": pregunta}, configuracion)

        # Enviamos la respuesta al mismo chat.
        await update.message.reply_text(estado_final["respuesta"])

    return responder


def main():
    if settings.telegram_bot_token == "" or settings.telegram_user_id == "":
        print("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_USER_ID en el .env")
        return

    modelo = crear_llm("fast")
    herramientas = asyncio.run(cargar_herramientas_mcp())
    grafo = crear_grafo(modelo, herramientas)

    # La aplicación de python-telegram-bot se conecta a Telegram con el token del bot.
    aplicacion = Application.builder().token(settings.telegram_bot_token).build()

    # Esto crea una regla, cuando llegue un mensaje de texto al bot de telegram, ejecuta la funcion (el manejador)
    manejador = crear_manejador(grafo, settings.telegram_user_id)
    aplicacion.add_handler(MessageHandler(filters.TEXT, manejador)) # Le entrega la regla al bot cada vez que recoja un mensaje

    print("Bot en marcha. Escríbele desde Telegram (Ctrl+C para parar).")

    # Se queda preguntando a Telegram por mensajes nuevos hasta que lo paras
    aplicacion.run_polling()


if __name__ == "__main__":
    main()
