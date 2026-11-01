# Lectura de Google Calendar: el inicio de sesión con Google (OAuth) y la consulta de eventos.
#
# Lo usa el servidor MCP (mcp_calendar.py) cuando CALENDAR_BACKEND=google.
#
# Iniciar sesión, solo la primera vez: python -m asistente_ia.google_calendar
# Se abre el navegador, aceptas el permiso y se guarda el token en secrets/token.json.

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError  # el error cuando no se puede renovar
from google.auth.transport.requests import Request  # para renovar el token caducado
from google.oauth2.credentials import Credentials  # lee el token.json guardado
from google_auth_oauthlib.flow import InstalledAppFlow  # inicio de sesión en el navegador
from googleapiclient.discovery import build  # crea el objeto para usar la API de Calendar

# Permiso que pedimos a Google: solo LEER el calendario. Con este permiso es imposible crear, cambiar o borrar eventos, aunque el modelo lo intentara
# No es una url es n permiso (se llama scope), le dice a google lo que queremos hacer
PERMISOS = ["https://www.googleapis.com/auth/calendar.readonly"]

# credentials.json identifica a nuestra app ante Google.
# token.json es la llave que nos da Google al iniciar sesión. El token caduca cada hora, cargar_credenciales() lo actualiza solo hasta pasados 7 dias
RUTA_CREDENCIALES = "secrets/credentials.json"
RUTA_SESION = "secrets/token.json"

# Zona horaria en la que pedimos y recibimos las horas de los eventos.
ZONA_HORARIA = "Europe/Madrid"


def iniciar_sesion():
    # Abre el navegador con la página de Google para aceptar el permiso.
    # run_local_server levanta un mini servidor web en tu equipo para recibir la respuesta.La libreria por dentro gestiona el async, no hace falta poner nada
    flujo = InstalledAppFlow.from_client_secrets_file(RUTA_CREDENCIALES, PERMISOS)
    credenciales = flujo.run_local_server(port=0)
    guardar_token(credenciales)
    print("Sesión iniciada. Token guardado en", RUTA_SESION)


def guardar_token(credenciales):
    with open(RUTA_SESION, "w") as fichero:
        fichero.write(credenciales.to_json())


def cargar_credenciales():
    if not os.path.exists(RUTA_SESION):
        raise RuntimeError(
            "No hay sesión de Google. Ejecuta primero: python -m asistente_ia.google_calendar"
        )

    credenciales = Credentials.from_authorized_user_file(RUTA_SESION, PERMISOS)

    # El token tiene dos partes: una llave de acceso que caduca cada hora y otra para renovarla (refresh token). Si la de acceso ha caducado, pedimos una nueva a Google sin volver a abrir el navegador, y la guardamos.
    if not credenciales.valid:
        # Si el refresh token también ha caducado (en modo Prueba, a los 7 días), Google lanza RefreshError. Lo recogemos para dar un mensaje claro que el modelo pueda transmitirte, en vez del error técnico de Google.
        try:
            credenciales.refresh(Request())
        except RefreshError:
            raise RuntimeError(
                "La sesión de Google ha caducado. Vuelve a ejecutar: "
                "python -m asistente_ia.google_calendar"
            ) from None
        guardar_token(credenciales)

    return credenciales


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


if __name__ == "__main__":
    iniciar_sesion()
