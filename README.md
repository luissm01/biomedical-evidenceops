# EvidenceOps

Proyecto de aprendizaje de AI Engineering aplicado a evidencia biomédica pública.

## Estado

Base de Milestone 0: aplicación FastAPI mínima con `GET /health` y una prueba
automatizada de su contrato HTTP. EvidenceOps utilizará evidencia biomédica
pública; las funcionalidades de IA se incorporarán en milestones posteriores.

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

## Ejecutar las pruebas

```bash
uv run pytest
```

La prueba utiliza `TestClient` para verificar el estado HTTP y el cuerpo JSON
sin arrancar Uvicorn. Se ha comprobado que detecta un cambio deliberado de
`"ok"` a `"error"` en la respuesta.

Aviso conocido: Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`.
Puede aparecer un `DeprecationWarning` aunque la prueba pase.

## Estructura

```text
src/evidenceops/       Paquete Python de la aplicación
  main.py             Aplicación FastAPI y endpoint /health
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
