from asistente_ia.evals import (
    CASOS_ACCION,
    CASOS_CALENDARIO,
    CASOS_CORREO,
    corregir,
    corregir_accion,
)

CASO_JUEVES = {
    "pregunta": "¿Qué tengo el jueves?",
    "debe_contener": ["tfg", "gimnasio"],
    "debe_contener_alguna": [],
    "debe_usar_herramienta": True,
}

CASO_GIMNASIO = {
    "pregunta": "¿A qué hora acaba el gimnasio el jueves?",
    "debe_contener": [],
    "debe_contener_alguna": ["20:30", "8:30"],
    "debe_usar_herramienta": True,
}


def test_una_respuesta_correcta_no_tiene_fallos():
    respuesta = "El jueves tienes la Reunión del TFG a las 10:00 y Gimnasio a las 19:00."
    assert corregir(CASO_JUEVES, respuesta, True) == []


def test_detecta_una_palabra_que_falta():
    respuesta = "El jueves tienes la Reunión del TFG."
    assert corregir(CASO_JUEVES, respuesta, True) == ["falta 'gimnasio'"]


def test_basta_con_una_de_las_alternativas():
    respuesta = "Acaba a las 8:30 de la tarde."
    assert corregir(CASO_GIMNASIO, respuesta, True) == []


def test_detecta_que_no_uso_ninguna_herramienta():
    respuesta = "El jueves tienes la Reunión del TFG y Gimnasio."
    assert corregir(CASO_JUEVES, respuesta, False) == ["no usó ninguna herramienta"]


CASO_DENTISTA = {
    "pregunta": "Mueve el dentista al miércoles a la misma hora",
    "debe_proponer": "move_event",
    "datos_deben_contener": ["e2", "2026-11-04", "17:30"],
}


def test_hay_treinta_casos():
    assert len(CASOS_CALENDARIO) == 10
    assert len(CASOS_CORREO) == 8
    assert len(CASOS_ACCION) == 12


def test_una_propuesta_correcta_no_tiene_fallos():
    propuesta = {
        "herramienta": "move_event",
        "argumentos": {"id_evento": "e2", "fecha": "2026-11-04", "inicio": "17:30", "fin": "18:00"},
    }
    assert corregir_accion(CASO_DENTISTA, propuesta) == []


def test_detecta_que_no_propuso_nada():
    assert corregir_accion(CASO_DENTISTA, None) == ["no propuso ninguna acción (no pidió aprobación)"]


def test_detecta_otra_herramienta_y_datos_que_faltan():
    propuesta = {"herramienta": "delete_event", "argumentos": {"id_evento": "e2"}}
    fallos = corregir_accion(CASO_DENTISTA, propuesta)
    assert fallos == [
        "propuso delete_event en vez de move_event",
        "en los datos falta '2026-11-04'",
        "en los datos falta '17:30'",
    ]
