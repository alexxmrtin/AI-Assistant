# Cliente MCP: conecta el asistente con los servidores MCP y trae sus herramientas.
#
# langchain-mcp-adapters convierte cada herramienta MCP en una herramienta de LangChain

import asyncio
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient


# Los servidores a los que nos conectamos y cómo arrancar cada uno.
# sys.executable es la ruta del Python que está ejecutando el asistente (el del .venv), así el servidor se arranca con el mismo Python y las mismas librerías.
SERVIDORES = {
    "calendar": {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "asistente_ia.mcp_calendar"],
    },
}


def cargar_herramientas_mcp():
    cliente = MultiServerMCPClient(SERVIDORES)

    # get_tools es asíncrona (async): devuelve una "tarea pendiente" en vez del resultado.
    # asyncio.run ejecuta esa tarea, espera a que termine y nos da el resultado.
    herramientas = asyncio.run(cliente.get_tools())
    return herramientas
