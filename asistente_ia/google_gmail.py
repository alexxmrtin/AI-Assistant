# Lectura de Gmail, buscar correos y leer uno entero.

# Lo usa el servidor MCP (mcp_correo.py) cuando CORREO_BACKEND=google.
# Devuelve los correos con la misma forma que la bandeja de prueba (mira mcp_correo), para que el modelo los reciba igual vengan de donde vengan.

import base64
from datetime import datetime
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
