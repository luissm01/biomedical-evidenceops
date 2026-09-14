# EvidenceOps — Current State

Última actualización: 2026-09-14.

## Milestone actual

Milestone 0 — Project initialization: completado.

Fase 1 — Software Engineering Foundations: registro y consulta de preguntas
implementados y probados. El desarrollador ha confirmado comprender los modelos,
la validación y el recorrido de los endpoints tras la explicación guiada.
Testing y CI completados e integrados en main mediante PR #3 y PR #4.
Las issues #1 y #2 están cerradas; Fase 1 continúa.

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
  por SHA y permisos de lectura. Integrado en main y verificado en GitHub.
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
- CI de main tras integrar ambas PRs: [ejecución 34822948154](https://github.com/luissm01/biomedical-evidenceops/actions/runs/34822948154),
  commit `a9cd353`, resultado correcto.
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

**Testing y CI completados.** El desarrollador ha integrado las PRs desde GitHub:
- [PR #3](https://github.com/luissm01/biomedical-evidenceops/pull/3): preguntas y tests,
  integrada en main; [issue #1](https://github.com/luissm01/biomedical-evidenceops/issues/1) cerrada.
- [PR #4](https://github.com/luissm01/biomedical-evidenceops/pull/4): GitHub Actions,
  integrada en main; [issue #2](https://github.com/luissm01/biomedical-evidenceops/issues/2) cerrada.
- [Milestone Fase 1](https://github.com/luissm01/biomedical-evidenceops/milestone/1)
  sigue abierto: estas dos issues no representan todo el alcance de la fase.

Main remoto está en `a9cd353` al verificar el cierre. El agente detectó los merges
al consultar GitHub; no los realizó. La rama local de cierre es
`docs/session-handoff`, basada en ese main, con esta actualización documental.
Antes de comenzar, consultar su PR y sincronizar main según el estado real.
No recrear las issues ni repetir la implementación de preguntas o CI.

**Siguiente misión propuesta: configuración de aplicación y logging básico.**

Problema inicial: poder distinguir el entorno de ejecución y obtener información
útil para investigar peticiones y errores sin depender de inspeccionar el código.
El alcance exacto se acordará al comenzar; todavía no existe una issue ni código
para esta misión.

Primeros pasos del próximo chat:
1. Leer AGENTS.md, CURRENT_STATE.md, LEARNING.md y DECISIONS.md. Comprobar estado
   local, main remoto y CI; resolver primero la integración del cierre documental
   si sigue pendiente.
2. Proponer un alcance pequeño: configuración necesaria mediante variables de
   entorno y logs útiles de la API, sin registrar el texto biomédico por defecto.
   Explicar el problema y las alternativas antes de escoger herramientas.
3. Crear una issue en Fase 1 con criterios de cierre, y una rama desde main.
4. Implementar únicamente el alcance acordado, verificar comportamiento y CI,
   documentar y abrir PR. No introducir persistencia ni IA por anticipación.

Contexto pedagógico: el desarrollador pidió una explicación estructural del
sistema antes de continuar. Priorizar problema, piezas y recorrido de ejecución
antes de detallar sintaxis. Fixtures, monkeypatch y parametrize están explicados,
pero no se ha confirmado dominio práctico; no convertir su revisión en un examen.
El agente preparó issues, ramas, commits y PRs; no registrar como dominados todos
los mecanismos de GitHub únicamente por haberse automatizado.

Preferencia de colaboración: cambiar de chat al pasar a una misión grande,
dejando un punto de continuación concreto. El roadmap conserva su alcance actual.

## Alcance pendiente

No existen todavía configuración de aplicación, logging, Dockerización,
base de datos ni componentes de IA.
RAG, tools, agentes, MCP, observabilidad avanzada y cloud se introducirán cuando
corresponda según `ROADMAP.md` y las decisiones del desarrollador.

Los conceptos trabajados se mantienen en `LEARNING.md`; las decisiones técnicas,
en `DECISIONS.md`. La filosofía de aprendizaje se detalla en `AGENTS.md` y se
resume en `PROJECT_CONTEXT.md`; el roadmap no cambia.
