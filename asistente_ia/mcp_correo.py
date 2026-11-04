# Servidor MCP del correo.
#
# Un programa aparte que ofrece herramientas siguiendo el estándar MCP, el asistente lo arranca como proceso hijo y le habla por stdio (ver cliente_mcp.py).
#
# Tiene dos fuentes de correos y CORREO_BACKEND (en el .env) elige cuál usar:
#   demo   -> la bandeja de prueba de abajo (la usan los tests y las evals)
#   google -> tu Gmail (ver google_gmail.py)


# Tiene cuatro herramientas:
#   search_emails -> busca y devuelve solo un resumen de cada correo (quién, asunto, fecha), sin el texto
#   read_email    -> devuelve un correo entero, con su texto
#   create_draft  -> crea un borrador (no lo envía)
#   send_draft    -> envía un borrador que ya existe
# Así el modelo no recibe el texto de todos los correos de golpe (gastaría muchos tokens) y solo lee los que le interesan.
# Las dos últimas escriben: el agente nunca las recibe, solo las usa el grafo después de que apruebes (ver grafo.py).

from mcp.server.fastmcp import FastMCP

from asistente_ia.config import settings
from asistente_ia.google_gmail import (
    buscar_correos_google,
    crear_borrador_google,
    enviar_borrador_google,
    leer_correo_google,
)

servidor = FastMCP("correo", log_level="WARNING")

# Bandeja de prueba. Los correos son de la misma semana que la agenda de prueba (lunes 2 de noviembre de 2026).
# Cada correo tiene un id, igual que en Gmail, para poder pedir uno en concreto con read_email.
BANDEJA_DE_PRUEBA = [
    {
        "id": "c1",
        "de": "Laura Gómez <laura.gomez@gmail.com>",
        "asunto": "¿Quedamos esta semana?",
        "fecha": "2026-11-02 08:15",
        "texto": "¡Hola! Hace mucho que no nos vemos. ¿Te viene bien cenar el viernes por la noche? Si no, dime otro día. Un abrazo, Laura",
    },
    {
        "id": "c2",
        "de": "Secretaría ETSIIT <secretaria@etsiit.ugr.es>",
        "asunto": "Plazo de matrícula del TFG",
        "fecha": "2026-11-01 12:40",
        "texto": "Os recordamos que el plazo para matricular el Trabajo Fin de Grado termina el 15 de noviembre de 2026. El trámite se hace desde el Acceso Identificado.",
    },
    {
        "id": "c3",
        "de": "Carlos Ruiz <carlos.ruiz@ugr.es>",
        "asunto": "Reunión del TFG del jueves",
        "fecha": "2026-11-01 18:05",
        "texto": "Hola, Alejandro. Te confirmo la reunión del jueves a las 10:00 en mi despacho. Trae el índice de la memoria y una demo del bot si puedes. Un saludo, Carlos (tutor del TFG)",
    },
    {
        "id": "c4",
        "de": "Banco Sabadell <avisos@bancsabadell.com>",
        "asunto": "Tu recibo de noviembre",
        "fecha": "2026-11-01 07:00",
        "texto": "Ya tienes disponible tu recibo de noviembre en la app. Importe: 39,90 € (cuota del gimnasio).",
    },
    {
        "id": "c5",
        "de": "Amazon <envios@amazon.es>",
        "asunto": "Tu pedido ha sido enviado",
        "fecha": "2026-10-31 16:22",
        "texto": "Tu pedido de 'Teclado mecánico' ha salido del almacén. Entrega prevista: martes 3 de noviembre.",
    },
    {
        "id": "c6",
        "de": "GitHub <noreply@github.com>",
        "asunto": "[alexxmrtin/AI-Assistant] Run failed: CI - dev",
        "fecha": "2026-10-31 11:48",
        "texto": "The workflow run 'CI' failed on branch dev. Job 'tests' exited with code 1.",
    },
    {
        "id": "c7",
        "de": "Clínica Dental Sonrisa <citas@clinicasonrisa.es>",
        "asunto": "Recordatorio de cita",
        "fecha": "2026-10-30 10:00",
        "texto": "Le recordamos su cita el martes 3 de noviembre a las 17:30. Si no puede venir, llame al 958 000 000.",
    },
    {
        "id": "c8",
        "de": "Laura Gómez <laura.gomez@gmail.com>",
        "asunto": "Fotos del viaje",
        "fecha": "2026-10-28 21:30",
        "texto": "Te paso el enlace con las fotos de Sierra Nevada. ¡Qué bien lo pasamos!",
    },
]



