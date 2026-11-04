# Google Calendar, consultar eventos, leer uno, crearlo, moverlo y borrarlo.

# Lo usa el servidor MCP (mcp_calendar.py) cuando CALENDAR_BACKEND=google.

# El inicio de sesión con Google está en google_auth.py (lo comparte con Gmail).

from datetime import datetime
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build  # crea el objeto para usar la API de Calendar
from googleapiclient.errors import HttpError  # el error que lanza Google si falla

from asistente_ia.google_auth import cargar_credenciales

# Zona horaria en la que pedimos y recibimos las horas de los eventos.
ZONA_HORARIA = "Europe/Madrid"


def convertir_evento(evento_de_google):
    # Google devuelve cada evento con muchos campos. Nos quedamos con los mismos que tiene la agenda de prueba, para que el modelo los reciba igual venga de donde venga.
    
    # Ejemplo de lo que llega de Google:
    # {
    #     "id": "4k2j9...",
    #     "summary": "Reunión del TFG",
    #     "start": {"dateTime": "2026-11-05T10:00:00+01:00"},
    #     "end": {"dateTime": "2026-11-05T11:00:00+01:00"},
    # }

    if "summary" in evento_de_google:
        titulo = evento_de_google["summary"]
    else:
        titulo = "(sin título)"

    inicio = evento_de_google["start"]
    fin = evento_de_google["end"]

    # Los eventos de todo el día traen "date" en vez de "dateTime": {"date": "2026-11-05"}
    if "dateTime" in inicio:
        fecha = inicio["dateTime"][0:10]
        hora_inicio = inicio["dateTime"][11:16]
        hora_fin = fin["dateTime"][11:16]
    else:
        fecha = inicio["date"]
        hora_inicio = "todo el día"
        hora_fin = ""

    return {"id": evento_de_google["id"], "titulo": titulo, "fecha": fecha, "inicio": hora_inicio, "fin": hora_fin}

# Crea el objeto que vamos a usar para comunicarnos con la API de google
def crear_servicio():
    credenciales = cargar_credenciales()

    return build("calendar", "v3", credentials=credenciales)


def listar_eventos_google(fecha_inicio, fecha_fin):
    servicio = crear_servicio()

    # Google quiere el rango con hora y zona horaria.
    zona = ZoneInfo(ZONA_HORARIA)
    desde = datetime.fromisoformat(fecha_inicio + "T00:00:00").replace(tzinfo=zona)
    hasta = datetime.fromisoformat(fecha_fin + "T23:59:59").replace(tzinfo=zona)

    # "primary" es tu calendario principal. singleEvents separa los eventos que se repiten (por ejemplo, cada lunes) en eventos sueltos, y orderBy los ordena por hora.
    peticion = servicio.events().list(
        calendarId="primary",
        timeMin=desde.isoformat(),
        timeMax=hasta.isoformat(),
        timeZone=ZONA_HORARIA,
        singleEvents=True,
        orderBy="startTime",
    )
    respuesta = peticion.execute()

    eventos_encontrados = []
    for evento_de_google in respuesta["items"]:
        eventos_encontrados.append(convertir_evento(evento_de_google))

    return eventos_encontrados

# Lee un determinado evento dado un id
def leer_evento_google(id_evento):
    servicio = crear_servicio()
    peticion = servicio.events().get(calendarId="primary", eventId=id_evento)
    try:
        evento_de_google = peticion.execute()
    except HttpError:
        # Igual que en la agenda de prueba, un mensaje claro para que el modelo pueda corregirse
        return {"error": "No existe ningún evento con el id " + id_evento + ". Usa list_events para ver los ids."}
    return convertir_evento(evento_de_google)

# Helper para unificar la fecha y hora juntas
def crear_hora(fecha, hora):
    # Google quiere la fecha y la hora juntas ("2026-11-05T17:30:00") y la zona horaria aparte
    return {"dateTime": fecha + "T" + hora + ":00", "timeZone": ZONA_HORARIA}


# Llamamos a la API de google para que nos cree un evento usando .insert(), devuelve un string de confirmacion
def crear_evento_google(titulo, fecha, inicio, fin):
    servicio = crear_servicio()
    evento = {
        "summary": titulo,
        "start": crear_hora(fecha, inicio),
        "end": crear_hora(fecha, fin),
    }
    peticion = servicio.events().insert(calendarId="primary", body=evento)
    peticion.execute()
    return "Evento creado: " + titulo + " el " + fecha + " de " + inicio + " a " + fin


# Modificamos un evento para cambia la hora de inicio y de fin, se usa .patch()
def mover_evento_google(id_evento, fecha, inicio, fin):
    servicio = crear_servicio()

    # patch solo cambia los campos que le mandamos (el inicio y el fin)
    cambios = {
        "start": crear_hora(fecha, inicio),
        "end": crear_hora(fecha, fin),
    }
    peticion = servicio.events().patch(calendarId="primary", eventId=id_evento, body=cambios)
    evento_de_google = peticion.execute()
    return "Evento movido: " + evento_de_google["summary"] + " ahora es el " + fecha + " de " + inicio + " a " + fin


# Usamos la API para borrar un evento usando .delete()
def borrar_evento_google(id_evento):
    servicio = crear_servicio()
    peticion = servicio.events().delete(calendarId="primary", eventId=id_evento)
    peticion.execute()
    return "Evento borrado"

