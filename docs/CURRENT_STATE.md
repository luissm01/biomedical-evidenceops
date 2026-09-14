# EvidenceOps — Current State

Última actualización: 2026-09-14.

## Milestone actual

Milestone 0 — Project initialization: completado.

Fase 1 — Software Engineering Foundations: registro y consulta de preguntas
implementados y probados. El desarrollador ha confirmado comprender los modelos,
la validación y el recorrido de los endpoints tras la explicación guiada.

## Implementado

- Proyecto Python 3.14 gestionado con uv y estructura `src/evidenceops/`.
- Configuración en `pyproject.toml`, `.python-version` y `uv.lock`.
- Dependencias de ejecución: FastAPI, Pydantic y Uvicorn.
- Pydantic declarado directamente como `pydantic>=2.13.5`; `uv.lock` mantiene
  la versión `2.13.5` que ya utilizaba FastAPI.
- Dependencias de desarrollo: pytest y httpx2.
- `GET /health`: devuelve `200 OK` y `{"status": "ok"}`.
- `HealthCheckResponse` en `main.py`: modelo Pydantic con `status: Literal["ok"]`,
  utilizado como tipo de retorno y como `response_model` del endpoint.
- `tests/test_health.py`: comprueba estado HTTP y cuerpo JSON con TestClient.
- `POST /questions`: valida `QuestionCreate`, genera un UUID y devuelve `201`,
  `QuestionResponse` (`id`, `text`) y la cabecera `Location` de consulta.
- `GET /questions/{question_id}`: devuelve la pregunta con `200`, `404` si el
  UUID no existe y `422` si el identificador no es un UUID válido.
- `text`: cadena de 1 a 2.000 caracteres tras quitar espacios de los extremos;
  los campos adicionales se rechazan. Entradas inválidas devuelven `422`.
- Almacenamiento temporal en un diccionario por proceso, acordado con el
  desarrollador. Cada POST válido crea un registro, incluso con texto repetido.
- `tests/test_questions.py`: 15 casos de creación, recuperación, IDs distintos,
  límites de longitud, datos inválidos y errores de consulta; almacenamiento
  aislado por test mediante una fixture.
- README con requisitos, instalación, ejecución, pruebas y estructura.
- `.github/workflows/ci.yml`: workflow CI para pushes y pull requests, con
  un trabajo Tests en Ubuntu, Python desde `.python-version` y uv 0.11.29.
  Ejecuta `uv sync --locked --dev` y `uv run --locked pytest`; acciones fijadas
  por SHA y permisos de lectura. Publicado en la rama de CI; primera ejecución
  remota correcta, pendiente de revisión e integración en main.
- `.gitignore` excluye entorno virtual, cachés, artefactos y archivos `.env` locales.
- Git inicializado en la rama `main`; Milestone 0 registrado en el commit `14bebbb`.
- Remoto `origin`: `https://github.com/luissm01/biomedical-evidenceops.git`.
  El desarrollador ha confirmado la publicación en GitHub; `main` tiene configurado
  el seguimiento de `origin/main`.
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
- Revisión del 2026-09-13: **1 passed, 1 warning** al ejecutar pytest con uv
  fuera del entorno restringido. Dentro de este volvió a quedar esperando.
- Revisión tras incorporar `HealthCheckResponse`: **1 passed, 1 warning**.
  Comprobaciones adicionales del agente: el modelo rechaza un campo `status`
  ausente y el valor `"error"`; OpenAPI enlaza la respuesta con el modelo y
  declara `status` obligatorio con valor constante `"ok"`.
- Tras declarar Pydantic directamente: `uv run --locked --offline pytest`
  fuera del entorno restringido termina con **1 passed, 1 warning**.
  La actualización del lockfile no cambia las versiones de los paquetes.
- Tras implementar preguntas: **16 passed, 1 warning** con
  `uv run --locked --offline pytest` fuera del entorno restringido.
- Preparación de CI: sincronización con `--locked --dev --offline` correcta;
  suite de nuevo con **16 passed, 1 warning**, Python 3.14.4 y uv 0.11.29,
  fuera del sandbox. Se utilizó la caché `/tmp/evidenceops-uv-cache`.
  YAML parseado correctamente y `git diff --check` sin errores.
- CI remoto por push verificado: [ejecución 34822739721](https://github.com/luissm01/biomedical-evidenceops/actions/runs/34822739721),
  commit `4e5c831`, **16 passed, 1 warning**, Python 3.14.7 y uv 0.11.29.
  `.python-version` fija la serie 3.14, no su versión de parche; localmente se
  verificó con 3.14.4. El aviso de Starlette sigue visible.

## Limitaciones y aviso conocido

Las preguntas se pierden al reiniciar o recargar el servidor y no se comparten
entre procesos. El almacenamiento no tiene límite de registros; esta versión
está destinada a desarrollo local temporal con un único proceso. No hay todavía
persistencia, búsqueda de evidencia ni generación de respuestas.

Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`, que genera un
`DeprecationWarning`. No impide que la prueba pase. Revisar su resolución cuando
corresponda actualizar dependencias; no se ha ocultado ni modificado código de terceros.

## Próximo paso

La tarea de modelos y endpoints queda cerrada tras la revisión del desarrollador.
La misión de testing y CI tiene el workflow publicado y una ejecución remota correcta.
Se han explicado los tests, su aislamiento y el recorrido de ejecución del
sistema; el desarrollador ha autorizado avanzar a la preparación de CI.

El trabajo está organizado en el milestone [Fase 1](https://github.com/luissm01/biomedical-evidenceops/milestone/1):
- [Issue #1](https://github.com/luissm01/biomedical-evidenceops/issues/1): preguntas,
  rama `feat/1-question-api`, con commits separados para la política de aprendizaje
  previa y para los endpoints con sus tests. [PR #3](https://github.com/luissm01/biomedical-evidenceops/pull/3), base main.
- [Issue #2](https://github.com/luissm01/biomedical-evidenceops/issues/2): testing y CI,
  rama `ci/2-github-actions`, basada en la anterior para ejecutar los 16 tests.
  [PR #4](https://github.com/luissm01/biomedical-evidenceops/pull/4), base `feat/1-question-api`.

Siguiente paso: revisar las dos PRs con el desarrollador.
Integrar primero preguntas en main; después actualizar la base de la PR de CI
hacia main y comprobar sus tests antes de integrarla. No se ha autorizado ni
realizado el merge. Las issues permanecen abiertas hasta completar la revisión.

Preferencia de colaboración: avisar explícitamente al cambiar de tarea grande
para que el desarrollador pueda continuar en otro chat, dejando aquí un punto
de continuación concreto.

## Alcance pendiente

No existen todavía configuración de aplicación, logging, Dockerización,
base de datos ni componentes de IA.
RAG, tools, agentes, MCP, observabilidad avanzada y cloud se introducirán cuando
corresponda según `ROADMAP.md` y las decisiones del desarrollador.

Los conceptos trabajados se mantienen en `LEARNING.md`; las decisiones técnicas,
en `DECISIONS.md`. La filosofía de aprendizaje se detalla en `AGENTS.md` y se
resume en `PROJECT_CONTEXT.md`; el roadmap no cambia.
