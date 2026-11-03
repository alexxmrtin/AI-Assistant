import asyncio

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.google_calendar import convertir_evento
from asistente_ia.mcp_calendar import listar_eventos_demo


def test_devuelve_los_eventos_del_jueves():
    eventos = listar_eventos_demo("2026-11-05", "2026-11-05")

    titulos = []
    for evento in eventos:
        titulos.append(evento["titulo"])

    assert titulos == ["Reunión del TFG", "Gimnasio"]


def test_un_dia_sin_eventos_devuelve_lista_vacia():
    eventos = listar_eventos_demo("2026-11-07", "2026-11-07")
    assert eventos == []


def test_el_rango_incluye_las_dos_fechas():
    eventos = listar_eventos_demo("2026-11-02", "2026-11-03")
    assert len(eventos) == 2


def test_el_cliente_trae_list_events_del_servidor(monkeypatch):
    monkeypatch.setitem(SERVIDORES["calendar"], "env", {"CALENDAR_BACKEND": "demo"})
    herramientas = asyncio.run(cargar_herramientas_mcp())

    herramientas_por_nombre = {}
    for herramienta in herramientas:
        herramientas_por_nombre[herramienta.name] = herramienta
    assert "list_events" in herramientas_por_nombre

    argumentos = {"fecha_inicio": "2026-11-05", "fecha_fin": "2026-11-05"}
    tarea_pendiente = herramientas_por_nombre["list_events"].ainvoke(argumentos)
    resultado = asyncio.run(tarea_pendiente)
    assert "Reunión del TFG" in str(resultado)
    assert "Gimnasio" in str(resultado)


def test_convierte_un_evento_con_hora():
    evento_de_google = {
        "summary": "Reunión del TFG",
        "start": {"dateTime": "2026-11-05T10:00:00+01:00"},
        "end": {"dateTime": "2026-11-05T11:00:00+01:00"},
    }
    evento = convertir_evento(evento_de_google)
    assert evento == {
        "titulo": "Reunión del TFG",
        "fecha": "2026-11-05",
        "inicio": "10:00",
        "fin": "11:00",
    }


def test_convierte_un_evento_de_todo_el_dia_sin_titulo():
    evento_de_google = {
        "start": {"date": "2026-11-07"},
        "end": {"date": "2026-11-08"},
    }
    evento = convertir_evento(evento_de_google)
    assert evento == {
        "titulo": "(sin título)",
        "fecha": "2026-11-07",
        "inicio": "todo el día",
        "fin": "",
    }
