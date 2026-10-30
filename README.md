# Asistente IA

Asistente personal por Telegram que lee tu calendario y tu correo, propone acciones y solo las ejecuta cuando tú las apruebas. Es un proyecto de portfolio de AI Engineer: lo importante no es cuántas integraciones tiene, sino que se mide (evals), se defiende (inyección de prompts) y se despliega.

## 1. Puesta en marcha del repo

### 1.1. Qué hace falta

- Python 3.10 o superior.
- Git.

### 1.2. Primeros comandos

```bash
python3 -m venv .venv                # crea el entorno virtual
source .venv/bin/activate            # lo activa
pip install -r requirements.txt      # instala las dependencias
python -m asistente_ia               # ejecuta el programa
pytest                               # pasa los tests
ruff check .                         # busca errores y malas prácticas
ruff format .                        # formatea el código
pre-commit install                   # activa las comprobaciones en cada commit
```

### 1.3. Qué es cada fichero y herramienta

**`requirements.txt`.** Las dependencias con la versión exacta (`==`), para que tu portátil, la CI y el contenedor instalen lo mismo.

**`pyproject.toml`.** Aquí solo está la configuración de ruff y pytest, en un único fichero en vez de `ruff.toml` y `pytest.ini`.

**`asistente_ia/`.** El paquete del proyecto: aquí va todo el código del asistente. `__init__.py` está vacío a propósito: marca la carpeta como paquete importable y se ejecuta en cada `import asistente_ia`. `__main__.py` es el punto de entrada: es lo que se ejecuta con `python -m asistente_ia`. La línea `if __name__ == "__main__":` hace que `main()` solo arranque al ejecutar el programa, y no cuando un test importa el fichero.

**ruff.** Linter y formateador en uno. Las reglas activas están en `[tool.ruff.lint]` de `pyproject.toml`. Destaca la familia `S` (bandit): detecta cosas como contraseñas escritas en el código o `subprocess` con `shell=True`, que encaja con la parte de seguridad del proyecto.

**pytest.** Busca en `tests/` las funciones que empiezan por `test_` y comprueba sus `assert`. `capsys` en `tests/test_arranque.py` es un *fixture*: un parámetro que pytest rellena por ti, en este caso con lo que el programa imprimió por pantalla.

**pre-commit.** Ejecuta comprobaciones antes de cada `git commit` (ver `.pre-commit-config.yaml`). Si ruff encuentra algo, el commit se para y lo arreglas antes de que llegue al repo. Es la primera línea de defensa; la CI será la segunda.

**`.gitignore`.** Además de lo típico de Python, ignora `.env` y `secrets/`. Desde el primer día, nada con claves puede entrar al repo por accidente.

## 2. Configuración y capa LLM

### 2.1. Cómo probarlo

```bash
cp .env.example .env                 # y rellena ANTHROPIC_API_KEY
pip install -r requirements.txt
python -m asistente_ia "¿Qué es un agente de IA? Responde en una frase."
```

Para usar Ollama, cambia en el `.env` `LLM_PROVIDER=ollama` y pon tu modelo en `LLM_MODEL_FAST`. La misma orden responde ahora con el modelo local, sin tocar el código.

### 2.2. Variables de entorno y `.env`

Las claves y los ajustes no van en el código: van en variables de entorno, valores que el sistema le pasa al programa al arrancar. Para no exportarlas a mano, se escriben en un fichero `.env` en la raíz. El `.env` nunca se sube a GitHub (está en `.gitignore`); en su lugar se sube `.env.example`, con los mismos nombres y sin valores.

### 2.3. `config.py`: la configuración

`Settings` tiene un atributo por variable de entorno, con su valor por defecto. pydantic-settings lo rellena desde el entorno o el `.env` (`llm_provider` lee `LLM_PROVIDER`). La configuración se lee una sola vez, al importar el fichero, y queda en la variable `settings`.

### 2.4. `llm.py`: un modelo sin saber de quién es

LangChain define una interfaz común, `BaseChatModel`. `ChatAnthropic`, `ChatGoogleGenerativeAI` y `ChatOllama` la implementan, así que todas se usan igual (`.invoke()`, `.bind_tools()`…). `crear_llm("fast")` o `crear_llm("smart")` devuelve la que toque según `LLM_PROVIDER`, y el resto del proyecto nunca pregunta cuál es.

- **fast y smart.** Uno barato y rápido para casi todo y uno más capaz para lo difícil. Esta semana solo se usa `fast`; el enrutado entre los dos llega en la semana 5.
- **`temperature=0`.** Reduce la aleatoriedad de las respuestas. Importa cuando el modelo tenga que elegir herramientas: queremos que ante la misma pregunta elija lo mismo.

### 2.5. Tests de este paso

`tests/test_llm.py` comprueba los modelos por defecto, que la variable de entorno manda sobre el defecto, que un `LLM_PROVIDER` desconocido da error y que se crea la clase del proveedor elegido. Ninguno llama a una API: crear el objeto del modelo no gasta nada.

## 3. Tool calling: el modelo pide, nosotros ejecutamos

### 3.1. Cómo probarlo

```bash
python -m asistente_ia "¿Qué tengo el jueves?"
```

Verás tres cosas: la herramienta que pide el modelo con sus argumentos, el resultado que le devolvemos y la respuesta final. Prueba también una pregunta que no necesite la agenda, como "¿Qué es Python?", y verás que no pide ninguna herramienta.

### 3.2. Qué es una herramienta

Un modelo solo sabe lo que aprendió al entrenarse: no conoce tu agenda ni la fecha de hoy. Una herramienta es una función nuestra que el modelo puede pedir que ejecutemos. En `herramientas.py`, `@tool` convierte `list_events` en algo que el modelo puede ver: su nombre, su descripción y sus parámetros con su tipo. El modelo no lee el código de la función, por eso la descripción tiene que explicar bien qué hace y en qué formato van las fechas.

De momento `list_events` lee una agenda inventada (`AGENDA_DE_PRUEBA`). En el paso 7 se mudará a un servidor MCP y en el paso 8 leerá Google Calendar.

### 3.3. El modelo no ejecuta nada

`__main__.py` hace el recorrido completo a mano:

1. `bind_tools([list_events])` le dice al modelo que la herramienta existe.
2. Primera llamada: el modelo contesta con una petición, por ejemplo `list_events` con `fecha_inicio="2026-11-05"`. Esa petición está en `respuesta.tool_calls`.
3. Nuestro código ejecuta la función y le devuelve el resultado en un `ToolMessage`. El `tool_call_id` indica a qué petición responde.
4. Segunda llamada: con el resultado delante, el modelo escribe la respuesta final.

Que el modelo solo pueda pedir, y que la ejecución dependa de nuestro código, es la base de la seguridad del proyecto: en la semana 2, antes de ejecutar una petición que cambie algo, te preguntaremos a ti.

### 3.4. Tipos de mensaje

- `SystemMessage`: instrucciones para el modelo. Aquí le decimos qué fecha es hoy, porque no lo sabe.
- `HumanMessage`: lo que escribes tú.
- `AIMessage`: lo que contesta el modelo, con texto o con peticiones de herramienta.
- `ToolMessage`: el resultado de una herramienta.

### 3.5. Tests de este paso

`tests/test_herramientas.py` comprueba que `list_events` devuelve los eventos del jueves, una lista vacía para un día libre y que el rango incluye las dos fechas. No llaman al modelo.

