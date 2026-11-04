# Bot de Telegram para hablar con el asistente desde el móvil en vez de tener que usar la terminal
# Es un programa diferente al que hay en main, usa el mismo grafo y el mismo MCP, pero es diferente, tiene su propio modelo (que es el mismo pero ejecutado en un programa diferente) 

# Se ejecuta con "python -m asistente_ia.telegram_bot"

# Usa "polling", el programa pregunta a Telegram cada poco si hay mensajes nuevos, así que funciona desde tu ordenador sin servidor público. Mientras esté en marcha, el bot responde; si lo paras, los mensajes esperan en Telegram hasta que lo vuelvas a arrancar.

#   Application    -> el bot en sí, se conecta a Telegram con el token y recoge los mensajes
#   MessageHandler -> une un tipo de mensaje con la función que lo atiende (responder)
#   filters        -> elige qué mensajes atender (aquí, filters.TEXT: los de texto)
#   CallbackQueryHandler -> une la pulsación de un botón con la función que la atiende (pulsar_boton)
#   InlineKeyboardButton / InlineKeyboardMarkup -> un botón y el teclado de botones que va pegado a un mensaje
from langgraph.types import Command
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from asistente_ia.cliente_mcp import cargar_herramientas_mcp  # trae las herramientas MCP
from asistente_ia.config import settings  # la configuración del .env
from asistente_ia.grafo import crear_grafo  # monta el grafo del asistente
from asistente_ia.llm import crear_llm  # crea el modelo (Claude, Gemini u Ollama)
from asistente_ia.memoria import abrir_memoria  # la memoria de las conversaciones (Postgres)
from asistente_ia.trazas import crear_callbacks  # las trazas de Langfuse

# Lo que contesta el bot si pulsas un botón de una propuesta que ya no está pendiente
TEXTO_PROPUESTA_CADUCADA = (
    "Esta propuesta ya no está pendiente (ya la contestaste o escribiste otra cosa después). No he hecho nada."
)


# Cada chat de Telegram es una conversación con su propia memoria, usamos el id del chat como thread_id.
def crear_configuracion(id_chat):
    return {
        "configurable": {"thread_id": id_chat},
        "callbacks": crear_callbacks(),
    }


# Convierte la propuesta en el texto del mensaje, con lo mismo que enseña la terminal (ver __main__.py)
def escribir_propuesta(propuesta):
    texto = "Quiero usar " + propuesta["herramienta"] + " con estos datos:"
    for nombre in propuesta["argumentos"]:
        texto = texto + "\n  " + nombre + ": " + str(propuesta["argumentos"][nombre])
    if "evento_actual" in propuesta:
        texto = texto + "\nEvento que se va a cambiar: " + propuesta["evento_actual"]
    if "id_borrador" in propuesta:
        texto = texto + "\nBorrador creado (puedes verlo en Gmail): " + propuesta["id_borrador"]
    texto = texto + "\n\n¿Lo apruebas?"
    return texto


# Envía al chat lo que toque, la propuesta con botones si el grafo se ha parado a pedir aprobación, o la respuesta normal si ha terminado.Es basicamente un print solo que se envia a la conversacion
async def contestar(estado_final, mensaje):
    if "__interrupt__" in estado_final:
        parada = estado_final["__interrupt__"][0]

        # callback_data es el texto que Telegram nos devuelve cuando pulsas el botón. Le añadimos el id de esta parada (lo pone LangGraph) para saber después a qué propuesta corresponde el botón
        boton_aprobar = InlineKeyboardButton("Aprobar", callback_data="aprobar:" + parada.id)
        boton_rechazar = InlineKeyboardButton("Rechazar", callback_data="rechazar:" + parada.id)

        # Un teclado es una lista de filas, y cada fila una lista de botones. Aquí, una sola fila con los dos botones
        teclado = InlineKeyboardMarkup([[boton_aprobar, boton_rechazar]])
        await mensaje.reply_text(escribir_propuesta(parada.value), reply_markup=teclado)
    else:
        await mensaje.reply_text(estado_final["respuesta"])


def crear_manejador(grafo, usuario_permitido):
    # Devuelve la función que se ejecuta con cada mensaje que llega al bot. Como los nodos en crear_grafo, la función de dentro "recuerda" el grafo y el usuario.

    # update trae el mensaje,quién lo envía, en qué chat y el texto, y context es un objeto con utilidades de la libreria (python-telegram-bot). Importante entender que es la libreria la que ejecuta la funcion y le da estas dos cosas de forma automatica.
    async def responder(update, context):
        id_usuario = str(update.effective_user.id)

        if id_usuario != usuario_permitido:
            print("Mensaje ignorado del usuario", id_usuario)
            return

        pregunta = update.message.text
        configuracion = crear_configuracion(str(update.effective_chat.id))

        # Si había una propuesta esperando tus botones y escribes otra cosa, primero la rechazamos. Así se cierra bien (con cerrar_propuesta) y la conversación queda en orden para el mensaje nuevo. Sus botones ya no harán nada
        estado = await grafo.aget_state(configuracion)
        if len(estado.interrupts) > 0:
            await grafo.ainvoke(Command(resume=False), configuracion)

        estado_final = await grafo.ainvoke({"pregunta": pregunta}, configuracion)

        # Enviamos al mismo chat la respuesta, o la propuesta con botones si el grafo se ha parado a pedir aprobación
        await contestar(estado_final, update.message)

    return responder


