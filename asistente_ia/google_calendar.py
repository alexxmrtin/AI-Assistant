# Lectura de Google Calendar: la consulta de eventos.
#
# Lo usa el servidor MCP (mcp_calendar.py) cuando CALENDAR_BACKEND=google.
#
# El inicio de sesión con Google está en google_auth.py (lo comparte con Gmail).

from datetime import datetime
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build  # crea el objeto para usar la API de Calendar

from asistente_ia.google_auth import cargar_credenciales

# Zona horaria en la que pedimos y recibimos las horas de los eventos.
ZONA_HORARIA = "Europe/Madrid"


def convertir_evento(evento_de_google):
    # Google devuelve cada evento con muchos campos. Nos quedamos con los mismos que tiene la agenda de prueba, para que el modelo los reciba igual venga de donde venga.
    
    # Ejemplo de lo que llega de Google:
    # {
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

    return {"titulo": titulo, "fecha": fecha, "inicio": hora_inicio, "fin": hora_fin}


def listar_eventos_google(fecha_inicio, fecha_fin):
    credenciales = cargar_credenciales()

    # build crea un objeto para hablar con la API de Google Calendar.Uso version 3
    servicio = build("calendar", "v3", credentials=credenciales)

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

