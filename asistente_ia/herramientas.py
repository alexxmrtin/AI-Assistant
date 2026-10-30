# Tool-calling: Herramientas que el modelo puede pedir que ejecutemos.


from langchain_core.tools import tool

# Agenda inventada para probar. La semana va del lunes 2 al domingo 8 de noviembre de 2026.
AGENDA_DE_PRUEBA = [
    {"titulo": "Clase de Redes", "fecha": "2026-11-02", "inicio": "09:00", "fin": "11:00"},
    {"titulo": "Dentista", "fecha": "2026-11-03", "inicio": "17:30", "fin": "18:00"},
    {"titulo": "Reunión del TFG", "fecha": "2026-11-05", "inicio": "10:00", "fin": "11:00"},
    {"titulo": "Gimnasio", "fecha": "2026-11-05", "inicio": "19:00", "fin": "20:30"},
    {"titulo": "Cena con Laura", "fecha": "2026-11-06", "inicio": "21:00", "fin": "23:00"},
]


# @tool convierte la función en una herramienta que el modelo puede ver.
@tool(
    description=(
        "Devuelve los eventos del calendario entre dos fechas, ambas incluidas. "
        "Las fechas van en formato AAAA-MM-DD, por ejemplo 2026-11-05."
    )
)
def list_events(fecha_inicio: str, fecha_fin: str) -> list:
    eventos_encontrados = []

    for evento in AGENDA_DE_PRUEBA:
        # Las fechas AAAA-MM-DD se pueden comparar como texto:
        # "2026-11-03" es menor que "2026-11-05", igual que en el calendario.
        if fecha_inicio <= evento["fecha"] and evento["fecha"] <= fecha_fin:
            eventos_encontrados.append(evento)

    return eventos_encontrados
