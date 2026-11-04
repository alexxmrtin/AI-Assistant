import asyncio
import base64

from asistente_ia.cliente_mcp import SERVIDORES, cargar_herramientas_mcp
from asistente_ia.google_gmail import convertir_resumen, sacar_texto
from asistente_ia.mcp_correo import buscar_correos_demo, leer_correo_demo


def test_busca_los_correos_de_laura():
    resumenes = buscar_correos_demo("laura")

    ids = []
    for resumen in resumenes:
        ids.append(resumen["id"])

    assert ids == ["c1", "c8"]


def test_la_busqueda_no_distingue_mayusculas():
    assert buscar_correos_demo("LAURA") == buscar_correos_demo("laura")


def test_la_busqueda_no_devuelve_el_texto():
    resumenes = buscar_correos_demo("laura")
    assert "texto" not in resumenes[0]


def test_buscar_sin_texto_devuelve_todos():
    resumenes = buscar_correos_demo("")
    assert len(resumenes) == 8


def test_una_busqueda_sin_resultados_devuelve_lista_vacia():
    assert buscar_correos_demo("lotería") == []


def test_lee_un_correo_completo():
    correo = leer_correo_demo("c1")
    assert correo["asunto"] == "¿Quedamos esta semana?"
    assert "viernes" in correo["texto"]


def test_un_id_que_no_existe_devuelve_un_error():
    correo = leer_correo_demo("c99")
    assert "error" in correo


def test_el_cliente_trae_las_herramientas_del_correo(monkeypatch):
    monkeypatch.setitem(SERVIDORES["correo"], "env", {"CORREO_BACKEND": "demo"})
    herramientas = asyncio.run(cargar_herramientas_mcp())

    herramientas_por_nombre = {}
    for herramienta in herramientas:
        herramientas_por_nombre[herramienta.name] = herramienta

    assert "search_emails" in herramientas_por_nombre
    assert "read_email" in herramientas_por_nombre

    tarea_pendiente = herramientas_por_nombre["read_email"].ainvoke({"id_correo": "c1"})
    resultado = asyncio.run(tarea_pendiente)
    assert "viernes" in str(resultado)


def test_convierte_el_resumen_de_un_correo_de_google():
    mensaje_de_google = {
        "id": "18c2f",
        "internalDate": "1793603700000",
        "payload": {
            "headers": [
                {"name": "From", "value": "Laura Gómez <laura.gomez@gmail.com>"},
                {"name": "Subject", "value": "¿Quedamos esta semana?"},
            ]
        },
    }
    resumen = convertir_resumen(mensaje_de_google)
    assert resumen == {
        "id": "18c2f",
        "de": "Laura Gómez <laura.gomez@gmail.com>",
        "asunto": "¿Quedamos esta semana?",
        "fecha": "2026-11-02 08:15",
    }


def test_un_correo_sin_asunto():
    mensaje_de_google = {
        "id": "18c2f",
        "internalDate": "1793603700000",
        "payload": {"headers": [{"name": "From", "value": "alguien@ejemplo.com"}]},
    }
    resumen = convertir_resumen(mensaje_de_google)
    assert resumen["asunto"] == "(sin asunto)"


def test_saca_el_texto_plano_de_un_correo_con_varias_partes():
    texto_en_bytes = "¿Cenamos el viernes?".encode()
    texto_codificado = base64.urlsafe_b64encode(texto_en_bytes).decode()
    payload = {
        "mimeType": "multipart/alternative",
        "body": {},
        "parts": [
            {"mimeType": "text/plain", "body": {"data": texto_codificado}},
            {"mimeType": "text/html", "body": {"data": "PGI-aG9sYTwvYj4="}},
        ],
    }
    assert sacar_texto(payload) == "¿Cenamos el viernes?"


def test_un_correo_solo_html_no_tiene_texto_plano():
    payload = {"mimeType": "text/html", "body": {"data": "PGI-aG9sYTwvYj4="}}
    assert sacar_texto(payload) == ""


def test_el_cliente_trae_las_herramientas_de_escritura(monkeypatch):
    monkeypatch.setitem(SERVIDORES["correo"], "env", {"CORREO_BACKEND": "demo"})
    herramientas = asyncio.run(cargar_herramientas_mcp())

    herramientas_por_nombre = {}
    for herramienta in herramientas:
        herramientas_por_nombre[herramienta.name] = herramienta

    datos = {"para": "laura.gomez@gmail.com", "asunto": "Re: Hola", "texto": "¡Vale!"}
    resultado = asyncio.run(herramientas_por_nombre["create_draft"].ainvoke(datos))
    assert resultado[0]["text"] == "borrador-demo"

    resultado = asyncio.run(herramientas_por_nombre["send_draft"].ainvoke({"id_borrador": "borrador-demo"}))
    assert "Enviado" in resultado[0]["text"]
