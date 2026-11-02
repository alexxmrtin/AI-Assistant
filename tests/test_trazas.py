from asistente_ia.config import Settings
from asistente_ia.trazas import crear_callbacks


def test_sin_claves_no_hay_trazas():
    settings = Settings(_env_file=None, langfuse_public_key="", langfuse_secret_key="")
    assert crear_callbacks(settings) == []


def test_con_claves_se_crea_el_callback_de_langfuse():
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-lf-falsa",
        langfuse_secret_key="sk-lf-falsa",
    )
    callbacks = crear_callbacks(settings)
    assert len(callbacks) == 1
    assert type(callbacks[0]).__name__ == "LangchainCallbackHandler"
