# Configuración del asistente, leída de variables de entorno o del fichero .env.

# Se usa pydantic para leer variables de entorno

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Lee también el fichero .env e ignora las variables que no aparezcan aquí.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"  # anthropic, google u ollama
    llm_model_fast: str = ""  # vacío = el modelo por defecto del proveedor
    llm_model_smart: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # De dónde lee los eventos el servidor MCP del calendario: demo o google.
    calendar_backend: str = "demo"

    # De dónde lee los correos el servidor MCP del correo: demo o google.
    correo_backend: str = "demo"

    # Dónde está la base de datos Postgres que guarda las conversaciones. Vacía = en RAM (se pierden al cerrar).
    database_url: str = ""

    # Telegram: el token del bot (te lo da @BotFather) y tu id de usuario (@userinfobot).
    # El bot solo responde a ese id.
    telegram_bot_token: str = ""
    telegram_user_id: str = ""

    # Langfuse (trazas). Si las claves están vacías, no se envían trazas.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


# Se lee una sola vez, al importar este fichero, y todo el proyecto usa esta misma variable.
settings = Settings()
