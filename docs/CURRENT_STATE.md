# EvidenceOps — Current State

Última actualización: 2026-09-15.

## Milestone actual

M0 — Project Foundation: completado.

M1 — Production Python & API Foundations: completado. El registro y consulta de
preguntas, sus contratos y pruebas, y CI están integrados en main mediante las
PR #3 y #4.

M2 — Application Architecture & Persistence: issue #6 implementada en
`feat/6-question-persistence`; PR #7 abierta para revisión.
Se eligió PostgreSQL local frente a SQLite, y SQLAlchemy ORM síncrono con
Psycopg y Alembic. No se usan servicios de pago.

## Implementado

- Proyecto Python 3.14 gestionado con uv y estructura `src/evidenceops/`.
- Configuración en `pyproject.toml`, `.python-version` y `uv.lock`.
- Dependencias de ejecución: FastAPI, Pydantic, Uvicorn, SQLAlchemy, Psycopg,
  Alembic y Pydantic Settings; resueltas en `uv.lock`.
- Dependencias de desarrollo: pytest y httpx2.
- `GET /health`: devuelve `200 OK` y `{"status": "ok"}`.
- `HealthCheckResponse` en `schemas.py`: modelo Pydantic con `status: Literal["ok"]`,
  utilizado como tipo de retorno y como `response_model` del endpoint.
- `tests/test_health.py`: comprueba estado HTTP y cuerpo JSON con TestClient.
- `POST /questions`: valida `QuestionCreate`, genera un UUID y devuelve `201`,
  `QuestionResponse` (`id`, `text`) y la cabecera `Location` de consulta.
- `GET /questions/{question_id}`: devuelve la pregunta con `200`, `404` si el
  UUID no existe y `422` si el identificador no es un UUID válido.
- `text`: cadena de 1 a 2.000 caracteres tras quitar espacios de los extremos;
  los campos adicionales se rechazan. Entradas inválidas devuelven `422`.
- Las preguntas se guardan en PostgreSQL mediante el modelo ORM `Question`.
  Una `Session` por petición, commit explícito en POST y rollback ante errores.
  Cada POST válido crea un registro, incluso con texto repetido.
- `Settings` valida `EVIDENCEOPS_DATABASE_URL` al arrancar. Un `SELECT 1`
  comprueba la conexión antes de aceptar peticiones.
- `compose.yaml` ejecuta PostgreSQL 18.6 local con volumen persistente y bases
  separadas de desarrollo y pruebas. `.env.example` documenta la configuración.
- Alembic aplica la migración inicial `20260914_01`, que crea `questions`.
- `tests/test_questions.py`: 16 casos, incluido reinicio de la aplicación.
  Las fixtures migran y limpian la base `evidenceops_test` entre pruebas.
- `tests/test_config.py`: 6 casos de URL válida, inválida y fallo de arranque.
- README con requisitos, instalación, ejecución, pruebas y estructura.
- `.github/workflows/ci.yml`: workflow CI para pushes y pull requests; la
  rama añade un servicio PostgreSQL efímero, migración explícita y pruebas.
  El servicio de CI usa autenticación `trust` y URLs sin contraseña fija;
  GitGuardian pasó tras retirar la contraseña de ejemplo del workflow.
- `.gitignore` excluye entorno virtual, cachés, artefactos y archivos `.env` locales.
- Git inicializado en la rama `main`; Milestone 0 registrado en el commit `14bebbb`.
- Remoto `origin`: `https://github.com/luissm01/biomedical-evidenceops.git`.
  El desarrollador ha confirmado la publicación en GitHub; `main` tiene configurado
  el seguimiento de `origin/main`.
- `AGENTS.md` y documentación de contexto, aprendizaje, decisiones y roadmap.

## Verificación

- Local: **23 passed, 1 warning** contra PostgreSQL 18.6 en Docker Desktop.
  Los tests de configuración, HTTP y persistencia pasan; la base de pruebas
  termina con cero preguntas.
- `alembic upgrade head` creó `questions` y registró `20260914_01`.
  Consultas SQL directas confirmaron `uuid` y `varchar(2000) NOT NULL`.
- Demostración HTTP: POST creó una pregunta; tras reiniciar FastAPI, GET la
  recuperó. La fila sobrevivió también a detener y reiniciar PostgreSQL,
  porque los datos están en el volumen nombrado.
- Con PostgreSQL detenido, Uvicorn terminó durante startup con
  `OperationalError` y código 3; no anunció startup completo.
- La primera ejecución de Alembic dentro del sandbox falló antes de conectar
  por restricción de red local; fuera del sandbox aplicó la migración.
- GitHub Actions de la PR #7 sobre `1981efb`: runs
  [push](https://github.com/luissm01/biomedical-evidenceops/actions/runs/34976823435)
  y [PR](https://github.com/luissm01/biomedical-evidenceops/actions/runs/34976828608),
  ambos correctos. GitGuardian Security Checks también pasó.

## Limitaciones y aviso conocido

La API depende de PostgreSQL para arrancar. Una caída posterior de PostgreSQL
todavía produce un error no controlado en los endpoints de datos. No hay aún
política de readiness ni recuperación; esos conceptos corresponden a M14.
No hay límite de registros, búsqueda de evidencia ni generación de respuestas.

Starlette utiliza el alias obsoleto `anyio.abc.BlockingPortal`, que genera un
`DeprecationWarning`. No impide que la prueba pase. Revisar su resolución cuando
corresponda actualizar dependencias; no se ha ocultado ni modificado código de terceros.

## Misión actual y siguiente paso

[Issue #6](https://github.com/luissm01/biomedical-evidenceops/issues/6),
`Persistir las preguntas más allá del proceso de la aplicación`, vinculada
a M2. El desarrollador creó la milestone y la issue para aprender el flujo de
GitHub. El agente preparó la rama `feat/6-question-persistence`.

El desarrollador eligió PostgreSQL local y SQLAlchemy ORM síncrono con Psycopg
y Alembic. También decidió que la API fallase al arrancar si PostgreSQL no
está disponible. Se explicaron el recorrido de la petición, modelos Pydantic
frente a ORM, Engine, pool, Session, transacciones, migración, configuración y
testing. La explicación no demuestra por sí sola comprensión profunda;
revisar la implementación y la evidencia con el desarrollador.

Siguiente paso inmediato: revisar la PR #7 con el desarrollador y, tras su
revisión, integrar y cerrar la issue #6. La documentación local pendiente se
publicó con este trabajo, no en una PR de cierre independiente.
El logging se reserva para M5 — Observability.

## Alcance pendiente

No existen todavía logging propio, Dockerización de la aplicación ni
componentes de IA. PostgreSQL se ejecuta en Docker local, pero FastAPI sigue
ejecutándose directamente con uv.
RAG, tools, agentes, MCP, observabilidad avanzada y cloud se introducirán cuando
corresponda según `ROADMAP.md` y las decisiones del desarrollador.

Los conceptos trabajados se mantienen en `LEARNING.md`; las decisiones técnicas,
en `DECISIONS.md`. La filosofía de aprendizaje se detalla en `AGENTS.md` y se
resume en `PROJECT_CONTEXT.md`; el roadmap no cambia.