def crear_manejador_de_botones(grafo, usuario_permitido):
    # Devuelve la función que se ejecuta cuando pulsas Aprobar o Rechazar. Es el equivalente al "(s/n)" de la terminal.
    # El grafo no está esperando en ningún sitio, la pausa está guardada en la memoria (Postgres). Por eso funciona aunque pulses el botón horas después, o con el bot reiniciado
    async def pulsar_boton(update, context):
        boton = update.callback_query

        # Telegram espera que contestemos a cada pulsación, si no, el botón se queda "cargando" en el móvil
        await boton.answer()

        # Igual que con los mensajes, solo tú puedes aprobar. Un botón lo puede pulsar cualquiera que vea el mensaje (por ejemplo, si algún día el bot está en un grupo)
        id_usuario = str(update.effective_user.id)
        if id_usuario != usuario_permitido:
            print("Botón ignorado del usuario", id_usuario)
            return

        # boton.data es el callback_data del botón, por ejemplo "aprobar:dd92045...". split(":") lo parte en ["aprobar", "dd92045..."]
        partes = boton.data.split(":")
        decision = partes[0]
        id_de_la_parada = partes[1]

        # Quitamos los botones del mensaje, para que no se puedan pulsar otra vez
        await boton.edit_message_reply_markup(reply_markup=None)

        configuracion = crear_configuracion(str(update.effective_chat.id))

        # Comprobamos que la propuesta de este botón es la que está pendiente ahora. Si después escribiste otra cosa, esa propuesta se descartó, y un botón viejo podría aprobar otra propuesta distinta
        estado = await grafo.aget_state(configuracion)
        sigue_pendiente = False
        for parada in estado.interrupts:
            if parada.id == id_de_la_parada:
                sigue_pendiente = True

        if sigue_pendiente is False:
            await boton.message.reply_text(TEXTO_PROPUESTA_CADUCADA)
            return

        if decision == "aprobar":
            aprobada = True
        else:
            aprobada = False

        # Igual que en la terminal, Command(resume=...) despierta al grafo donde se paró
        estado_final = await grafo.ainvoke(Command(resume=aprobada), configuracion)
        await contestar(estado_final, boton.message)

    return pulsar_boton


async def preparar_asistente(aplicacion):
    # Se ejecuta una vez al arrancar el bot.Monta el asistente y le da al bot la regla para atender mensajes.
    
    # Por qué aquí y no en main: la conexión con Postgres pertenece al "bucle async" en el que se abre, y run_polling crea el suyo propio. Si la abriéramos antes con asyncio.run, quedaría en un bucle que ya no existe y fallaría con el primer mensaje. post_init se ejecuta dentro del bucle del bot, así que todo vive en el mismo.
    modelo = crear_llm("fast")
    herramientas = await cargar_herramientas_mcp()
    memoria = await abrir_memoria()
    grafo = crear_grafo(modelo, herramientas, memoria=memoria)

    # Esto crea una regla, cuando llegue un mensaje de texto al bot de telegram, ejecuta la funcion (el manejador)
    manejador = crear_manejador(grafo, settings.telegram_user_id)
    aplicacion.add_handler(MessageHandler(filters.TEXT, manejador))  # Le entrega la regla al bot cada vez que recoja un mensaje

    # La segunda regla, cuando pulses un botón, ejecuta pulsar_boton
    manejador_de_botones = crear_manejador_de_botones(grafo, settings.telegram_user_id)
    aplicacion.add_handler(CallbackQueryHandler(manejador_de_botones))


def main():
    if settings.telegram_bot_token == "" or settings.telegram_user_id == "":
        print("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_USER_ID en el .env")
        return


    #CREACION DE BOT 

    # La aplicación de python-telegram-bot se conecta a Telegram con el token del bot.
    # post_init le dice qué función ejecutar al arrancar, antes de empezar a recoger mensajes (ver preparar_asistente).
    constructor = Application.builder().token(settings.telegram_bot_token)
    constructor = constructor.post_init(preparar_asistente)
    aplicacion = constructor.build()

    print("Bot en marcha. Escríbele desde Telegram (Ctrl+C para parar).")

    # Se queda preguntando a Telegram por mensajes nuevos hasta que lo paras
    aplicacion.run_polling()


if __name__ == "__main__":
    main()
