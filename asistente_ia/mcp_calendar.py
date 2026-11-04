# Servidor MCP del calendario.
#
# Es un programa aparte que ofrece herramientas siguiendo el estándar MCP. El asistente
# (el cliente, ver cliente_mcp.py) lo arranca como un proceso hijo y le habla por la
# entrada y salida estándar (stdio), con mensajes JSON.
#
# Tiene dos fuentes de eventos y CALENDAR_BACKEND (en el .env) elige cuál usar:
#   demo   -> la agenda inventada de abajo (la usan los tests)
#   google -> tu Google Calendar (ver google_calendar.py)
#
# Herramientas de lectura, list_events y get_event.
# Herramientas de escritura, create_event, move_event y delete_event. El agente nunca las recibe, solo las usa el grafo después de que apruebes (ver grafo.py)

from mcp.server.fastmcp import FastMCP

from asistente_ia.config import settings
from asistente_ia.google_calendar import (
    borrar_evento_google,
    crear_evento_google,
    leer_evento_google,
    listar_eventos_google,
    mover_evento_google,
)

# El servidor. "calendar" es el nombre con el que se presenta a los clientes.
# log_level="WARNING" hace que solo escriba avisos y errores, no cada petición que recibe.
servidor = FastMCP("calendar", log_level="WARNING")

# Agenda inventada para probar. La semana va del lunes 2 al domingo 8 de noviembre de 2026.
# Cada evento tiene un id, igual que en Google, para poder moverlo o borrarlo.
AGENDA_DE_PRUEBA = [
    {"id": "e1", "titulo": "Clase de Redes", "fecha": "2026-11-02", "inicio": "09:00", "fin": "11:00"},
    {"id": "e2", "titulo": "Dentista", "fecha": "2026-11-03", "inicio": "17:30", "fin": "18:00"},
    {"id": "e3", "titulo": "Reunión del TFG", "fecha": "2026-11-05", "inicio": "10:00", "fin": "11:00"},
    {"id": "e4", "titulo": "Gimnasio", "fecha": "2026-11-05", "inicio": "19:00", "fin": "20:30"},
    {"id": "e5", "titulo": "Cena con Laura", "fecha": "2026-11-06", "inicio": "21:00", "fin": "23:00"},
]


# @servidor.tool registra la función como herramienta del servidor. Hace lo mismo que el
# @tool de LangChain del paso 3, pero para MCP. La descripción es lo que leerá el modelo.
@servidor.tool(
    description=(
        "Devuelve los eventos del calendario entre dos fechas, ambas incluidas, con su id. "
        "Las fechas van en formato AAAA-MM-DD, por ejemplo 2026-11-05."
    )
)
def list_events(fecha_inicio: str, fecha_fin: str) -> list:
    if settings.calendar_backend == "google":
        return listar_eventos_google(fecha_inicio, fecha_fin)
    else:
        return listar_eventos_demo(fecha_inicio, fecha_fin)


@servidor.tool(description="Devuelve un evento (id, título, fecha, inicio y fin) a partir de su id, que se obtiene con list_events.")
def get_event(id_evento: str) -> dict:
    if settings.calendar_backend == "google":
        return leer_evento_google(id_evento)
    else:
        return leer_evento_demo(id_evento)


@servidor.tool(
    description=(
        "Crea un evento en el calendario. NO se crea hasta que la persona lo apruebe. "
        "fecha en formato AAAA-MM-DD, inicio y fin en formato HH:MM (24 horas), por ejemplo 17:30."
    )
)
def create_event(titulo: str, fecha: str, inicio: str, fin: str) -> str:
    if settings.calendar_backend == "google":
        return crear_evento_google(titulo, fecha, inicio, fin)
    else:
        return "Evento creado (demo): " + titulo + " el " + fecha + " de " + inicio + " a " + fin


@servidor.tool(
    description=(
        "Cambia la fecha y la hora de un evento que ya existe. NO se cambia hasta que la persona lo apruebe. "
        "id_evento lo da list_events. fecha en formato AAAA-MM-DD, inicio y fin en formato HH:MM."
    )
)
def move_event(id_evento: str, fecha: str, inicio: str, fin: str) -> str:
    if settings.calendar_backend == "google":
        return mover_evento_google(id_evento, fecha, inicio, fin)
    else:
        return "Evento movido (demo) al " + fecha + " de " + inicio + " a " + fin


@servidor.tool(description="Borra un evento del calendario. NO se borra hasta que la persona lo apruebe. id_evento lo da list_events.")
def delete_event(id_evento: str) -> str:
    if settings.calendar_backend == "google":
        return borrar_evento_google(id_evento)
    else:
        return "Evento borrado (demo): " + id_evento


# Funciones para los tests (y la demo).
# Igual que en el correo, la demo no guarda los cambios, cada llamada arranca el servidor de cero. Las de escritura solo devuelven un texto, y aquí no se puede usar print (rompería el stdio)

def listar_eventos_demo(fecha_inicio, fecha_fin):
    eventos_encontrados = []

    for evento in AGENDA_DE_PRUEBA:
        # Las fechas AAAA-MM-DD se pueden comparar como texto:
        # "2026-11-03" es menor que "2026-11-05", igual que en el calendario.
        if fecha_inicio <= evento["fecha"] and evento["fecha"] <= fecha_fin:
            eventos_encontrados.append(evento)

    return eventos_encontrados


def leer_evento_demo(id_evento):
    for evento in AGENDA_DE_PRUEBA:
        if evento["id"] == id_evento:
            return evento

    # Igual que con los correos, un mensaje claro en vez de fallar
    return {"error": "No existe ningún evento con el id " + id_evento + ". Usa list_events para ver los ids."}


if __name__ == "__main__":
    # Arranca el servidor por stdio
    servidor.run()
