# EvidenceOps

Proyecto de aprendizaje de AI Engineering aplicado a evidencia biomédica pública.

## Estado

M3: API FastAPI con registro y consulta de preguntas en PostgreSQL, y cliente
Gemini con salida estructurada validada. Todavía no hay endpoint HTTP de
generación: esa integración corresponde a #10.

## Requisitos e instalación

- Python 3.14.
- uv instalado.
- Docker con Docker Compose para ejecutar PostgreSQL localmente.

Desde la raíz del proyecto:

```bash
uv sync --locked
```

Este comando prepara `.venv/` con las dependencias de ejecución y desarrollo
registradas en `uv.lock`. No es necesario activar el entorno para usar `uv run`.

Crea la configuración local a partir del ejemplo y arranca PostgreSQL:

```bash
cp .env.example .env
docker compose up -d postgres
uv run alembic upgrade head
```

El contenedor crea dos bases: `evidenceops` para desarrollo y
`evidenceops_test` para las pruebas. Las credenciales del ejemplo son únicamente
locales. Los archivos `.env` reales no se versionan.

## Ejecutar la API

```bash
uv run uvicorn evidenceops.main:app --reload
```

La API escucha en `http://127.0.0.1:8000`. `--reload` permite recargar los cambios
durante el desarrollo. Detén el servidor con `Ctrl+C`.

Desde otra terminal:

```bash
curl -i http://127.0.0.1:8000/health
```

Respuesta esperada: `200 OK`, contenido JSON y cuerpo `{"status":"ok"}`.
Este endpoint comprueba que la aplicación responde; no verifica servicios externos.

## Registrar y consultar preguntas

```bash
curl -i http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"text": "¿Qué evidencia existe sobre la intervención X?"}'
```

Devuelve `201 Created`, un JSON con `id` (UUID generado por el servidor) y `text`,
y una cabecera `Location` con la ruta de consulta. Copia el identificador recibido:

```bash
curl -i http://127.0.0.1:8000/questions/ID_DEVUELTO
```

- `200 OK`: devuelve la pregunta registrada.
- `404 Not Found`: el UUID es válido, pero no existe una pregunta con ese ID.
- `422 Unprocessable Entity`: el cuerpo o el identificador no cumplen el contrato.

`text` debe ser una cadena de entre 1 y 2.000 caracteres después de quitar los
espacios de los extremos. Se rechazan campos adicionales, incluido un `id`
enviado por el cliente. Cada POST válido crea un registro nuevo, aunque repita
el texto. El endpoint registra preguntas; todavía no busca evidencia ni genera
respuestas. El contrato interactivo está disponible en `http://127.0.0.1:8000/docs`.

Las preguntas se almacenan en PostgreSQL y sobreviven al reinicio de la
aplicación. Alembic mantiene el esquema de la base de datos; una aplicación nueva
debe ejecutar `uv run alembic upgrade head` antes de atender peticiones.

## Primera integración Gemini

El SDK oficial `google-genai` se instala con `uv sync --locked`. Configura en
`.env` los valores del ejemplo; introduce personalmente la clave en
`EVIDENCEOPS_GEMINI_API_KEY` y mantenla fuera de Git.

| Variable | Valor inicial |
| --- | --- |
| `EVIDENCEOPS_GEMINI_API_KEY` | Sin valor; necesaria para la llamada manual |
| `EVIDENCEOPS_GEMINI_MODEL` | `gemini-3.6-flash` |
| `EVIDENCEOPS_GEMINI_MAX_OUTPUT_TOKENS` | `2048` |
| `EVIDENCEOPS_GEMINI_TIMEOUT_SECONDS` | `60` |

`Settings` exige modelo no vacío, tokens positivos y timeout positivo y finito.
La clave usa `SecretStr`; una clave vacía se trata como ausente. La API actual
puede arrancar sin ella: todavía no crea un generador. El script manual detecta
su ausencia antes de crear el cliente. Las variables de entorno prevalecen
sobre `.env`. La configuración común exige también la URL de PostgreSQL,
aunque esta llamada manual no conecta a la base de datos.

Para repetir voluntariamente la inferencia real:

```bash
uv run --locked python test_gemini.py
```

El desarrollador ya confirmó una primera llamada real correcta, con instrucción
separada de la pregunta, JSON Schema y validación Pydantic. El script utiliza
los límites configurados y cierra el cliente con `contextlib.closing`, también
si la generación falla. Importarlo o ejecutar pytest no hace inferencias.

`GeminiGenerator` reutiliza un cliente síncrono entre llamadas. Devuelve
`GeneratedContent(answer, limitations)` o `GenerationError`, conservando la
excepción original con `raise ... from ...`. Una salida inválida se clasifica
como `INVALID_OUTPUT`; los demás fallos quedan como `UNKNOWN` hasta #11.
Los mensajes propios no incluyen credenciales ni el cuerpo del proveedor;
la cadena original es diagnóstica y no debe exponerse como respuesta HTTP.

