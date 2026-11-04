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
3. Inicia sesión una vez: `python -m asistente_ia.google_auth`. Se abre el navegador; como la app no está verificada, Google avisa: pulsa "Continuar" (o "Configuración avanzada" → "Ir a Asistente IA") y acepta el permiso. En modo Prueba, repite este paso cada 7 días. Se crea `secrets/token.json`.
4. En el `.env`, pon `CALENDAR_BACKEND=google`.
5. `python -m asistente_ia` y pregunta por tus eventos reales.

### 8.2. OAuth: el "iniciar sesión con Google"

El programa nunca ve tu contraseña. Inicias sesión en la página de Google, aceptas el permiso y Google le da al programa un token: una llave limitada que solo sirve para lo que aceptaste. Pedimos `calendar.readonly`, así que con esa llave es imposible crear, cambiar o borrar eventos. (Desde el apartado 19 pedimos `calendar.events`, que sí permite cambiar eventos, pero solo después de que tú lo apruebes.)

El token tiene dos partes: una llave de acceso que caduca cada hora y un *refresh token* para pedir otra sin volver a abrir el navegador. `cargar_credenciales()` la renueva sola cuando hace falta.

- `secrets/credentials.json`: identifica a la app ante Google.
- `secrets/token.json`: tu sesión. Quien lo tenga puede leer tu calendario.

Los dos están en `secrets/`, que está en el `.gitignore`.

### 8.3. Decisión: app en modo "Prueba"

**Decidido el 01-11-2026.** Es un proyecto de uso personal: quien quiera usarlo crea su propio proyecto de Google Cloud y su cliente OAuth. Por eso la app se queda en modo "Prueba", con mi cuenta como usuario de prueba, sin rellenar página principal ni política de privacidad.

Consecuencia: en modo Prueba Google caduca el inicio de sesión cada 7 días, y hay que volver a ejecutar `python -m asistente_ia.google_auth`. Si más adelante molesta (por ejemplo, con el bot y n8n funcionando solos), se puede pasar a "En producción" sin verificar: hay que añadir en Desarrollo de la marca una URL de página principal y otra de política de privacidad. El código no cambia.

### 8.4. Cómo encaja en el código

- `google_calendar.py`: el inicio de sesión (`iniciar_sesion`), la carga del token (`cargar_credenciales`), la petición a Google (`listar_eventos_google`) y la conversión de cada evento al mismo formato que la agenda de prueba (`convertir_evento`). Desde el apartado 14, el inicio de sesión y la carga del token están en `google_auth.py`, compartidos con Gmail.
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

1. Ten el `.env` relleno y, si usas Google Calendar, inicia sesión fuera del contenedor (`python -m asistente_ia.google_auth`) para que exista `secrets/token.json`.
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

## 13. Servidor MCP del correo

### 13.1. Cómo probarlo

1. `python -m asistente_ia` y pregunta "¿Tengo algún correo de Laura?" y después "¿Qué me dice en el primero?".
2. En la terminal verás `El modelo pide: search_emails ...` y luego `read_email ...`: primero busca y después lee solo el que necesita.
3. `pytest`.

De momento el correo es una bandeja de prueba con 8 correos inventados. Tu Gmail real llega en el apartado 14.

### 13.2. Para qué sirve

Es el segundo servidor MCP, gemelo del calendario (apartado 7): un programa aparte que ofrece herramientas de correo. Tener un servidor por servicio hace que cada uno solo tenga los permisos de lo suyo: el del correo no puede tocar el calendario y al revés.

Tiene dos herramientas:

- `search_emails(texto)`: busca el texto en el remitente, el asunto y el mensaje, y devuelve un resumen de cada correo (`id`, `de`, `asunto`, `fecha`), sin el mensaje.
- `read_email(id_correo)`: devuelve un correo entero.

Están separadas a propósito, como la bandeja de entrada de Gmail y abrir un correo. Si la búsqueda devolviera el texto de todos los correos, el modelo recibiría muchísimo texto (y cada palabra cuesta tokens). Así, primero ve la lista y luego abre solo los que le hacen falta.

