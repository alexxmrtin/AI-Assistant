# Cliente MCP: conecta el asistente con los servidores MCP y trae sus herramientas.
#
# langchain-mcp-adapters convierte cada herramienta MCP en una herramienta de LangChain

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
    "correo": {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "asistente_ia.mcp_correo"],
    },
}


# async def, la función es asíncrona, así que quien la llame tiene que usar await.
async def cargar_herramientas_mcp():
    cliente = MultiServerMCPClient(SERVIDORES)

    # get_tools es asíncrona: await espera a que arranque el servidor, nos diga sus
    # herramientas y se cierre.
    herramientas = await cliente.get_tools()
    return herramientas

