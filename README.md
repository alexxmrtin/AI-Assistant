# Asistente IA

Asistente personal por Telegram que lee tu calendario y tu correo, propone acciones y solo las ejecuta cuando tú las apruebas. Es un proyecto de portfolio de AI Engineer: lo importante no es cuántas integraciones tiene, sino que se mide (evals), se defiende (inyección de prompts) y se despliega.

## 1. Puesta en marcha del repo

### 1.1. Qué hace falta

- Python 3.11 o superior (Langfuse no funciona con versiones anteriores).
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

> Este apartado describe la versión a mano del paso 3, guardada en el tag `Explicacion-tool-calling-en-main` (`git checkout Explicacion-tool-calling-en-main`). Desde el paso 5, ese mismo recorrido vive en `grafo.py`.

### 3.1. Cómo probarlo

```bash
python -m asistente_ia "¿Qué tengo el jueves?"
```

Verás tres cosas: la herramienta que pide el modelo con sus argumentos, el resultado que le devolvemos y la respuesta final. Prueba también una pregunta que no necesite la agenda, como "¿Qué es Python?", y verás que no pide ninguna herramienta.

### 3.2. Qué es una herramienta

Un modelo solo sabe lo que aprendió al entrenarse: no conoce tu agenda ni la fecha de hoy. Una herramienta es una función nuestra que el modelo puede pedir que ejecutemos. En `herramientas.py` (desde el paso 7 vive en `mcp_calendar.py`, ver sección 7), `@tool` convierte `list_events` en algo que el modelo puede ver: su nombre, su descripción y sus parámetros con su tipo. El modelo no lee el código de la función, por eso la descripción tiene que explicar bien qué hace y en qué formato van las fechas.

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

`tests/test_herramientas.py` (desde el paso 7, `tests/test_mcp_calendar.py`) comprobaba que `list_events` devuelve los eventos del jueves, una lista vacía para un día libre y que el rango incluye las dos fechas. No llaman al modelo.

## 4. LLM falso para los tests

### 4.1. Cómo probarlo

```bash
pytest
```

No hace falta clave ni internet: los tests del recorrido usan un modelo de mentira.

### 4.2. Para qué sirve

Los tests se ejecutan en cada commit y en la CI. Si llamaran al modelo de verdad, cada ejecución gastaría dinero, necesitaría internet y podría dar un resultado distinto cada vez, porque el modelo no siempre contesta igual. Un test tiene que ser rápido, gratis y dar siempre lo mismo.

### 4.3. Cómo funciona `LLMFalso`

`tests/llm_falso.py` es una clase con los mismos métodos que usamos de un modelo real: `bind_tools` e `invoke`. En el test le pasamos una lista de respuestas preparadas (`AIMessage`) y las va devolviendo en orden, una por cada `invoke`. Además guarda cada conversación que recibe, para comprobar qué le llegó.

Como `main()` solo usa `bind_tools` e `invoke`, no nota la diferencia. Es la misma idea de la capa LLM: a quien usa el modelo le da igual quién hay detrás.

### 4.4. `monkeypatch`

`monkeypatch` es un fixture de pytest que cambia algo solo durante un test y lo deja como estaba al terminar. Lo usamos para dos cosas:

- Sustituir `crear_llm` por una función que devuelve el modelo falso.
- Cambiar `sys.argv`, para simular que escribimos una pregunta en la terminal.

### 4.5. Tests vs. evals

Estos tests comprueban que **nuestro código** hace bien su parte: ejecuta la herramienta que se pide, devuelve el resultado y vuelve a preguntar. No comprueban si el modelo elige bien la herramienta: eso lo medirán las evals del paso 10, con el modelo de verdad.

## 5. El grafo con LangGraph

### 5.1. Cómo probarlo

```bash
pip install -r requirements.txt
python -m asistente_ia
```

Se abre una conversación en la terminal. Prueba "¿Qué tengo el jueves?" y después "¿Y el viernes?": la segunda pregunta solo tiene sentido si el asistente recuerda la primera. Para salir, escribe "salir".

### 5.2. Para qué sirve

