# Inicio de sesión con Google (OAuth), común para Google Calendar y Gmail.

# Iniciar sesión: python -m asistente_ia.google_auth
# Se abre el navegador, aceptas los permisos y se guarda el token en secrets/token.json. Solo una vez

import os

from google.auth.exceptions import RefreshError  # el error cuando no se puede renovar
from google.auth.transport.requests import Request  # para renovar el token caducado
from google.oauth2.credentials import Credentials  # lee el token.json guardado
from google_auth_oauthlib.flow import InstalledAppFlow  # inicio de sesión en el navegador

# Permisos (scopes) que pedimos a Google. No son urls que se visiten, son los nombres de los permisos.
# calendar.events permite ver, crear, cambiar y borrar eventos (sustituye a calendar.readonly). gmail.readonly es de solo lectura. gmail.compose permite crear borradores y enviarlos (pero no borrar correos)
PERMISOS = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

# credentials.json identifica a nuestra app ante Google.
# token.json es la llave que nos da Google al iniciar sesión. El token caduca cada hora, cargar_credenciales() lo actualiza solo hasta pasados 7 dias
RUTA_CREDENCIALES = "secrets/credentials.json"
RUTA_SESION = "secrets/token.json"

COMANDO_PARA_INICIAR_SESION = "python -m asistente_ia.google_auth"


def iniciar_sesion():
    # Abre el navegador con la página de Google para aceptar los permisos.
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
            "No hay sesión de Google. Ejecuta primero: " + COMANDO_PARA_INICIAR_SESION
        )

    # Sin pasarle los permisos, lee del token.json los permisos que aceptaste de verdad al iniciar sesión.
    credenciales = Credentials.from_authorized_user_file(RUTA_SESION)

    # Si añadimos un permiso nuevo (como gmail.readonly en este paso), el token antiguo no lo tiene y Google rechazaría la petición. Lo comprobamos aquí para dar un mensaje claro.
    if not credenciales.has_scopes(PERMISOS):
        raise RuntimeError(
            "La sesión de Google no tiene todos los permisos que necesita el asistente. Vuelve a ejecutar: "
            + COMANDO_PARA_INICIAR_SESION
        )

    # El token tiene dos partes: una llave de acceso que caduca cada hora y otra para renovarla (refresh token). Si la de acceso ha caducado, pedimos una nueva a Google sin volver a abrir el navegador, y la guardamos.
    if not credenciales.valid:
        # Si el refresh token también ha caducado (en modo Prueba, a los 7 días), Google lanza RefreshError. Lo recogemos para dar un mensaje claro que el modelo pueda transmitirte, en vez del error técnico de Google.
        try:
            credenciales.refresh(Request())
        except RefreshError:
            raise RuntimeError(
                "La sesión de Google ha caducado. Vuelve a ejecutar: " + COMANDO_PARA_INICIAR_SESION
            ) from None
        guardar_token(credenciales)

    return credenciales


if __name__ == "__main__":
    iniciar_sesion()
