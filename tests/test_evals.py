from asistente_ia.evals import CASOS, corregir

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


def test_detecta_que_no_consulto_el_calendario():
    respuesta = "El jueves tienes la Reunión del TFG y Gimnasio."
    assert corregir(CASO_JUEVES, respuesta, False) == ["no consultó el calendario"]


def test_hay_diez_casos():
    assert len(CASOS) == 10
