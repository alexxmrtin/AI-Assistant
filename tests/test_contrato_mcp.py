import asyncio

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.grafo import HERRAMIENTAS_DE_ESCRITURA, HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER

# El contrato, lo que el grafo espera de cada servidor MCP, herramienta por herramienta, con sus argumentos obligatorios
CONTRATO_CALENDARIO = {
    "list_events": ["fecha_inicio", "fecha_fin"],
    "get_event": ["id_evento"],
    "create_event": ["titulo", "fecha", "inicio", "fin"],
    "move_event": ["id_evento", "fecha", "inicio", "fin"],
    "delete_event": ["id_evento"],
}

CONTRATO_CORREO = {
    "search_emails": ["texto"],
    "read_email": ["id_correo"],
    "create_draft": ["para", "asunto", "texto"],
    "send_draft": ["id_borrador"],
}


# Arranca los dos servidores de verdad (en modo demo) y pregunta, como haría el asistente, qué herramientas anuncian. Devuelve {nombre: argumentos obligatorios}
def leer_lo_que_anuncian(monkeypatch):
    monkeypatch.setitem(SERVIDORES["calendar"], "env", {"CALENDAR_BACKEND": "demo"})
    monkeypatch.setitem(SERVIDORES["correo"], "env", {"CORREO_BACKEND": "demo"})
    herramientas = asyncio.run(cargar_herramientas_mcp())

    anunciadas = {}
    for herramienta in herramientas:
        # args_schema es la descripción de los argumentos que manda el servidor (un JSON Schema). "required" son los obligatorios
        anunciadas[herramienta.name] = herramienta.args_schema["required"]
    return anunciadas


def test_el_servidor_del_calendario_cumple_el_contrato(monkeypatch):
    anunciadas = leer_lo_que_anuncian(monkeypatch)
    for nombre in CONTRATO_CALENDARIO:
        assert nombre in anunciadas, "falta la herramienta " + nombre
        assert anunciadas[nombre] == CONTRATO_CALENDARIO[nombre], "cambian los argumentos de " + nombre


def test_el_servidor_del_correo_cumple_el_contrato(monkeypatch):
    anunciadas = leer_lo_que_anuncian(monkeypatch)
    for nombre in CONTRATO_CORREO:
        assert nombre in anunciadas, "falta la herramienta " + nombre
        assert anunciadas[nombre] == CONTRATO_CORREO[nombre], "cambian los argumentos de " + nombre


def test_no_hay_herramientas_fuera_del_contrato(monkeypatch):
    # Si un servidor anuncia una herramienta nueva, el agente la recibiría sin que nadie lo decida. Este test obliga a añadirla aquí a propósito
    anunciadas = leer_lo_que_anuncian(monkeypatch)
    for nombre in anunciadas:
        assert nombre in CONTRATO_CALENDARIO or nombre in CONTRATO_CORREO, "herramienta nueva sin contrato " + nombre


def test_las_listas_de_escritura_del_grafo_existen():
    # Si se renombra una herramienta de escritura en un servidor y no en grafo.py, el grafo dejaría de reconocerla como escritura y el agente la recibiría. Este test lo evita
    for nombre in HERRAMIENTAS_DE_ESCRITURA:
        assert nombre in CONTRATO_CALENDARIO or nombre in CONTRATO_CORREO
    for nombre in HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER:
        assert nombre in HERRAMIENTAS_DE_ESCRITURA