@servidor.tool(
    description=(
        "Busca correos que contengan un texto en el remitente, el asunto o el mensaje. "
        "Devuelve solo un resumen de cada correo (id, de, asunto y fecha), del más reciente al más antiguo. "
        "Para ver el mensaje completo, usa read_email con el id. "
        "Si el texto está vacío, devuelve todos los correos."
    )
)
def search_emails(texto: str) -> list:
    if settings.correo_backend == "google":
        return buscar_correos_google(texto)
    else:
        return buscar_correos_demo(texto)


@servidor.tool(
    description="Devuelve un correo completo (de, asunto, fecha y texto) a partir de su id, que se obtiene con search_emails."
)
def read_email(id_correo: str) -> dict:
    if settings.correo_backend == "google":
        return leer_correo_google(id_correo)
    else:
        return leer_correo_demo(id_correo)


# responder_a: str = "" es un valor por defecto, si el modelo no lo rellena, vale "" (un correo nuevo, no una respuesta)
@servidor.tool(
    description=(
        "Crea un borrador de correo. NO lo envía, se enviará solo si la persona lo aprueba. "
        "para: la dirección de correo del destinatario. "
        "asunto: el asunto; si respondes a un correo, 'Re: ' más el asunto original. "
        "texto: el mensaje completo, listo para enviar. "
        "responder_a: si es una respuesta, el id del correo al que respondes (lo da search_emails); si es un correo nuevo, déjalo vacío. "
        "Devuelve el id del borrador."
    )
)
def create_draft(para: str, asunto: str, texto: str, responder_a: str = "") -> str:
    if settings.correo_backend == "google":
        return crear_borrador_google(para, asunto, texto, responder_a)
    else:
        return crear_borrador_demo(para, asunto, texto, responder_a)


@servidor.tool(description="Envía un borrador que ya existe, a partir de su id (el que devuelve create_draft).")
def send_draft(id_borrador: str) -> str:
    if settings.correo_backend == "google":
        return enviar_borrador_google(id_borrador)
    else:
        return enviar_borrador_demo(id_borrador)


# -----------------------–------------------------------------------------------------

# Funciones para los tests

def buscar_correos_demo(texto):
    texto_buscado = texto.lower() # psamos texto a minuscula
    resumenes = []

   # Para los tests
    for correo in BANDEJA_DE_PRUEBA:
        donde_buscar = correo["de"] + " " + correo["asunto"] + " " + correo["texto"]

        if texto_buscado in donde_buscar.lower():
            resumen = {
                "id": correo["id"],
                "de": correo["de"],
                "asunto": correo["asunto"],
                "fecha": correo["fecha"],
            }
            resumenes.append(resumen)

    return resumenes


def leer_correo_demo(id_correo):
    
    #para los tests
    for correo in BANDEJA_DE_PRUEBA:
        if correo["id"] == id_correo:
            return correo

    # Si el modelo pide un id que no existe, le respondemos con un mensaje claro en vez de fallar, para que pueda corregirse.
    mensaje = "No existe ningún correo con el id " + id_correo
    mensaje = mensaje + ". Usa search_emails para ver los ids."
    return {"error": mensaje}


# En la demo no se guarda nada: cada llamada a una herramienta arranca el servidor de cero, así que no podría recordar los borradores. Devolvemos un id inventado.
# Ojo: aquí no se puede usar print. El servidor habla con el asistente por stdio, y un print se mezclaría con los mensajes MCP y rompería la conversación
def crear_borrador_demo(para, asunto, texto, responder_a):
    return "borrador-demo"


def enviar_borrador_demo(id_borrador):
    return "Enviado (demo): " + id_borrador


if __name__ == "__main__":
    # Arranca el servidor por stdio
    servidor.run()