En el paso 3 escribimos a mano el orden de las cosas con `if` y `for`: preguntar al modelo, ejecutar la herramienta y volver a preguntar. Funciona, pero cuando el asistente crezca (aprobación humana, memoria, reanudar tras un reinicio) ese código a mano se vuelve inmanejable. LangGraph organiza ese orden como un grafo: cada paso es un nodo y las flechas dicen a qué nodo se va después.

### 5.3. Los nodos (`grafo.py`)

```
START → ingest → agent → ¿pide herramientas? → tools → agent → ... → respond → END
```

- **`ingest`**: convierte la pregunta en un `HumanMessage`. Más adelante también recibirá notas de voz y fotos.
- **`agent`**: llama al modelo con las instrucciones y toda la conversación.
- **`tools`**: ejecuta las herramientas que pidió el modelo y añade un `ToolMessage` por cada una.
- **`respond`**: guarda el texto de la respuesta final.

Cada nodo es una función normal que recibe el estado y devuelve **solo lo que cambia**.

### 5.4. El estado y los reducers

El estado (`Estado`) es la información que viaja de un nodo a otro: `messages` (la conversación), `pregunta` y `respuesta`. Cuando un nodo devuelve `{"respuesta": "..."}`, ese campo se sustituye. Con `messages` pasa otra cosa: `MessagesState` le asigna un *reducer*, una regla que dice cómo se combina lo nuevo con lo que ya había. En este caso la regla es "añadir al final". Por eso `agent` devuelve `{"messages": [respuesta]}` y la conversación crece en vez de borrarse.

### 5.5. Flecha condicional

Después de `agent` hay dos caminos. `siguiente_paso` mira el último mensaje: si el modelo pidió herramientas, va a `tools`; si no, a `respond`. Es el mismo `if` del paso 3, convertido en una flecha del grafo. Desde `tools` siempre se vuelve a `agent`, y ese es el bucle.

### 5.6. Memoria: checkpointer y `thread_id`

El checkpointer guarda el estado de cada conversación después de cada nodo. Cuando llega otra pregunta con el mismo `thread_id`, el grafo recupera la conversación anterior y la continúa. `InMemorySaver` lo guarda en la memoria del programa, así que se pierde al cerrarlo; en la semana 2 lo guardaremos en Postgres. En Telegram, el `thread_id` será el id de tu chat.

### 5.7. Tests de este paso

`tests/test_tool_calling.py` prueba el grafo con el modelo falso: que ejecuta la herramienta y le devuelve el resultado, que responde directamente si no hace falta herramienta, y que recuerda la conversación con el mismo `thread_id`.

## 6. Trazas con Langfuse

### 6.1. Cómo probarlo

