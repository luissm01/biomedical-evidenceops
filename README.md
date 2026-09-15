# EvidenceOps

Proyecto de aprendizaje de AI Engineering aplicado a evidencia biomédica pública.

## Estado

M2: API FastAPI con comprobación de salud, registro y consulta persistente de
preguntas biomédicas en PostgreSQL. Las funcionalidades de IA se incorporarán
en milestones posteriores.

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
Puede aparecer un `DeprecationWarning` aunque la prueba pase.

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
actual contiene 23 y se ejecuta también contra PostgreSQL.

## Estructura

```text
src/evidenceops/       Paquete Python de la aplicación
  config.py           Configuración validada desde variables de entorno
  database.py         Engine y ciclo de vida de sesiones SQLAlchemy
  main.py             Aplicación FastAPI y endpoints
  models.py           Modelos persistentes de SQLAlchemy
  schemas.py          Contratos HTTP de Pydantic
migrations/           Evolución reproducible del esquema PostgreSQL
docker/               Inicialización de servicios locales
tests/                Pruebas automatizadas
.github/workflows/    Automatización de pruebas en GitHub Actions
docs/                 Contexto, estado, aprendizaje, decisiones y roadmap
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
