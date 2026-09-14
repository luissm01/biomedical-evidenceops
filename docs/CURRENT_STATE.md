# EvidenceOps — Current State

Última actualización: 2026-09-14.

## Milestone actual

Milestone 0 — Project initialization: completado.

Fase 1 — Software Engineering Foundations: registro y consulta de preguntas
implementados y probados. El desarrollador ha confirmado comprender los modelos,
la validación y el recorrido de los endpoints tras la explicación guiada.
Testing y CI implementados y verificados en GitHub; falta revisar e integrar las PRs.

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

- Suite actual: **16 passed, 1 warning**. Incluye salud y 15 casos de preguntas.
- Local: Python 3.14.4, uv 0.11.29; sincronización correcta con
  `uv sync --locked --dev --cache-dir /tmp/evidenceops-uv-cache --offline` y
  pruebas con `uv run --locked --cache-dir /tmp/evidenceops-uv-cache --offline pytest`.
  TestClient queda esperando dentro del sandbox; fuera termina correctamente.
  No interpretar esa espera como fallo de una assertion ni cambiar tests por ello.
- GitHub Actions: Python 3.14.7, uv 0.11.29; 16 tests correctos y el mismo aviso.
  Eventos verificados sobre `db1efd3`:
  [push](https://github.com/luissm01/biomedical-evidenceops/actions/runs/34822825578) y
  [pull request](https://github.com/luissm01/biomedical-evidenceops/actions/runs/34822828806).
  Estos enlaces son evidencia de ese commit; los commits posteriores de
  documentación disparan nuevas ejecuciones que deben consultarse antes del merge.
- `.python-version` fija la serie 3.14, no su versión de parche.
- YAML parseado correctamente y `git diff --check` sin errores.
- Regresión de /health trabajada por el desarrollador: observó fallar el test al
  devolver `error` en lugar de `ok`, restauró el código y confirmó que pasaba.

## Limitaciones y aviso conocido

Las preguntas se pierden al reiniciar o recargar el servidor y no se comparten
entre procesos. El almacenamiento no tiene límite de registros; esta versión
está destinada a desarrollo local temporal con un único proceso. No hay todavía
persistencia, búsqueda de evidencia ni generación de respuestas.

Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`, que genera un
`DeprecationWarning`. No impide que la prueba pase. Revisar su resolución cuando
corresponda actualizar dependencias; no se ha ocultado ni modificado código de terceros.

## Cierre de sesión y siguiente misión

La implementación de modelos y endpoints está revisada a nivel de aprendizaje;
su entrega mediante PR sigue pendiente.
La misión de testing y CI tiene el workflow publicado y una ejecución remota correcta.
Se han explicado los tests, su aislamiento y el recorrido de ejecución del
sistema; el desarrollador ha autorizado avanzar a la preparación de CI.

Rama local al cerrar: `ci/2-github-actions`, publicada en origin. `main` conserva
`9a35c4d`; todavía no contiene los endpoints de preguntas ni CI. No volver a
implementar estas tareas ni crear issues duplicadas.

El trabajo está organizado en el milestone [Fase 1](https://github.com/luissm01/biomedical-evidenceops/milestone/1):

- [Issue #1](https://github.com/luissm01/biomedical-evidenceops/issues/1): preguntas,
  rama `feat/1-question-api`, con commits separados para la política de aprendizaje
  previa y para los endpoints con sus tests. [PR #3](https://github.com/luissm01/biomedical-evidenceops/pull/3), base main.
- [Issue #2](https://github.com/luissm01/biomedical-evidenceops/issues/2): testing y CI,
  rama `ci/2-github-actions`, basada en la anterior para ejecutar los 16 tests.
  [PR #4](https://github.com/luissm01/biomedical-evidenceops/pull/4), base `feat/1-question-api`.

**Primera misión del próximo chat: revisión e integración de las PRs.**

1. Leer AGENTS.md y este documento; comprobar rama, árbol de trabajo y estado
   remoto de PR #3 y PR #4, por si el desarrollador ha actuado desde GitHub.
2. Guiar una revisión breve de PR #3: contrato HTTP, límites del almacenamiento
   y qué comportamientos protegen los tests. Evitar repetir la explicación básica
   salvo que el desarrollador la necesite.
3. Revisar PR #4: recorrido del workflow, resultado de Tests y diferencia entre
   fallo de instalación, test fallido y warning.
4. Tras la aprobación del desarrollador, integrar primero PR #3. Mantener su rama
   hasta actualizar la base de PR #4 a main; revisar el diff y CI tras el cambio.
   Si el método de merge cambia la historia, ajustar la rama de CI preservando
   sus cambios, sin duplicar los de preguntas.
5. Integrar PR #4 cuando corresponda, comprobar el estado de las issues #1 y #2,
   sincronizar main y actualizar este documento. No se ha realizado ni autorizado
   todavía el merge; la autorización previa cubrió commits, publicación y PRs.

Después de integrar: proponer la siguiente misión de Fase 1, configuración de
aplicación y logging básico, partiendo de una necesidad concreta de ejecución o
diagnóstico. Es una propuesta para acordar alcance, no una misión ya iniciada.
Crear su issue con criterios de cierre antes de implementar. No añadir aún
persistencia ni componentes de IA ni ampliar el roadmap.

Contexto pedagógico: el desarrollador pidió una explicación estructural del
sistema antes de continuar. Priorizar problema, piezas y recorrido de ejecución
antes de detallar sintaxis. Fixtures, monkeypatch y parametrize están explicados,
pero no se ha confirmado dominio práctico; no convertir su revisión en un examen.

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
