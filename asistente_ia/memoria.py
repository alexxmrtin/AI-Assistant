# Memoria del grafo, dónde se guardan las conversaciones (el checkpointer).

#Las conversaciones se guardan en Postgres (en disco), una base de datos que vive en Docker, así que sobreviven aunque reinicies el bot.

# DATABASE_URL (en el .env) dice dónde está Postgres. Si está vacía, se usa la RAM como antes (así funcionan los tests).

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # memoria en Postgres
from psycopg import AsyncConnection  # la conexión de Python con Postgres
from psycopg.rows import dict_row

from asistente_ia.config import settings


# Usamos async para establcer una conexion con la base de datos
async def abrir_memoria():
    if settings.database_url == "":
        print("Sin DATABASE_URL: la memoria se guarda en RAM y se pierde al cerrar.")
        return InMemorySaver()

    # Abrimos la conexión. Las tres opciones las pide LangGraph para que su memoria funcione bien:
    #   autocommit=True      -> cada cambio se guarda en el momento, sin tener que confirmarlo aparte
    #   prepare_threshold=0  -> desactiva una optimización de psycopg que da problemas con varias peticiones a la vez
    #   row_factory=dict_row -> cada fila de la base de datos llega como diccionario ({"columna": valor})
    conexion = await AsyncConnection.connect(
        settings.database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )

    memoria = AsyncPostgresSaver(conexion)

    # setup crea las tablas que necesita LangGraph la primera vez. Las siguientes veces ve que ya existen y no hace nada.
    await memoria.setup()

    print("Memoria en Postgres: las conversaciones se guardan aunque cierres el programa.")
    return memoria # devolvemos un objeto que va a usar langraph para comunicarse con la base de datos y guardar las cosas. Langraph se encarga de esto por nosotros no tenemos que hacer nada