### 13.3. Cómo encaja en el código

- `cliente_mcp.py` tiene ahora dos servidores en `SERVIDORES`. `cargar_herramientas_mcp()` los arranca los dos y devuelve todas las herramientas juntas: `list_events`, `search_emails` y `read_email`.
- El grafo no cambia nada: recibe una lista de herramientas más larga y el modelo elige cuál usar leyendo sus descripciones.
- La bandeja de prueba vive en `mcp_correo.py`, igual que la agenda de prueba en `mcp_calendar.py`. Sus correos son de la misma semana (2 de noviembre de 2026), y en el apartado 23 se le añadirán correos con trampa para medir ataques.

### 13.4. Tests de este paso

`tests/test_mcp_correo.py` prueba la búsqueda (por remitente, sin distinguir mayúsculas, sin texto, sin resultados, que no devuelve el mensaje), la lectura (un correo que existe y uno que no) y el camino completo por MCP. En `tests/test_mcp_calendar.py`, el test del cliente ya no espera que `list_events` sea la única herramienta, porque ahora también llegan las del correo.

## 14. Gmail real

### 14.1. Cómo probarlo

1. En [Google Cloud](https://console.cloud.google.com), en el mismo proyecto del apartado 8: busca "Gmail API" en la barra de arriba y pulsa **Habilitar**.
2. En **Google Auth Platform → Acceso a los datos → Añadir o quitar permisos**, busca `gmail.readonly`, márcalo y guarda.
3. Vuelve a iniciar sesión: `python -m asistente_ia.google_auth`. Google te enseñará los dos permisos (leer el calendario y leer el correo); acepta los dos. El `token.json` se sustituye por uno nuevo.
4. En el `.env`, añade `CORREO_BACKEND=google`.
5. `python -m asistente_ia` y pregunta "¿Cuáles son mis últimos correos?" o "¿Tengo algún correo de GitHub?".
6. `pytest`.

Si te saltas el paso 3, el asistente responde que a la sesión le faltan permisos y te dice el comando.

### 14.2. Un solo inicio de sesión para todo Google

Antes el inicio de sesión estaba en `google_calendar.py`. Ahora está en `google_auth.py`, y Calendar y Gmail lo usan los dos: un solo `credentials.json`, un solo `token.json` y un solo comando para iniciar sesión.

Pedimos los dos permisos a la vez (`calendar.readonly` y `gmail.readonly`) porque un token solo vale para los permisos que aceptaste al crearlo. Por eso, cada vez que se añade un permiso, hay que volver a iniciar sesión. `cargar_credenciales()` lo comprueba con `has_scopes`: si al token le falta algún permiso, da un mensaje claro en vez del error de Google.

Los dos permisos son de solo lectura: con este token es imposible enviar, borrar o cambiar nada, aunque el modelo lo intentara. `secrets/token.json` ahora también permite leer tu correo: sigue en `secrets/`, fuera del repo.

### 14.3. Cómo se busca y se lee en Gmail (`google_gmail.py`)

- `buscar_correos_google(texto)`: le pasa el texto a Gmail tal cual, como si lo escribieras en su barra de búsqueda (vale `laura`, `from:laura` o `is:unread`). Gmail devuelve solo los ids de hasta 10 correos, y por cada uno pedimos solo el remitente y el asunto (`format="metadata"`), sin el texto.
- `leer_correo_google(id_correo)`: pide el correo entero (`format="full"`) y saca su texto con `sacar_texto`. Si el id no existe, devuelve el mismo mensaje de error que la bandeja de prueba.
- `convertir_resumen`: convierte lo que manda Google al mismo formato que la bandeja de prueba (`id`, `de`, `asunto`, `fecha`). La fecha llega en milisegundos desde 1970 (`internalDate`) y se pasa a la hora de Madrid.
- `sacar_texto`: un correo es un conjunto de partes (formato MIME): texto plano, HTML, adjuntos, y partes dentro de partes. La función busca la primera parte de texto plano y la decodifica de base64. Si el correo solo tiene HTML, usamos el resumen corto de Gmail (`snippet`). Los correos de más de 3000 letras se recortan para no llenar el contexto del modelo.

### 14.4. Cómo encaja en el código

- `mcp_correo.py`: `search_emails` y `read_email` miran `CORREO_BACKEND` y llaman a la bandeja de prueba (`demo`) o a Gmail (`google`), igual que `list_events` con `CALENDAR_BACKEND`.
- El grafo, el cliente MCP y las descripciones de las herramientas no cambian: el modelo no sabe de dónde salen los correos.
- El servidor se llama `mcp_correo.py` (y no `mcp_gmail.py`) porque no depende de Google: Gmail es solo una de sus fuentes. Para usar otro proveedor bastaría con un fichero nuevo (por ejemplo `microsoft_outlook.py`) y otra opción en `CORREO_BACKEND`.
- Las evals fuerzan `CORREO_BACKEND=demo`, igual que el calendario: nunca leen tu correo real.

### 14.5. Tests de este paso

En `tests/test_mcp_correo.py`: `convertir_resumen` con un correo de Google escrito a mano (y otro sin asunto), y `sacar_texto` con un correo de varias partes y otro solo con HTML. Ninguno se conecta a Google. El test que arranca el servidor le fuerza `CORREO_BACKEND=demo`, para que dé siempre el mismo resultado aunque tu `.env` diga `google`.

## 15. Memoria del grafo en Postgres

### 15.1. Cómo probarlo

1. `pip install -r requirements.txt` (hay dos librerías nuevas: `langgraph-checkpoint-postgres` y `psycopg`).
2. En el `.env`, añade las líneas de Postgres de `.env.example`. Pon una contraseña solo con letras y números en `POSTGRES_PASSWORD`, y esa misma contraseña dentro de `DATABASE_URL`, en lugar de `TU_CONTRASEÑA`.
3. Arranca solo la base de datos: `docker compose up -d db`. La primera vez descarga la imagen. Con `docker compose ps` verás `db` como `healthy`.
4. `python -m asistente_ia`. Al arrancar dirá "Memoria en Postgres". Dile "Me llamo Alejandro", sal con "salir", vuelve a arrancarlo y pregúntale "¿Cómo me llamo?". Se acuerda.
5. Lo mismo con el bot: `python -m asistente_ia.telegram_bot`, o todo junto en Docker con `docker compose up -d`.
6. `pytest`.

Para parar la base de datos: `docker compose stop db`. Los datos no se pierden al pararla: viven en el volumen `datos_postgres`.

### 15.2. Para qué sirve

El checkpointer (apartado 5.6) es donde el grafo guarda el estado de cada conversación después de cada nodo, como los puntos de guardado de un videojuego. Hasta ahora era `InMemorySaver`: vivía en la RAM del programa y desaparecía al cerrarlo. Ahora es `AsyncPostgresSaver`: el mismo guardado, pero en tablas de Postgres.

Nos hace falta para la aprobación (apartado 17). Cuando el asistente te proponga enviar un correo, el grafo se quedará parado a medias esperando tu respuesta, quizá horas. Si en ese tiempo el bot se reinicia, la propuesta tiene que seguir guardada para poder continuar.

### 15.3. `memoria.py`

`abrir_memoria()` mira `DATABASE_URL`:

- **Vacía**: devuelve `InMemorySaver`, como antes. Así funcionan los tests y la CI, que no tienen Postgres.
- **Con valor**: abre una conexión con `psycopg` (el conector de Python con Postgres) y crea un `AsyncPostgresSaver` encima. `setup()` crea las tablas de LangGraph la primera vez; las siguientes veces no hace nada.

`DATABASE_URL` tiene la forma `postgresql://usuario:contraseña@servidor:puerto/base_de_datos`. Desde tu ordenador el servidor es `localhost`. Dentro de Compose, el bot ve a Postgres por el nombre del servicio, `db`. Por eso `docker-compose.yml` le pone al bot su propia `DATABASE_URL`, que sustituye a la del `.env`.

### 15.4. Cómo encaja en el código

- `grafo.py`: `crear_grafo` recibe la memoria como argumento (`memoria=`). Si no se le pasa, usa la RAM, así los tests no cambian.
- `__main__.py`: abre la memoria con `await abrir_memoria()` y se la pasa al grafo.
- `telegram_bot.py`: el asistente se monta ahora en `preparar_asistente`, que el bot ejecuta al arrancar (`post_init`). La conexión con Postgres pertenece al bucle async donde se abre, y `run_polling` crea su propio bucle; si la abriéramos antes con `asyncio.run`, fallaría con el primer mensaje.
- `docker-compose.yml`: nuevo servicio `db` con la imagen de Postgres 16 con pgvector (pgvector lo usaremos en la semana 4 para la memoria a largo plazo). Su puerto solo se abre en `127.0.0.1`, así que nadie fuera de tu ordenador puede conectarse. El bot espera a que `db` esté `healthy` antes de arrancar.

### 15.5. Tests de este paso

`tests/test_memoria.py` comprueba que sin `DATABASE_URL` la memoria va a la RAM, y que el grafo guarda la conversación en la memoria que le pasan. La prueba contra un Postgres de verdad (guardar, cerrar, volver a abrir y que se acuerde) es la del apartado 15.1, porque la CI no tiene base de datos.

## 16. Salida estructurada con Pydantic: el nodo `route`

### 16.1. Cómo probarlo

1. `python -m asistente_ia` y pregunta "¿Qué tengo el jueves?". En la terminal verás `Clasificación: consulta - ...` y después responde como siempre.
2. Ahora pide algo que cambie tu cuenta: "Responde a Laura que el viernes me va bien" o "Borra el dentista". Verás `Clasificación: accion - ...` y, desde el paso 6, te pedirá aprobación (apartado 17).
3. `pytest`.

### 16.2. Para qué sirve

Antes de que el agente se ponga a trabajar, el nodo `route` decide si el mensaje es una **consulta** (saber algo, leer la agenda o el correo, charlar) o una **acción** (enviar un correo, crear, mover o borrar un evento). Según la respuesta, el grafo va por un camino u otro:

```
ingest → route → consulta → agent ⇄ tools → respond
               → accion   → propose → approval_gate → execute / reject
```

Al principio el camino de acción solo contestaba que aún no estaba disponible (nodo `accion_no_disponible`). En el paso 6 (apartado 17) se cambió por la propuesta y la aprobación.

### 16.3. Salida estructurada

Si le preguntáramos al modelo "¿esto es una consulta o una acción?" con texto libre, podría contestar "Es una acción", "acción.", "Creo que es una consulta porque..." y tendríamos que adivinar qué ha querido decir. Con salida estructurada le damos una ficha con campos fijos y le obligamos a rellenarla:

```python
class Clasificacion(BaseModel):
    intencion: str = Field(description="'consulta' si ... 'accion' si ...")
    motivo: str = Field(description="Una frase corta que explique por qué...")
```

- `BaseModel` es la clase de Pydantic para definir fichas: cada campo tiene un nombre y un tipo. Pydantic ya lo usábamos sin verlo: `pydantic-settings` (apartado 2) está hecho con él.
- `Field(description=...)` es lo que lee el modelo para saber qué poner en cada campo, igual que la descripción de una herramienta.
- `modelo.with_structured_output(Clasificacion)` crea una versión del modelo que devuelve directamente un objeto `Clasificacion` ya comprobado. Por dentro usa el tool calling del apartado 3: le da al modelo una "herramienta" con la forma de la ficha y le obliga a usarla.

### 16.4. Qué pasa si el modelo se equivoca

Un modelo puede fallar al rellenar la ficha. `route` lo controla en tres niveles, y en todos elige "consulta", porque es lo seguro (no cambia nada):

1. **Ficha inválida** (falta un campo o el tipo no es el correcto): Pydantic lanza `ValidationError`, o LangChain `OutputParserException` si no puede ni leerla. Se recoge con `try/except`.
2. **No rellena la ficha** (contesta con texto normal): llega `None`.
3. **Rellena la ficha con otra palabra** ("saludo", "Acción"): Pydantic solo garantiza que es un texto, no que sea una de nuestras dos palabras. Lo comprobamos nosotros: "accion" o "acción" es acción; cualquier otra cosa, consulta.

### 16.5. Cómo encaja en el código

- `grafo.py`: la clase `Clasificacion`, las instrucciones del clasificador, el campo `intencion` en el estado, y el nodo `route`.
- `route` solo le pasa al modelo el mensaje nuevo, no toda la conversación: para clasificar basta, y gasta menos tokens. A cambio, cada mensaje hace ahora una llamada más al modelo (la clasificación), que se ve en Langfuse.
- `tests/llm_falso.py`: `LLMFalso` tiene ahora `with_structured_output`, que devuelve un `ClasificadorFalso`. Si no se le preparan intenciones, todo es "consulta", así los tests anteriores no han cambiado.

### 16.6. Tests de este paso

`tests/test_route.py`: una acción no llega al agente (va al camino de aprobación), una consulta sí, "Acción" con tilde y mayúscula cuenta como acción, una palabra desconocida y una ficha sin rellenar se tratan como consulta.

## 17. Aprobación antes de actuar (`approval_gate`)

### 17.1. Cómo probarlo

1. `python -m asistente_ia` y pide una acción: "Borra el dentista del jueves".
2. Verás `Propuesta: {...}` y la pregunta `¿Apruebas? (s/n)`.
3. Responde `n`: contesta "Vale, no hago nada" y no se ejecuta nada.
4. Repite y responde `s`: verás `[PRUEBA] Aquí se ejecutaría: ...`. De momento no cambia nada de verdad; eso llega en los pasos 7 (Gmail) y 8 (Calendar).
5. `pytest`.

En Telegram todavía no hay botones para aprobar (llegan en el paso 9), así que de momento el bot rechaza las acciones y avisa.

### 17.2. Para qué sirve

Es la pieza de seguridad más importante del proyecto: **el modelo propone, la persona decide y el código ejecuta**. El modelo nunca tiene a mano las herramientas que escriben (enviar un correo, borrar un evento). Solo rellena una propuesta, y el único nodo que puede hacer cambios (`execute`) solo se alcanza pasando por `approval_gate` con un sí. Así, aunque alguien engañe al modelo con un correo trampa, como mucho conseguirá una propuesta rara que tú verás y rechazarás.

```
route → accion → propose → approval_gate ──(se para y pregunta)
                               │ sí → execute → END
                               │ no → reject  → END
         (si propose no entiende la acción, contesta pidiendo detalles y termina)
```

### 17.3. Proponer: la segunda ficha

`propose` usa salida estructurada, igual que `route` (apartado 16), con otra ficha:

```python
class PropuestaDeAccion(BaseModel):
    accion: str    # "enviar correo", "crear evento", "mover evento" o "borrar evento"
    detalles: str  # a quién, qué texto, qué día y a qué hora...
```

A diferencia de `route`, a `propose` le pasamos toda la conversación, para que entienda cosas como "bórralo" refiriéndose a algo de lo que hablabais antes. La propuesta se guarda en el estado como un diccionario normal.

> En el paso 7 (apartado 18) esta ficha se cambió por una llamada a herramienta, para tener los datos exactos que necesita `execute`.

### 17.4. Pausar y reanudar: `interrupt` y `Command(resume=...)`

- `interrupt(valor)` dentro de `approval_gate` **para el grafo**: guarda el estado en la memoria (por eso hace falta el checkpointer del apartado 15) y `ainvoke` termina devolviendo una clave `"__interrupt__"` con el valor (la propuesta).
- El main ve esa clave, enseña la propuesta y pregunta `¿Apruebas? (s/n)`.
- `grafo.ainvoke(Command(resume=True), configuracion)` **reanuda** el grafo en esa misma conversación (mismo `thread_id`). El nodo `approval_gate` se vuelve a ejecutar desde el principio, pero esta vez `interrupt()` no para: devuelve el valor de `resume`.
- Solo un `True` exacto cuenta como sí. Cualquier otra cosa es no.

Como la pausa queda guardada en la memoria, con Postgres el grafo puede esperar tu respuesta aunque el programa se reinicie. Lo necesitaremos en Telegram, donde puedes tardar horas en pulsar el botón.

### 17.5. Cómo encaja en el código

- `grafo.py`: la clase `PropuestaDeAccion`, los campos `propuesta` y `aprobada` en el estado, y los nodos `propose`, `approval_gate`, `execute` y `reject` (sustituyen a `accion_no_disponible`).
- `__main__.py`: el bucle `while "__interrupt__" in estado_final` que pregunta y reanuda.
- `telegram_bot.py`: si el grafo se para, lo reanuda con un no y avisa de que las acciones aún solo funcionan en la terminal.
- `evals.py`: las evals solo tienen consultas. Si el modelo confunde una con una acción, se reanuda con un no y ese caso falla.
- `tests/llm_falso.py`: `with_structured_output` devuelve un falso distinto según la ficha. Para `PropuestaDeAccion`, un `ProponedorFalso` que por defecto propone borrar el dentista.

### 17.6. Tests de este paso

`tests/test_aprobacion.py`: el grafo se para con la propuesta, con un sí se ejecuta, con un no no, cualquier valor que no sea `True` es un no, si no hay propuesta no pide aprobación, y Telegram rechaza las acciones sin dejar el grafo parado.

## 18. Escribir en Gmail: borrador y envío al aprobar

### 18.1. Qué tienes que hacer tú (una vez)

1. En **Google Cloud → Google Auth Platform → Acceso a los datos → Añadir o quitar permisos**, busca `gmail.compose`, márcalo y guarda (igual que hiciste con `gmail.readonly` en el apartado 14).
2. Vuelve a iniciar sesión, porque el token antiguo no tiene el permiso nuevo: `python -m asistente_ia.google_auth`. Si no lo haces, el asistente te avisará con un mensaje claro.

### 18.2. Cómo probarlo

1. **Primero con la demo** (`CORREO_BACKEND=demo` en el `.env`): `python -m asistente_ia` y escribe "Responde a Laura que el viernes me va bien". Verás cómo el modelo busca el correo, propone `create_draft` con los datos y te pregunta `¿Apruebas? (s/n)`. Responde `n` y luego repite con `s`. En la demo no se envía nada de verdad.
2. **Después con tu Gmail** (`CORREO_BACKEND=google`): pídele que te escriba **a ti mismo** ("Mándame un correo a mi dirección con el asunto Prueba"). Antes de contestar a la pregunta, abre Gmail: el borrador ya está en **Borradores**. Si respondes `s`, se envía; si respondes `n`, se queda como borrador.
3. `pytest`.

### 18.3. Para qué sirve

Es el primer paso en el que el asistente **cambia algo de verdad**. Por eso sigue la regla del apartado 17: el modelo propone, tú decides y el código ejecuta.

- **Las herramientas de escritura no se le dan al agente.** `crear_grafo` separa las herramientas en dos listas. El agente (camino de consulta) solo recibe las de lectura. En `propose` el modelo ve también `create_draft` para poder **proponerla**, pero quien la ejecuta es el grafo.
- **Segunda barrera.** Si el modelo se inventara una llamada a `send_draft` (no la tiene, pero podría escribir el nombre), el nodo `tools` se niega a ejecutarla.
- **Borrador primero.** `prepare` crea el borrador antes de preguntarte, para que veas el correo tal cual saldría. Crear un borrador no tiene riesgo: nadie lo recibe. Solo `execute`, después de tu sí, lo envía con `send_draft`.

```
route → accion → propose ⇄ tools        (puede buscar el correo antes de proponer)
                 propose → prepare → approval_gate → sí → execute (send_draft) → END
                                                   → no → reject → END
                 propose → respond      (si no propone nada, por ejemplo para preguntarte un dato)
```

### 18.4. La propuesta es una llamada a herramienta

En el paso 6 la propuesta era una ficha con texto libre (`accion` y `detalles`). Para enviar un correo de verdad hacen falta datos exactos (para quién, asunto, texto, a qué correo responde), así que ahora la propuesta es una **llamada a herramienta**, el mismo tool calling del apartado 3:

```python
{"herramienta": "create_draft", "argumentos": {"para": "...", "asunto": "...", "texto": "...", "responder_a": "c1"}}
```

Los datos los describe la propia herramienta en su `description`, y en el paso 8 (calendario) servirá igual con `create_event`. La diferencia con el camino de consulta es que aquí la llamada **no se ejecuta**: se guarda en el estado y se te enseña.

Como el modelo pidió una herramienta, la conversación tiene que llevar su resultado (un `ToolMessage`) antes del siguiente mensaje. Lo añade `cerrar_propuesta` en `execute`, `reject` o si falla `prepare`. Así, además, el modelo recuerda qué pasó con su propuesta.

### 18.5. Un correo por dentro

- Un correo es texto con **cabeceras** (`To`, `Subject`...) y el mensaje, en formato **MIME**. `EmailMessage`, que viene con Python, lo monta por nosotros. `From` lo pone Gmail.
- La API de Gmail lo recibe entero codificado en **base64**, como cuando leemos (apartado 14).
- **Responder dentro del mismo hilo.** Si es una respuesta (`responder_a`), pedimos el correo original y usamos dos cosas: `threadId`, que agrupa el correo en la misma conversación de Gmail, y su `Message-ID`, que va en las cabeceras `In-Reply-To` y `References` para que el programa de correo de la otra persona también lo muestre como respuesta.
- `gmail.compose` permite crear borradores y enviarlos, pero no borrar correos.

### 18.6. Cómo encaja en el código

- `mcp_correo.py`: herramientas `create_draft` y `send_draft`, con su versión demo (no guarda nada: cada llamada arranca el servidor de cero) y la de Google.
- `google_gmail.py`: `crear_borrador_google` y `enviar_borrador_google`.
- `google_auth.py`: el permiso `gmail.compose`.
- `grafo.py`: las listas `HERRAMIENTAS_DE_ESCRITURA` y `HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER`, y los nodos `propose`, `prepare`, `execute` y `reject` nuevos. `tools` vuelve a `agent` o a `propose` según la intención. Desaparece `PropuestaDeAccion`.
- `__main__.py`: enseña la herramienta y sus datos antes de preguntar.
- `telegram_bot.py`: sigue rechazando las acciones hasta el paso 9. Ojo: con `CORREO_BACKEND=google`, el borrador sí se crea y se queda en Gmail.

### 18.7. Tests de este paso

- `tests/test_aprobacion.py`: el agente no recibe las herramientas de escritura, se crea el borrador y se para antes de enviarlo, con un sí se envía y con un no no, la conversación queda cerrada con su `ToolMessage`, puede buscar antes de proponer, si no propone nada contesta con su texto, el agente no puede ejecutar `send_draft` y Telegram rechaza las acciones.
- `tests/test_mcp_correo.py`: `create_draft` y `send_draft` de la demo a través del cliente MCP.
- `tests/llm_falso.py`: `HerramientaFalsa`, que imita una herramienta MCP y apunta con qué datos la llaman. `LLMFalso` apunta qué herramientas recibe en cada `bind_tools`.

## 19. Escribir en el calendario: crear, mover y borrar eventos

### 19.1. Qué tienes que hacer tú (una vez)

1. En **Google Cloud → Google Auth Platform → Acceso a los datos → Añadir o quitar permisos**, marca `calendar.events` y guarda. Puedes quitar `calendar.readonly`, porque `calendar.events` ya incluye leer.
2. Vuelve a iniciar sesión: `python -m asistente_ia.google_auth`.

### 19.2. Cómo probarlo

1. **Con la agenda de prueba** (`CALENDAR_BACKEND=demo`): `python -m asistente_ia` y escribe "Mueve el dentista al miércoles a la misma hora". Verás cómo el modelo busca el evento con `list_events`, propone `move_event` y, antes de preguntarte, te enseña qué evento se va a cambiar. Prueba también "Borra el gimnasio del jueves" y "Apúntame al gimnasio el sábado a las 10". En la demo no se guarda nada.
2. **Con tu calendario** (`CALENDAR_BACKEND=google`): crea primero un evento de prueba ("Apúntame Prueba mañana a las 12"), luego muévelo y al final bórralo. Comprueba cada paso en Google Calendar.
3. `pytest`.

### 19.3. Para qué sirve

Es el mismo camino que el correo (apartado 18): el modelo propone, tú decides y el código ejecuta. Solo cambian las herramientas:

| Herramienta | Tipo | Qué hace |
| --- | --- | --- |
| `list_events` | lectura | Eventos entre dos fechas, ahora con su `id` |
| `get_event` | lectura | Un evento a partir de su `id` |
| `create_event` | escritura | Crea un evento |
| `move_event` | escritura | Cambia la fecha y la hora de un evento |
| `delete_event` | escritura | Borra un evento |

Las tres de escritura están en `HERRAMIENTAS_DE_ESCRITURA` y en `HERRAMIENTAS_QUE_SE_PUEDEN_PROPONER`: el agente no las recibe, el modelo solo puede proponerlas y `execute` las ejecuta después de tu sí.

### 19.4. Identificadores de evento y por qué borrar exige más cuidado

- Para mover o borrar un evento hace falta su **id** (en Google, algo como `4k2j9a...`). El modelo lo consigue antes con `list_events`, igual que el id de un correo con `search_emails`.
- Un id no le dice nada a una persona. Si la tarjeta dijera "¿Borro el evento 4k2j9a?", aprobarías a ciegas. Por eso `prepare`, para `move_event` y `delete_event`, lee el evento con `get_event` y la propuesta lleva `evento_actual` ("Dentista, 2026-11-03 de 17:30 a 18:00"), que el main te enseña antes de preguntar.
- Si el id no existe (por ejemplo, el modelo se lo ha inventado), `prepare` para ahí y te lo dice: no se llega a pedir aprobación.
- Crear se puede deshacer borrando; borrar no se deshace desde el asistente (en Google Calendar el evento va a la papelera, pero tendrías que recuperarlo a mano). Por eso es la acción en la que más importa ver qué apruebas.
- `move_event` usa `patch`, que solo cambia el inicio y el fin. El título, la descripción o los invitados se quedan como estaban.
- En los eventos que se repiten (por ejemplo, cada lunes), `list_events` devuelve cada día como un evento suelto con su propio id, así que mover o borrar afecta solo a ese día.

### 19.5. Cómo encaja en el código

- `mcp_calendar.py`: las herramientas nuevas y un `id` en cada evento de la agenda de prueba (`e1` a `e5`).
- `google_calendar.py`: `leer_evento_google`, `crear_evento_google`, `mover_evento_google` y `borrar_evento_google`, y `convertir_evento` devuelve también el `id`.
- `google_auth.py`: `calendar.events` en lugar de `calendar.readonly`.
- `grafo.py`: las herramientas nuevas en las dos listas, `prepare` lee el evento antes de mover o borrar, y `execute` ejecuta la herramienta propuesta tal cual.
- `__main__.py`: enseña "Evento que se va a cambiar" cuando lo hay.

### 19.6. Tests de este paso

- `tests/test_mcp_calendar.py`: leer un evento por su id, un id que no existe, el formato de hora de Google y las herramientas de escritura de la demo a través del cliente MCP.
- `tests/test_aprobacion.py`: antes de borrar se enseña qué evento es, con un sí se borra, un id inventado no llega a la aprobación y crear un evento no necesita preparar nada.
