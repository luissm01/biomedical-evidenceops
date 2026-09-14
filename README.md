# EvidenceOps

Proyecto de aprendizaje de AI Engineering aplicado a evidencia biomédica pública.

## Estado

Fase 1: API FastAPI con comprobación de salud, registro y consulta de preguntas
biomédicas en memoria, con pruebas de su contrato HTTP. Las funcionalidades de
IA se incorporarán en milestones posteriores.

## Requisitos e instalación

- Python 3.14.
- uv instalado.

Desde la raíz del proyecto:

```bash
uv sync --locked
```

Este comando prepara `.venv/` con las dependencias de ejecución y desarrollo
registradas en `uv.lock`. No es necesario activar el entorno para usar `uv run`.

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

El almacenamiento es un diccionario en memoria para desarrollo local con un
solo proceso. Las preguntas se pierden al reiniciar o recargar Uvicorn y no se
comparten entre workers. La persistencia se incorporará cuando corresponda.

## Ejecutar las pruebas

```bash
uv run pytest
```

Las pruebas utilizan `TestClient` para verificar salud, creación y recuperación,
IDs distintos, límites de longitud y errores de validación y de recurso ausente,
sin arrancar Uvicorn. Cada test de preguntas utiliza un diccionario vacío propio.

Aviso conocido: Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`.
Puede aparecer un `DeprecationWarning` aunque la prueba pase.

## Estructura

```text
src/evidenceops/       Paquete Python de la aplicación
  main.py             API, modelos y almacenamiento temporal de preguntas
tests/                Pruebas automatizadas
docs/                 Contexto, estado, aprendizaje, decisiones y roadmap
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
