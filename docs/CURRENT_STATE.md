# EvidenceOps — Current State

Última actualización: 2026-09-06.

## Milestone actual

Milestone 0 — Project initialization: completado.

## Implementado

- Proyecto Python 3.14 gestionado con uv y estructura `src/evidenceops/`.
- Configuración en `pyproject.toml`, `.python-version` y `uv.lock`.
- Dependencias de ejecución: FastAPI y Uvicorn.
- Dependencias de desarrollo: pytest y httpx2.
- `GET /health`: devuelve `200 OK` y `{"status": "ok"}`.
- `tests/test_health.py`: comprueba estado HTTP y cuerpo JSON con TestClient.
- README con requisitos, instalación, ejecución, pruebas y estructura.
- `.gitignore` excluye entorno virtual, cachés, artefactos y archivos `.env` locales.
- Git inicializado en la rama `main`; el cierre se registra en el primer commit local.
- Remoto `origin`: `https://github.com/luissm01/biomedical-evidenceops.git`.
  Configurado por el desarrollador; la publicación mediante push no está confirmada.
- `AGENTS.md` y documentación de contexto, aprendizaje, decisiones y roadmap.

## Verificación

- El desarrollador ha probado el endpoint mediante curl.
- Experimento de regresión completado: cambiar el cuerpo a `{"status": "error"}`
  provoca un fallo en la comparación del JSON, manteniendo el estado HTTP 200.
- El desarrollador ha restaurado `{"status": "ok"}` y confirmado que pytest pasa.
- Verificación del agente tras restaurar el endpoint: **1 passed, 1 warning**.
  Se ejecutó `uv run --cache-dir /tmp/evidenceops-uv-cache --offline pytest`
  fuera del entorno restringido, donde la ejecución inicial quedó esperando.
- El aviso por utilizar httpx ha desaparecido tras migrar a httpx2.

## Aviso conocido

Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`, que genera un
`DeprecationWarning`. No impide que la prueba pase. Revisar su resolución cuando
corresponda actualizar dependencias; no se ha ocultado ni modificado código de terceros.

## Próximo paso

Al retomar, revisar el cierre de Milestone 0 y acordar el primer objetivo pequeño
de la fase de fundamentos de software. Todavía no se ha decidido el siguiente
endpoint ni se ha autorizado implementar fases posteriores.

## Alcance pendiente

No existen todavía modelos Pydantic propios, configuración de aplicación,
logging, Dockerización, CI, base de datos ni componentes de IA.
RAG, tools, agentes, MCP, observabilidad avanzada y cloud se introducirán cuando
corresponda según `ROADMAP.md` y las decisiones del desarrollador.

Los conceptos trabajados se mantienen en `LEARNING.md`; las decisiones técnicas,
en `DECISIONS.md`. En este cierre no cambian el roadmap ni el contexto del proyecto.
