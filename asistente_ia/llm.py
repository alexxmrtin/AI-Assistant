# Se configura en variables que va a usar el asistente (el programa) los modelos LLM. 
# Es decir, dependiendo de la funcion o tarea que queramos hacer usaremos dos tipos de modelos diferentes en tres variables, fast y smart.

# El fast para tareas sencillas, el smart para tareas complejas. Todo esto se configura en el .env , 
# se lee aqui y se crea el modelo dependiendo del proveedor asignado a cada uno.

from asistente_ia.config import settings as settings_del_env  # Traemos las variables de entorno

# Modelos por defecto. Se cambian sin tocar código con LLM_MODEL_FAST y LLM_MODEL_SMART.
MODELOS_POR_DEFECTO = {
    "anthropic": {"fast": "claude-haiku-5-5", "smart": "claude-sonnet-5-5"},
    "google": {"fast": "gemini-2.5-flash", "smart": "gemini-2.5-pro"},
    "ollama": {"fast": "qwen3:8b", "smart": "qwen3:8b"},
    "groq": {"fast": "llama-3.3-70b-versatile", "smart": "llama-3.3-70b-versatile"},
}



def nombre_modelo(tipo, settings):
    # Primero miramos si en el .env se eligió un modelo concreto para este tipo.
    if tipo == "fast":
        modelo_del_env = settings.llm_model_fast
    else:
        modelo_del_env = settings.llm_model_smart

    # Si se eligió uno, se usa ese.
    if modelo_del_env != "":
        return modelo_del_env

    # Si la variable está vacía, se usa el modelo por defecto del proveedor.
    modelos_del_proveedor = MODELOS_POR_DEFECTO[settings.llm_provider]
    return modelos_del_proveedor[tipo]


def crear_llm(tipo="fast", settings=None):

    if settings is None:
        settings = settings_del_env

    proveedor = settings.llm_provider

    if proveedor not in MODELOS_POR_DEFECTO:
        raise ValueError("LLM_PROVIDER no válido: " + proveedor)

    modelo = nombre_modelo(tipo, settings)

    # Cada import va dentro de su if para no cargar las librerías de los proveedores que no se usan.
    # temperature=0 hace que las respuestas sean lo más estables posible.
    if proveedor == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=modelo,
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=1024,
        )

    if proveedor == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=modelo,
            google_api_key=settings.google_api_key,
            temperature=0,
        )

    if proveedor == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=modelo,
            base_url=settings.ollama_base_url,
            temperature=0,
        )

    if proveedor == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=modelo,
            api_key=settings.groq_api_key,
            temperature=0,
            max_tokens=1024,
        )