1. Crea una cuenta gratuita en [Langfuse Cloud](https://cloud.langfuse.com) y un proyecto.
2. En el proyecto, ve a Settings → API Keys y crea un par de claves.
3. Copia `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_HOST` en tu `.env`. El host aparece junto a las claves, porque depende de la región que elegiste.
4. `pip install -r requirements.txt` y `python -m asistente_ia`.
5. Pregunta "¿Qué tengo el jueves?" y abre Traces en Langfuse.

Sin claves, el asistente funciona igual pero no envía nada.

### 6.2. Para qué sirve

Cuando el asistente responde mal, desde fuera solo ves la respuesta. Una traza es el registro de todo lo que pasó por dentro de una petición: qué nodos se ejecutaron y en qué orden, qué mensajes recibió el modelo, qué herramienta pidió y con qué argumentos, qué devolvió, cuánto tardó cada paso y cuántos tokens gastó (y cuánto costó). Es lo que en sistemas se llama observabilidad: como los logs de un servidor, pero pensados para un LLM.

### 6.3. Cómo se conecta: callbacks

LangChain y LangGraph avisan de cada paso que dan a unos objetos llamados *callbacks*. En `trazas.py`, `crear_callbacks()` crea el callback de Langfuse, y en `__main__.py` se le pasa al grafo dentro de `configuracion`. A partir de ahí, cada `grafo.invoke(...)` deja una traza, sin tocar `grafo.py`.

### 6.4. Qué verás en una traza

Un árbol con un elemento por paso: `ingest`, `agent` (dentro, la llamada al modelo con sus mensajes de entrada y salida, tokens y coste), `tools` (la herramienta, sus argumentos y su resultado), otra vez `agent` y `respond`. Cada elemento tiene su duración.

### 6.5. Tests de este paso

`tests/test_trazas.py` comprueba que sin claves no se crea ningún callback y que con claves se crea el de Langfuse. No envían nada a Langfuse.


### 6.6. Decisión: Langfuse Cloud solo con datos de prueba

**Decidido el 31-10-2026.** Las trazas se guardan en Langfuse Cloud, pero solo mientras se desarrolla con la agenda de prueba. Cuando el asistente use mis datos reales (calendario, correo), dejo vacías `LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY` en el `.env`. Así no se envía ninguna traza, porque una traza guarda el contenido completo de cada petición.

El motivo: no quiero mis datos personales en la nube de un proveedor que no conozco bien.

**Si en el futuro lo quiero en local:** Langfuse se puede instalar en mi equipo con Docker Compose, usando el fichero que da Langfuse en su documentación ("Self-hosting"). Levanta 6 contenedores:

- `langfuse-web`: la web y la entrada de trazas.
- `langfuse-worker`: procesa las trazas en segundo plano.
- Redis: la cola de trabajo entre web y worker.
- MinIO: almacén de los datos en bruto.
- Postgres: usuarios, proyectos y claves.
- ClickHouse: las trazas, para consultarlas rápido.

El código no cambia. Solo hay que poner `LANGFUSE_HOST=http://localhost:3000` en el `.env` y usar las claves del Langfuse local.

Ojo: aunque no haya trazas, con Claude o Gemini las preguntas siguen pasando por Anthropic o Google. Para que nada salga del equipo, hay que usar también `LLM_PROVIDER=ollama`.

## 7. Servidor MCP del calendario

### 7.1. Cómo probarlo

1. `pip install -r requirements.txt` (hay dos librerías nuevas: `mcp` y `langchain-mcp-adapters`).
2. `python -m asistente_ia` y pregunta "¿Qué tengo el jueves?". La respuesta es la misma que antes, pero ahora los eventos vienen del servidor MCP.
3. `pytest` (los tests arrancan el servidor de verdad).

### 7.2. Para qué sirve

MCP (Model Context Protocol) es un estándar para conectar herramientas a una IA, como un USB: el cliente no necesita saber cómo está hecha la herramienta, solo que habla MCP.

- **Servidor MCP** (`mcp_calendar.py`): un programa aparte que ofrece herramientas. Aquí, `list_events`.
- **Cliente MCP** (`cliente_mcp.py`): nuestro asistente. Pregunta al servidor qué herramientas tiene y las llama cuando el modelo las pide.
- **Transporte stdio**: el cliente arranca el servidor como un proceso hijo y se hablan por la entrada y salida estándar con mensajes JSON, como una tubería `|` de Linux.

Ventajas: en el paso 8 cambiaremos la agenda de prueba por Google Calendar solo dentro del servidor, sin tocar el grafo; las claves de Google vivirán en el servidor, lejos del modelo; y cualquier otro cliente MCP (por ejemplo Claude Desktop) podría usar el mismo servidor.

El LLM no se conecta al servidor: sigue siendo el tool calling del paso 3. El modelo pide la herramienta, nuestro código se la pide al servidor, el servidor la ejecuta y devuelve el resultado.

### 7.3. Cómo encaja en el código

1. `__main__.py` llama a `cargar_herramientas_mcp()`, que arranca el servidor y trae sus herramientas ya convertidas a herramientas de LangChain (eso lo hace `langchain-mcp-adapters`).
2. Se las pasa a `crear_grafo(modelo, herramientas)`, que hace `bind_tools` como antes.
3. En el nodo `tools`, cada llamada se envía al servidor MCP, que ejecuta `list_events` y devuelve el resultado como bloques de texto.

### 7.4. `async` y `asyncio.run`

La librería de MCP es asíncrona: sus funciones (`get_tools`, `ainvoke`) no devuelven el resultado, sino una tarea pendiente, porque hablar con otro programa implica esperar. `asyncio.run(tarea)` ejecuta esa tarea, espera a que termine y devuelve el resultado. Lo usamos solo en dos sitios (`cliente_mcp.py` y el nodo `tools`) para que el resto del código siga siendo normal. Cuando llegue Telegram (paso 9) pasaremos a `async` completo.

### 7.5. Tests de este paso

`tests/test_mcp_calendar.py` prueba `list_events` directamente (tres casos) y el camino completo por MCP: arranca el servidor, trae la herramienta y la llama. `tests/test_tool_calling.py` usa ahora las herramientas del servidor MCP con el LLM falso.

## 8. Google Calendar

### 8.1. Cómo probarlo

1. Crea el proyecto en [Google Cloud](https://console.cloud.google.com): activa la Google Calendar API, configura la pantalla de consentimiento (público Externo, en modo "Prueba", y añade tu Gmail en Público → Usuarios de prueba) y crea un cliente OAuth de tipo "App de escritorio". Descarga su JSON como `secrets/credentials.json`.
2. `pip install -r requirements.txt`.
3. Inicia sesión una vez: `python -m asistente_ia.google_calendar`. Se abre el navegador; como la app no está verificada, Google avisa: pulsa "Continuar" (o "Configuración avanzada" → "Ir a Asistente IA") y acepta el permiso. En modo Prueba, repite este paso cada 7 días. Se crea `secrets/token.json`.
4. En el `.env`, pon `CALENDAR_BACKEND=google`.
5. `python -m asistente_ia` y pregunta por tus eventos reales.

### 8.2. OAuth: el "iniciar sesión con Google"

El programa nunca ve tu contraseña. Inicias sesión en la página de Google, aceptas el permiso y Google le da al programa un token: una llave limitada que solo sirve para lo que aceptaste. Pedimos `calendar.readonly`, así que con esa llave es imposible crear, cambiar o borrar eventos.

El token tiene dos partes: una llave de acceso que caduca cada hora y un *refresh token* para pedir otra sin volver a abrir el navegador. `cargar_credenciales()` la renueva sola cuando hace falta.

- `secrets/credentials.json`: identifica a la app ante Google.
- `secrets/token.json`: tu sesión. Quien lo tenga puede leer tu calendario.

Los dos están en `secrets/`, que está en el `.gitignore`.

### 8.3. Decisión: app en modo "Prueba"

**Decidido el 01-11-2026.** Es un proyecto de uso personal: quien quiera usarlo crea su propio proyecto de Google Cloud y su cliente OAuth. Por eso la app se queda en modo "Prueba", con mi cuenta como usuario de prueba, sin rellenar página principal ni política de privacidad.

Consecuencia: en modo Prueba Google caduca el inicio de sesión cada 7 días, y hay que volver a ejecutar `python -m asistente_ia.google_calendar`. Si más adelante molesta (por ejemplo, con el bot y n8n funcionando solos), se puede pasar a "En producción" sin verificar: hay que añadir en Desarrollo de la marca una URL de página principal y otra de política de privacidad. El código no cambia.

### 8.4. Cómo encaja en el código

- `google_calendar.py`: el inicio de sesión (`iniciar_sesion`), la carga del token (`cargar_credenciales`), la petición a Google (`listar_eventos_google`) y la conversión de cada evento al mismo formato que la agenda de prueba (`convertir_evento`).
- `mcp_calendar.py`: `list_events` mira `CALENDAR_BACKEND` y llama a la agenda de prueba (`demo`) o a Google (`google`).
- El grafo y el cliente MCP no cambian: no saben de dónde salen los eventos.

### 8.5. Tests de este paso

`tests/test_mcp_calendar.py` prueba `convertir_evento` con eventos de Google escritos a mano (uno con hora y otro de todo el día sin título), sin conectarse a Google. Los tests que arrancan el servidor le fuerzan `CALENDAR_BACKEND=demo`, para que den siempre el mismo resultado aunque tu `.env` diga `google`.

## 9. Bot de Telegram

### 9.1. Cómo probarlo

1. En Telegram, habla con **@BotFather**: `/newbot`, elige un nombre y un usuario acabado en `bot`. Te dará un token.
2. Habla con **@userinfobot** para saber tu id de usuario (un número).
3. En el `.env`, pon `TELEGRAM_BOT_TOKEN=` (el token) y `TELEGRAM_USER_ID=` (tu id).
4. `pip install -r requirements.txt` y `python -m asistente_ia.telegram_bot`.
5. Escribe a tu bot desde el móvil. Mientras el programa esté en marcha, te responde. Ctrl+C lo para.

### 9.2. Cómo funciona

El bot es una cuenta de Telegram que maneja nuestro programa. Usamos *polling*: `run_polling()` pregunta a Telegram cada poco si hay mensajes nuevos, así que funciona desde tu ordenador sin servidor público. (La alternativa, *webhook*, necesita una URL pública; llegará al desplegar.)

Con cada mensaje se ejecuta `responder`:

1. Comprueba que el mensaje viene de `TELEGRAM_USER_ID`. A cualquier otro no le contesta: el bot lee tu calendario y cualquiera puede encontrarlo en Telegram.
2. Llama al grafo con el id del chat como `thread_id`: cada chat tiene su propia memoria.
3. Envía la respuesta al chat.

### 9.3. El grafo pasa a `async`

La librería de Telegram es asíncrona, y dentro de algo asíncrono no se puede usar `asyncio.run`. Por eso todo lo que espera respuestas pasa a `async def` + `await`:

- En `grafo.py`, los nodos `agent` y `tools` son `async def` y usan `await modelo.ainvoke(...)` y `await herramienta.ainvoke(...)`.
- `cargar_herramientas_mcp()` es `async def`, así que se llama con `await`.
- El grafo se ejecuta con `await grafo.ainvoke(...)` en vez de `grafo.invoke(...)`.
- `asyncio.run` queda solo en los puntos de entrada: `asyncio.run(main())` en `__main__.py`, la carga de herramientas en `telegram_bot.py` y los tests.

Esto sustituye lo explicado en la sección 7.4, donde usábamos `asyncio.run` dentro del grafo.

### 9.4. Tests de este paso

`tests/test_telegram_bot.py` prueba `responder` con un mensaje de Telegram de mentira (no se conecta a Telegram): responde a tu id y no responde, ni llama al modelo, con otro id. El LLM falso tiene ahora también `ainvoke`.

## 10. Evals: medir cómo responde el asistente

### 10.1. Cómo probarlo

`python -m asistente_ia.evals`. Usa el modelo de verdad (gasta unos céntimos de tokens) y siempre la agenda de prueba, aunque el `.env` diga `CALENDAR_BACKEND=google`. Al final muestra la nota, por ejemplo `Nota: 9/10 (90 %)`, y de cada caso fallido, qué falló y qué respondió.

### 10.2. Tests vs. evals

- **Tests** (`pytest`): comprueban que nuestro código funciona, con el LLM falso. Gratis, rápidos y siempre dan lo mismo.
- **Evals**: comprueban lo bien que responde el modelo real. Cuestan tokens y pueden variar un poco entre ejecuciones, porque el modelo no siempre contesta igual.

Se pasan cuando cambias algo que afecta a las respuestas (el prompt, el modelo, el proveedor) para saber con números si ha mejorado o empeorado.

### 10.3. Cómo se corrige cada caso

Cada caso de `CASOS` (en `evals.py`) tiene una pregunta y unas reglas:

- `debe_contener`: palabras que tienen que aparecer todas.
- `debe_contener_alguna`: basta con que aparezca una (para cosas que se dicen de varias formas, como "20:30" u "8:30").
- `debe_usar_herramienta`: si tenía que consultar el calendario o no. Se mira si en la conversación hay algún `ToolMessage`.

`corregir()` devuelve la lista de fallos; si está vacía, el caso está aprobado. Es una corrección sencilla por palabras. En la semana 3 añadiremos un LLM que haga de juez para respuestas más abiertas.

### 10.4. La fecha de "hoy"

Antes la fecha estaba escrita en las instrucciones ("Hoy es lunes 2 de noviembre de 2026"), así que el asistente creía que siempre era ese día. Ahora `crear_instrucciones(fecha)` (en `grafo.py`) escribe la fecha que le pases, y el nodo `agent` usa la fecha real de cada día. Las evals y algunos tests le pasan `fecha_fija` (el 2 de noviembre de 2026), porque la agenda de prueba es de esa semana.

### 10.5. Tests de este paso

`tests/test_evals.py` prueba `corregir()` con respuestas escritas a mano. `tests/test_tool_calling.py` comprueba que las instrucciones llevan la fecha y que con `fecha_fija` el modelo recibe esa fecha.

## 11. Docker y Compose

### 11.1. Cómo probarlo

1. Ten el `.env` relleno y, si usas Google Calendar, inicia sesión fuera del contenedor (`python -m asistente_ia.google_calendar`) para que exista `secrets/token.json`.
2. Para el bot si lo tienes abierto con `python -m asistente_ia.telegram_bot`: Telegram no deja que dos programas recojan los mensajes del mismo bot a la vez.
3. `docker compose up -d --build` construye la imagen y arranca el bot en segundo plano.
4. `docker compose logs -f` para ver lo que imprime. `docker compose down` para pararlo.

### 11.2. Qué hay dentro del contenedor

Un solo contenedor con el bot de Telegram. El servidor MCP del calendario no necesita uno propio: el bot lo arranca como proceso hijo por stdio, así que vive dentro del mismo contenedor. Cuando lleguen Postgres y n8n, Compose levantará más servicios.

### 11.3. `Dockerfile`

- Parte de `python:3.12-slim` e instala `tzdata` (zonas horarias), que la imagen slim no trae.
- Copia primero `requirements.txt` e instala: así Docker reutiliza esa capa si solo cambias código.
- Copia solo `asistente_ia/`. El `.env`, `secrets/` y `.venv` nunca entran en la imagen.
- Arranca `python -m asistente_ia.telegram_bot`.

### 11.4. `docker-compose.yml`

- `env_file: .env`: las claves llegan al contenedor desde tu `.env`, no se guardan en la imagen.
- `TZ: Europe/Madrid`: sin esto el contenedor usa la hora UTC y el bot podría equivocarse de día.
- `OLLAMA_BASE_URL` y `extra_hosts`: dentro del contenedor, `localhost` es el propio contenedor; tu ordenador se alcanza como `host.docker.internal`. Solo importa si usas Ollama.
- `volumes: ./secrets:/app/secrets`: el contenedor usa tus `credentials.json` y `token.json`, y cuando renueva el token, el nuevo se guarda en tu carpeta.
- `restart: unless-stopped`: si se cae o reinicias el ordenador, vuelve a arrancar solo.

El inicio de sesión con Google se hace siempre fuera del contenedor, porque necesita abrir el navegador. En modo Prueba, cuando caduque a los 7 días: inicias sesión fuera y `docker compose restart`.

## 12. CI y secretos

### 12.1. Cómo probarlo

1. Activa pre-commit una vez en tu ordenador: `pre-commit install`. Desde entonces, cada `git commit` pasa antes ruff y gitleaks; si alguno falla, el commit no se hace.
2. Para pasarlo a mano sobre todo el proyecto: `pre-commit run --all-files`.
3. Haz push y mira la pestaña **Actions** del repo en GitHub: cada push aparece con ✓ verde o ✗ roja. Pinchando en él ves cada paso y su salida.

### 12.2. Qué es la CI

CI (integración continua) significa que, en cada push, GitHub arranca una máquina limpia, instala el proyecto desde cero y pasa las comprobaciones. Si algo falla, lo ves en el commit. Así, lo que está en GitHub siempre está probado, y no depende de que te acuerdes de pasar los tests.

### 12.3. `.github/workflows/ci.yml`

- `on: push` y `pull_request`: cuándo se ejecuta.
- `runs-on: ubuntu-latest`: la máquina que pone GitHub.
- `actions/checkout`: descarga el código (con todo el historial, para que gitleaks lo revise entero).
- `gitleaks/gitleaks-action`: busca claves en el código y en los commits. En repos personales no necesita licencia.
- `actions/setup-python`, `pip install`, `ruff check .` y `pytest`: lo mismo que haces tú en la terminal.

Los tests no necesitan claves: usan el LLM falso y la agenda de prueba.

### 12.4. `.pre-commit-config.yaml`

- `ruff`: el mismo linter, antes de cada commit.
- `gitleaks`: revisa solo lo que vas a commitear. Si ve algo con pinta de clave, para el commit, así la clave no llega nunca a GitHub.

La primera vez tarda un poco porque pre-commit descarga las herramientas.

### 12.5. Decisión: líneas largas permitidas

Ruff tenía activada la regla E501 (líneas de más de 100 caracteres), y los comentarios largos que son apuntes la incumplían. Se ha desactivado en `pyproject.toml`.
