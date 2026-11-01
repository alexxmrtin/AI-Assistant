# Servidor MCP del calendario.
#
# Es un programa aparte que ofrece herramientas siguiendo el estándar MCP. El asistente
# (el cliente, ver cliente_mcp.py) lo arranca como un proceso hijo y le habla por la
# entrada y salida estándar (stdio), con mensajes JSON.
#
# Tiene dos fuentes de eventos y CALENDAR_BACKEND (en el .env) elige cuál usar:
#   demo   -> la agenda inventada de abajo (la usan los tests)
#   google -> tu Google Calendar (ver google_calendar.py)

from mcp.server.fastmcp import FastMCP

from asistente_ia.config import settings
from asistente_ia.google_calendar import listar_eventos_google

# El servidor. "calendar" es el nombre con el que se presenta a los clientes.
# log_level="WARNING" hace que solo escriba avisos y errores, no cada petición que recibe.
servidor = FastMCP("calendar", log_level="WARNING")

# Agenda inventada para probar. La semana va del lunes 2 al domingo 8 de noviembre de 2026.
AGENDA_DE_PRUEBA = [
    {"titulo": "Clase de Redes", "fecha": "2026-11-02", "inicio": "09:00", "fin": "11:00"},
    {"titulo": "Dentista", "fecha": "2026-11-03", "inicio": "17:30", "fin": "18:00"},
    {"titulo": "Reunión del TFG", "fecha": "2026-11-05", "inicio": "10:00", "fin": "11:00"},
    {"titulo": "Gimnasio", "fecha": "2026-11-05", "inicio": "19:00", "fin": "20:30"},
    {"titulo": "Cena con Laura", "fecha": "2026-11-06", "inicio": "21:00", "fin": "23:00"},
]


# @servidor.tool registra la función como herramienta del servidor. Hace lo mismo que el
# @tool de LangChain del paso 3, pero para MCP. La descripción es lo que leerá el modelo.
@servidor.tool(
    description=(
        "Devuelve los eventos del calendario entre dos fechas, ambas incluidas. "
        "Las fechas van en formato AAAA-MM-DD, por ejemplo 2026-11-05."
    )
)
def list_events(fecha_inicio: str, fecha_fin: str) -> list:
    if settings.calendar_backend == "google":
        return listar_eventos_google(fecha_inicio, fecha_fin)
    else:
        return listar_eventos_demo(fecha_inicio, fecha_fin)


def listar_eventos_demo(fecha_inicio, fecha_fin):
    eventos_encontrados = []

    for evento in AGENDA_DE_PRUEBA:
        # Las fechas AAAA-MM-DD se pueden comparar como texto:
        # "2026-11-03" es menor que "2026-11-05", igual que en el calendario.
        if fecha_inicio <= evento["fecha"] and evento["fecha"] <= fecha_fin:
            eventos_encontrados.append(evento)

    return eventos_encontrados


if __name__ == "__main__":
    # Arranca el servidor por stdio: se queda escuchando hasta que el cliente lo cierra.
    servidor.run()
