# Gmail: buscar correos, leer uno entero, crear un borrador y enviarlo.

# Lo usa el servidor MCP (mcp_correo.py) cuando CORREO_BACKEND=google.
# Devuelve los correos con la misma forma que la bandeja de prueba (mira mcp_correo), para que el modelo los reciba igual vengan de donde vengan.

import base64
from datetime import datetime
from email.message import EmailMessage  # construye un correo (formato MIME); viene con Python
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build  # crea el objeto para usar la API de Gmail
from googleapiclient.errors import HttpError  # el error que lanza Google si falla

from asistente_ia.google_auth import cargar_credenciales

ZONA_HORARIA = "Europe/Madrid"

# Cuántos correos devuelve como mucho una búsqueda. Para minimizar tokens
MAXIMO_DE_CORREOS = 10

# Los correos largos se recortan a este número de letras para no llenar el contexto del modelo.
MAXIMO_DE_LETRAS = 3000


def crear_servicio():
    # build crea un objeto para hablar con la API de Gmail
    credenciales = cargar_credenciales()
    return build("gmail", "v1", credentials=credenciales)


def buscar_correos_google(texto):
    servicio = crear_servicio()

    # userId="me" es tu propia cuenta. q es la búsqueda, y funciona igual que la barra de búsqueda de Gmail: "laura" busca esa palabra en cualquier parte, y también vale "from:laura" o "is:unread"
    # Esta petición solo devuelve los ids de los correos, no su contenido.
    peticion = servicio.users().messages().list(userId="me", q=texto, maxResults=MAXIMO_DE_CORREOS)
    respuesta = peticion.execute()

    # Si no hay ningún resultado, Google no manda la clave "messages".
    if "messages" not in respuesta:
        return []

    resumenes = []
    for mensaje in respuesta["messages"]:
        # Por cada id pedimos solo las cabeceras que nos interesan (format="metadata"), sin el texto del correo.
        peticion = servicio.users().messages().get(
            userId="me",
            id=mensaje["id"],
            format="metadata",
            metadataHeaders=["From", "Subject"],
        )
        mensaje_de_google = peticion.execute()
        resumenes.append(convertir_resumen(mensaje_de_google))

    return resumenes


def leer_correo_google(id_correo):
    servicio = crear_servicio()

    # format="full" trae el correo entero: cabeceras y texto.
    peticion = servicio.users().messages().get(userId="me", id=id_correo, format="full")
    try:
        mensaje_de_google = peticion.execute()
    except HttpError:
        # Igual que en la bandeja de prueba: un mensaje claro para que el modelo pueda corregirse.
        mensaje = "No existe ningún correo con el id " + id_correo
        mensaje_final = mensaje + ". Usa search_emails para ver los ids."
        return {"error": mensaje_final}

    correo = convertir_resumen(mensaje_de_google)

    texto = sacar_texto(mensaje_de_google["payload"])
    # Si el correo no tiene parte de texto plano (solo HTML), usamos el "snippet" (comentario que enseña google en la bandeja de entrada).
    if texto == "":
        texto = mensaje_de_google["snippet"]
    if len(texto) > MAXIMO_DE_LETRAS:
        texto = texto[0:MAXIMO_DE_LETRAS] + "\n[... correo recortado ...]"

    correo["texto"] = texto
    return correo


def crear_borrador_google(para, asunto, texto, responder_a):
    servicio = crear_servicio()

    # Un correo por dentro es texto con cabeceras (To, Subject...) y el mensaje, EmailMessage lo monta por nosotros con el formato correcto. 
    # From no hace falta,Gmail pone tu dirección
    correo = EmailMessage()
    correo["To"] = para
    correo["Subject"] = asunto
    correo.set_content(texto)

    mensaje_para_google = {}

    # Cuando respondemos a un correo, necesitamos especificar a que conversacion estamos respondiendo, es decir, el conjunto de correo que tiene una conversacion en gmail.
    # Para ello "responder_a" va a tener el id del correo al que estamos respondiendo en la conversacion, con el vamos a sacar el id de la conversacion ("ThreadID") y el message-id que es el id global para servidores de correo (diferente a lo que viene en el parametro responder_a)
    if responder_a != "":
        peticion = servicio.users().messages().get(
            userId="me",
            id=responder_a,
            format="metadata",
            metadataHeaders=["Message-ID"],
        )
        original = peticion.execute()

        mensaje_para_google["threadId"] = original["threadId"]

        # Message-ID es el identificador único del correo original en internet. In-Reply-To y References lo usan los programas de correo de la otra persona (Outlook, el móvil...) para mostrarlo como respuesta
        for cabecera in original["payload"]["headers"]:
            if cabecera["name"].lower() == "message-id":
                correo["In-Reply-To"] = cabecera["value"]
                correo["References"] = cabecera["value"]

    # La API de Gmail recibe el correo entero codificado en base64
    correo_en_bytes = correo.as_bytes()
    mensaje_para_google["raw"] = base64.urlsafe_b64encode(correo_en_bytes).decode()

    # Esto no envia nada a google, de eso se encarga la funcion de abajo, esto lo que hace es crear un borrador en el servidor de google solamente
    peticion = servicio.users().drafts().create(userId="me", body={"message": mensaje_para_google})
    borrador = peticion.execute()
    return borrador["id"]

# Y esta funcion envia ese borrador que hemos creado arriba
def enviar_borrador_google(id_borrador):
    servicio = crear_servicio()
    peticion = servicio.users().drafts().send(userId="me", body={"id": id_borrador})
    peticion.execute()
    return "Enviado"


def convertir_resumen(mensaje_de_google):
    # Google devuelve las cabeceras como un diccionario:
    # {
    #     "id": "18c2f...",
    #     "internalDate": "1793603700000",
    #     "payload": {
    #         "headers": [
    #             {"name": "From", "value": "Laura Gómez <laura.gomez@gmail.com>"},
    #             {"name": "Subject", "value": "¿Quedamos esta semana?"},
    #         ]
    #     },
    # }
    de = ""
    asunto = "(sin asunto)"
    for cabecera in mensaje_de_google["payload"]["headers"]:
        if cabecera["name"] == "From":
            de = cabecera["value"]
        if cabecera["name"] == "Subject":
            asunto = cabecera["value"]

    # internalDate es el momento en que llegó el correo, en milisegundos desde el 1 de enero de 1970. Lo dividimos entre 1000 para tener segundos y lo pasamos a fecha en la hora de Madrid
    segundos = int(mensaje_de_google["internalDate"]) / 1000
    fecha = datetime.fromtimestamp(segundos, ZoneInfo(ZONA_HORARIA))

    return {
        "id": mensaje_de_google["id"],
        "de": de,
        "asunto": asunto,
        "fecha": fecha.strftime("%Y-%m-%d %H:%M"),
    }


def sacar_texto(parte):
    # Un correo está hecho de "partes" (formato MIME), por ejemplo, una versión en texto plano, otra en HTML y los adjuntos. Las partes pueden tener partes dentro
    # Buscamos la primera parte de texto plano (text/plain).
    if parte["mimeType"] == "text/plain" and "data" in parte["body"]:
        # Google manda el texto codificado en base64 (para viajar por internet). Lo decodificamos a bytes y después a texto.
        datos = base64.urlsafe_b64decode(parte["body"]["data"])
        return datos.decode("utf-8", errors="replace")

    # Si esta parte no es texto plano, miramos sus partes de dentro, una a una. La función se llama a sí misma con cada una.
    if "parts" in parte:
        for subparte in parte["parts"]:
            texto = sacar_texto(subparte)
            if texto != "":
                return texto

    return ""