Se utiliza `interactions.create` con `store=False`. No se guardan respuestas en
PostgreSQL. Un esquema válido no demuestra veracidad biomédica; no hay búsqueda
de fuentes externas. En #10 EvidenceOps añadirá `external_sources_consulted: false`
al contrato HTTP, fuera de los campos generados por Gemini.

**Limitación del SDK 2.23.0:** aunque se solicita `HttpRetryOptions(attempts=0)`,
el SDK normaliza ese valor a 1 y su implementación de Interactions lo interpreta
como un reintento. El test con un 503 simulado verifica dos intentos, sin esperar
realmente. No hay retries propios. El timeout se aplica a cada petición HTTP;
no garantiza un presupuesto total de 60 segundos. Resolver la política y el
presupuesto total corresponde a #11, sin modificar internals del SDK en #9.
La opción pública está descrita en la [documentación del SDK](https://googleapis.github.io/python-genai/genai.html#genai.types.HttpRetryOptions).

## Ejecutar las pruebas

Antes, comprueba que PostgreSQL está arrancado con `docker compose up -d --wait postgres`.
Los tests usan exclusivamente la base `evidenceops_test` y aplican allí las
migraciones automáticamente.

```bash
uv run pytest
```

Las pruebas utilizan `TestClient` y la base dedicada `evidenceops_test` para
verificar salud, creación, persistencia tras reinicio, IDs distintos, límites de
longitud y errores. Cada test comienza y termina sin preguntas almacenadas.

Aviso conocido: Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`.
El SDK Gemini también avisa del uso de `typing._UnionGenericAlias`, obsoleto
para Python 3.17. Son dos `DeprecationWarning` de dependencias; no se ocultan.

## Integración continua

El workflow [CI](.github/workflows/ci.yml) ejecuta las pruebas en GitHub Actions
en cada push y pull request. Utiliza Ubuntu, la versión de Python indicada en
`.python-version` (3.14), uv 0.11.29 y un servicio PostgreSQL efímero.
Aplica las migraciones antes de ejecutar la suite.

Para reproducir sus comandos en local:

```bash
uv sync --locked --dev
uv run --locked alembic upgrade head
uv run --locked pytest
```

`--locked` exige que `uv.lock` esté actualizado respecto a `pyproject.toml`;
si no lo está, el comando falla en lugar de modificarlo automáticamente.
La sincronización incluye las dependencias de desarrollo necesarias para pytest.

Tras publicar los cambios, abre la pestaña **Actions** del repositorio y revisa
el workflow **CI**, trabajo **Tests**. Si falla, abre el paso que aparece en rojo:
un error de instalación ocurre antes de ejecutar los tests y debe investigarse
por separado de un fallo de sus assertions. Este workflow ejecuta pruebas;
no despliega la aplicación. La primera versión de CI pasó 16 tests; la suite
actual incluye además pruebas de Gemini con transporte HTTP simulado, sin
clave real ni acceso al proveedor, y se ejecuta también contra PostgreSQL.

## Estructura

```text
src/evidenceops/       Paquete Python de la aplicación
  config.py           Configuración validada desde variables de entorno
  database.py         Engine y ciclo de vida de sesiones SQLAlchemy
  generation.py       Protocol, contenido validado y error de aplicación
  gemini.py           Adaptador Gemini, prompt y validación de salida
  main.py             Aplicación FastAPI y endpoints
  models.py           Modelos persistentes de SQLAlchemy
  schemas.py          Contratos HTTP de Pydantic
migrations/           Evolución reproducible del esquema PostgreSQL
docker/               Inicialización de servicios locales
tests/                Pruebas automatizadas
.github/workflows/    Automatización de pruebas en GitHub Actions
docs/                 Contexto, estado, aprendizaje, decisiones y roadmap
test_gemini.py        Llamada manual explícita; sin inferencia al importar
compose.yaml          PostgreSQL local para desarrollo y pruebas
pyproject.toml        Configuración y dependencias declaradas
uv.lock               Versiones resueltas de las dependencias
.python-version       Versión local de Python
AGENTS.md             Reglas de colaboración y aprendizaje
```

Se versionan la configuración y `uv.lock`; `.venv/`, cachés y archivos `.env`
locales se excluyen mediante `.gitignore`.

## Documentación del proyecto

- [Estado actual y próximo paso](docs/CURRENT_STATE.md)
- [Contexto y objetivos](docs/PROJECT_CONTEXT.md)
- [Conceptos trabajados](docs/LEARNING.md)
- [Decisiones técnicas](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
