# EvidenceOps — Current State

Última actualización: 2026-09-25.

## Milestone actual

M0, M1, M2 y M3 completados. La persistencia PostgreSQL se integró mediante PR #7.

Milestone actual: [M4 — Evaluation Foundations](https://github.com/luissm01/biomedical-evidenceops/milestone/4),
abierta y sin fecha límite. El dataset de #15 está integrado en `main` mediante
PR #18. La implementación de #16 está validada y se publica para revisión.

- [M3 — First LLM Integration](https://github.com/luissm01/biomedical-evidenceops/milestone/3)
  está cerrada; #8–#11 completadas y cerradas.
- PRs #12 y #13 integradas; la
  [PR #14](https://github.com/luissm01/biomedical-evidenceops/pull/14) de #11 está
  integrada en `main` (`68d18c2`). Tests y demostración manual HTTP con Gemini completos.
- Secuencia de M4:
  1. [#15 — Definir criterios de calidad y crear el primer evaluation dataset](https://github.com/luissm01/biomedical-evidenceops/issues/15).
  2. [#16 — Construir un runner de evaluación offline y establecer un baseline](https://github.com/luissm01/biomedical-evidenceops/issues/16).
  3. [#17 — Añadir evaluadores y detectar regresiones de calidad](https://github.com/luissm01/biomedical-evidenceops/issues/17).
- Dimensiones acordadas: `relevance`, `factual_correctness` y
  `prudence_and_limitations`. Dataset manual en `evaluation/cases.json`, versión
  `0.1`, con exactamente los 10 casos acordados: hechos de referencia,
  comportamiento esperado y afirmaciones prohibidas semánticas.
- #16 completada, validada y cerrada en GitHub: runner secuencial sobre Generator en `evaluation.py`, con
  Gemini explícito mediante `--live`, JSON por run y promoción validada de baseline.
  Baseline real pendiente únicamente de ejecución/promoción cuando Gemini disponga
  de cuota suficiente; no queda desarrollo pendiente de #16.
  Sin scores, evaluadores ni LLM-as-a-judge. Instrucciones en `evaluation/README.md`.
- `GenerationSettings` reutiliza la configuración de Gemini sin exigir PostgreSQL;
  `Settings` conserva la configuración y requisitos de la API.

## Implementado

- Python 3.14, uv y estructura `src/evidenceops/`.
- FastAPI: `GET /health`, `POST /questions` y `GET /questions/{question_id}`.
  También `POST /questions/{question_id}/generate`, sin body.
- Preguntas en PostgreSQL mediante SQLAlchemy síncrono y Psycopg. Una Session
  por petición, commit explícito y rollback ante errores. Alembic mantiene la
  migración `20260914_01`. No se guardan respuestas generadas.
- Configuración Pydantic Settings con prefijo `EVIDENCEOPS_` y `.env` local.
  La API comprueba PostgreSQL al arrancar; falla si no está disponible.
- `compose.yaml`: PostgreSQL 18.6 con volumen persistente y bases separadas de
  desarrollo y pruebas. CI utiliza PostgreSQL efímero.
- `generation.py`: `Generator` es un Protocol con una operación; devuelve
  `GeneratedContent(answer, limitations)` o lanza `GenerationError` con causa.
  Se exige texto no vacío tras recortar espacios; limitations puede ser vacía.
- `gemini.py`: único proveedor actual, SDK oficial `google-genai` 2.23.0.
  Instrucción separada de pregunta, JSON Schema derivado del modelo y validación
  Pydantic posterior. Sin dependencias de FastAPI, PostgreSQL ni tipos HTTP.
- Modelo inicial `gemini-3.6-flash`, máximo de salida 2.048 tokens y timeout
  de 60 segundos por operación de transporte, sin deadline total.
  Settings valida modelo, tokens y timeout finito.
  La clave se representa como `SecretStr`, no se versiona y no se imprime.
- Sin Generator inyectado, la clave ausente/vacía impide arrancar la API.
  No hay inferencia al arrancar ni al importar módulos; startup no comprueba
  la validez de la clave contra el proveedor.
- Cliente reutilizable con `close()`. `test_gemini.py` utiliza `closing` y solo
  hace una llamada real al ejecutarlo explícitamente. El desarrollador confirmó
  que ya realizó una primera inferencia estructurada correcta.
- Errores propios: TIMEOUT → 504, RATE_LIMIT → 429, AUTHENTICATION y
  PROVIDER_UNAVAILABLE → 503, INVALID_OUTPUT y UNKNOWN → 502. Mensajes HTTP
  fijos y seguros; se conserva la excepción original solo internamente.
- `httpx` se declara como dependencia directa para clasificar errores de
  transporte. No cambian las versiones resueltas.
- `store=False` en Interactions; sin persistencia propia de respuestas.
- Tests del adaptador con SDK real y transporte HTTP simulado: petición,
  respuesta, validación, cierre, reutilización, mensajes seguros y retries.
  Tests de configuración y contrato sin credenciales reales ni red.
- README, `.env.example`, dependencias y lock actualizados. Se conserva la mejora
  manual de AGENTS.md sobre confianza en confirmaciones y uso acotado de herramientas.

- Generación HTTP mediante `Depends` y `app.state.generator`: GeminiGenerator
  en producción y FakeGenerator en tests. El lifespan cierra solo el generador
  creado por la aplicación; libera el Engine incluso si falla ese cierre.
- Recupera `question.text` de una pregunta persistida y libera la Session antes
  de la inferencia. UUID inválido (`422`) y pregunta ausente (`404`) no invocan
  al generador. Devuelve `answer`, `limitations` y `external_sources_consulted:
  false`, establecido por EvidenceOps. No persiste respuestas ni hace retrieval.

## Verificación de #16

- Runner, metadata, checkpoint y promoción cubiertos con fake de Generator.
  Tests de envío exclusivo de question, causas seguras, continuación tras error,
  interrupción, dataset inválido y rechazo de baseline incompleto/incompatible.
  CLI exige --live, valida clave y cierra el cliente. Importación sin API/DB/SDK.
- Suite enfocada (runner/dataset/configuración): **30 passed**; tras añadir la
  comprobación de importación aislada, tests del runner: **24 passed**.
- Suite completa final: **111 passed, 2 DeprecationWarning conocidos**. El primer
  intento con acceso local encontró **81 passed y 29 errores de conexión/setup**
  por PostgreSQL no disponible; al estar healthy el contenedor existente, pasó.
- Ejecución real confirmada por el desarrollador: **1 caso exitoso y 9 con
  `rate_limit`**. No se obtuvieron outputs correctos para todos los casos y la
  promoción a baseline fue rechazada correctamente.
- **#16 completada y cerrada en GitHub** por decisión del desarrollador el 2026-09-25. El baseline
  real queda pendiente de ejecución/promoción cuando Gemini tenga cuota suficiente,
  como operación futura. La limitación es externa, de cuota del proveedor,
  no un fallo de implementación. No se modifica el runner, cambia de proveedor,
  paga cuota ni introduce retries artificiales para obtenerlo.
- `git diff --check`: correcto.
- LEARNING.md no cambia: el código y tests generados no acreditan aprendizaje
  práctico adicional. D014 registra el diseño aprobado. ROADMAP.md y
  PROJECT_CONTEXT.md no cambian. Implementación, tests y documentación se publican
  juntos en la rama `feat/16-offline-evaluation`, por petición del desarrollador.

## Verificación de #15

- `evaluation/cases.json`: versión `0.1`, diez casos transcritos del texto acordado
  sin correcciones factuales. Revisión prudente de coherencia; no es una revisión
  sistemática de literatura ni se añaden fuentes al formato del dataset.
- Un test estructural comprueba JSON, versión, número de casos, IDs únicos,
  campos y listas no vacíos, dimensiones permitidas y ausencia de campos extra.
  No evalúa calidad de respuestas ni llama al proveedor.
- `uv run --locked pytest`: **87 passed, 2 DeprecationWarning conocidos**.
  El intento con acceso local encontró 29 errores de conexión/setup por PostgreSQL
  apagado (58 tests pasaron); tras arrancar Docker Desktop y el contenedor existente,
  la suite completa pasó. Se usó caché uv en `/tmp/evidenceops-uv-cache`.
- `git diff --check`: correcto. Sin nuevas dependencias, cambios en `.env` ni
  llamadas reales a Gemini. Los cambios documentales locales previos se conservan.

## Verificación de #11

- `uv sync --locked --dev`: correcto; `httpx` pasa a dependencia directa,
  sin actualizar versiones de paquetes.
- Suite completa, `uv run --locked pytest`: **86 passed, 2 warnings** contra
  PostgreSQL local; incluye API, configuración, contratos, lifecycle y adaptador.
  Sin inferencias reales, credenciales reales ni esperas de retry en tests.
- Cobertura de todas las causas y mensajes HTTP, número máximo de intentos,
  ausencia de retry en 429/autenticación/transporte, Retry-After, recuperación
  tras 503 y flujo completo HTTP/PostgreSQL/SDK con transporte simulado.
- Revisión final: corregidos fixtures de salida inválida para usar `steps/content`
  reales; documentadas discrepancias del SDK y ausencia de deadline total.
- Demostración manual HTTP con Gemini realizada y confirmada por el desarrollador
  el 2026-09-17. No se repite la inferencia para verificar su confirmación.
- `git diff --check`: correcto. `.env` no se modifica.

## Verificación de #10

- `uv sync --locked --dev` y `uv run --locked alembic upgrade head`: correctos.

- `uv run pytest`: **62 passed, 2 warnings**, con acceso a PostgreSQL local.
  El intento restringido encontró errores de acceso; la ejecución autorizada pasó.
- Tests HTTP con FakeGenerator, sin clave ni inferencias reales. Se añaden
  pruebas de ownership, startup sin clave, cierre y devolución de la conexión
  antes de generar. El test de reinicio también inyecta el fake.
- `git diff --check`: correcto. `.env` no se modifica ni se incluye en Git.
- Se mantienen los dos DeprecationWarning conocidos, sin cambios de dependencias.

## Verificación previa de #9

- `uv sync --locked --dev`: correcto (caché en `/tmp/evidenceops-uv-cache` por
  restricciones de escritura del entorno).
- Pruebas sin PostgreSQL: **37 passed, 2 warnings**.
- `uv run --locked alembic upgrade head`: correcto.
- `uv run --locked pytest`: **54 passed, 2 warnings** contra PostgreSQL.
- El primer intento falló porque PostgreSQL estaba apagado. Se arrancaron Docker
  Desktop y el contenedor existente desde el ejecutable de Windows; la repetición
  de migraciones y suite completa terminó correctamente. La integración del CLI
  Docker con esta WSL sigue sin estar disponible.
- `git diff --check`: correcto. `.env` está ignorado y fuera del índice.
- PR #12 integrada en `main`; GitGuardian Security Checks y las
  [últimas pruebas de CI](https://github.com/luissm01/biomedical-evidenceops/actions/runs/35021321065)
  pasaron. `Closes #9` cerró la issue automáticamente.
- No se han repetido inferencias reales ni expuesto la clave local.

## Limitaciones y avisos conocidos

SDK 2.23.0: máximo un retry para HTTP 408/500/502/503/504, ninguno para
400/401/403/429, salida inválida o errores de transporte. El SDK traduce estos
últimos antes de su mecanismo de retry; se verifica ese comportamiento real.
No hay retries propios. Un retry puede duplicar consumo/cuota si la primera
inferencia se ejecutó pero no se recibió su respuesta.
Backoff de 0,5 s, pero Retry-After/retry-after-ms pueden
alargarlo. Los timeouts HTTPX no son deadlines: no se garantiza una duración
total de 120,5 s ni se implementa cancelación externa.

Dos `DeprecationWarning` de dependencias: Starlette usa
`anyio.abc.BlockingPortal`; google-genai usa `typing._UnionGenericAlias`,
previsto para eliminación en Python 3.17. No se ocultan ni se modifica código
de terceros para resolverlos.

Una caída de PostgreSQL posterior al arranque aún produce un error no controlado
en los endpoints de datos. Readiness y recuperación corresponden a M14.
No hay búsqueda de evidencia, citas verificadas, RAG ni evaluación factual.

## Siguiente paso exacto

#16 completada; queda únicamente la operación futura de ejecutar un run real
cuando Gemini disponga de cuota suficiente y promoverlo si todos los casos tienen
éxito. No es desarrollo pendiente ni bloquea el cierre de #16. #17 no se inicia
en esta tarea. El baseline permitirá comparación manual por case_id, sin
certificar la calidad de los outputs.

Gemini es el único proveedor de M3. Ollama queda aplazado por decisión explícita
del desarrollador; podría reconsiderarse cuando Evaluation lo justifique.
La secuencia canónica no cambia. Logging y observabilidad se reservan para M5.

LEARNING.md refleja solo el trabajo real del desarrollador; DECISIONS.md recoge
también el alcance del dataset inicial. ROADMAP.md y PROJECT_CONTEXT.md no cambian.
