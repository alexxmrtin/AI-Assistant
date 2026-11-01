# Trazas con Langfuse: cada pregunta deja un registro de todo lo que pasó por dentro.

# LangChain y LangGraph avisan de cada paso (cada nodo, cada llamada al modelo, cada
# herramienta) a unos objetos llamados "callbacks". El callback de Langfuse recoge esos
# avisos y los envía a Langfuse, donde los ves como un árbol con tiempos, tokens y coste.

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from asistente_ia.config import settings as settings_del_env


def crear_callbacks(settings=None):
    if settings is None:
        settings = settings_del_env

    # Sin claves de Langfuse, el asistente funciona igual pero no envía trazas.
    if settings.langfuse_public_key == "" or settings.langfuse_secret_key == "":
        return []

    # Conectamos con Langfuse usando las claves del .env.
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    # El callback que recoge los avisos del grafo y los manda a esa conexión.
    callback_de_langfuse = CallbackHandler(public_key=settings.langfuse_public_key) # Importante CallbackHanlder usa la sesion iniciada antes en Langfuse, por eso usa la public key
    return [callback_de_langfuse]
