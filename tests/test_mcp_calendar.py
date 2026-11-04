import asyncio

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.google_calendar import convertir_evento, crear_hora
from asistente_ia.mcp_calendar import leer_evento_demo, listar_eventos_demo


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
        "id": "4k2j9",
        "summary": "Reunión del TFG",
        "start": {"dateTime": "2026-11-05T10:00:00+01:00"},
        "end": {"dateTime": "2026-11-05T11:00:00+01:00"},
    }
    evento = convertir_evento(evento_de_google)
    assert evento == {
        "id": "4k2j9",
        "titulo": "Reunión del TFG",
        "fecha": "2026-11-05",
        "inicio": "10:00",
        "fin": "11:00",
    }


def test_convierte_un_evento_de_todo_el_dia_sin_titulo():
    evento_de_google = {
        "id": "8x7c1",
        "start": {"date": "2026-11-07"},
        "end": {"date": "2026-11-08"},
    }
    evento = convertir_evento(evento_de_google)
    assert evento == {
        "id": "8x7c1",
        "titulo": "(sin título)",
        "fecha": "2026-11-07",
        "inicio": "todo el día",
        "fin": "",
    }


def test_lee_un_evento_por_su_id():
    evento = leer_evento_demo("e2")
    assert evento["titulo"] == "Dentista"


def test_un_evento_que_no_existe_devuelve_un_error():
    evento = leer_evento_demo("e99")
    assert "error" in evento


def test_crea_la_hora_en_el_formato_de_google():
    assert crear_hora("2026-11-05", "17:30") == {"dateTime": "2026-11-05T17:30:00", "timeZone": "Europe/Madrid"}


def test_el_cliente_trae_las_herramientas_de_escritura_del_calendario(monkeypatch):
    monkeypatch.setitem(SERVIDORES["calendar"], "env", {"CALENDAR_BACKEND": "demo"})
    herramientas = asyncio.run(cargar_herramientas_mcp())

    herramientas_por_nombre = {}
    for herramienta in herramientas:
        herramientas_por_nombre[herramienta.name] = herramienta

    datos = {"titulo": "Dentista", "fecha": "2026-11-05", "inicio": "17:30", "fin": "18:00"}
    resultado = asyncio.run(herramientas_por_nombre["create_event"].ainvoke(datos))
    assert "Evento creado" in resultado[0]["text"]

    datos = {"id_evento": "e2", "fecha": "2026-11-04", "inicio": "17:30", "fin": "18:00"}
    resultado = asyncio.run(herramientas_por_nombre["move_event"].ainvoke(datos))
    assert "Evento movido" in resultado[0]["text"]

    resultado = asyncio.run(herramientas_por_nombre["delete_event"].ainvoke({"id_evento": "e2"}))
    assert "Evento borrado" in resultado[0]["text"]

    resultado = asyncio.run(herramientas_por_nombre["get_event"].ainvoke({"id_evento": "e2"}))
    assert "Dentista" in resultado[0]["text"]
