# Estado actual

Actualizado: 2026-10-01. Distingue código versionado de trabajo local pendiente.

## Presente

- **M5 — Observability** completado: #21, #22 y #23 cerradas, con sus PRs
  integradas. El [plan M5](plans/completed/m5-observability.md) conserva su orden.
  **M6 — Biomedical Data Ingestion** está iniciada: #28 está cerrada y sus
  decisiones documentadas. PubMed/NCBI E-utilities es la fuente
  inicial; el contrato normalizado y la identidad de ingestión están en
  [D021](decisions/D021-biomedical-ingestion-source-and-contract.md).
  [Plan M6](plans/m6-biomedical-data-ingestion.md). Aún no hay implementación.
- API para registrar/consultar preguntas persistidas en PostgreSQL y generar
  respuestas efímeras mediante Gemini o DeepSeek, seleccionados por configuración. [Límites y flujo](ARCHITECTURE.md).
- Evaluación offline con runs trazables, promoción de baseline y revisión humana
  por caso/dimensión, con agregación y comparación de regresiones.
  [Procedimiento](../evaluation/README.md).
- #21: logs JSON y correlación HTTP. #22: métricas Prometheus de generaciones,
  errores, latencia y tokens observados para Gemini y DeepSeek en `GET /metrics`.
  #23: spans OpenTelemetry para HTTP, generación y proveedor, con correlación
  en logs y exportación opcional a consola.

## Limitaciones relevantes

- No existe todavía un baseline real completo y revisado: la cuota impidió
  completar el run. Obtenerlo es una operación futura, no desarrollo pendiente
  de M4 ni prueba de calidad del modelo. No cambiar proveedor, pagar cuota o
  añadir retries artificiales para conseguirlo.
- Sin retrieval, fuentes consultadas ni citas verificadas. La revisión humana
  aplica una rúbrica limitada; no hay validación factual automática.
- Timeout de transporte sin deadline total; un retry puede duplicar consumo.
  [Política y motivos](decisions/D011-gemini.md).
- Una caída de PostgreSQL tras startup aún produce errores no controlados en
  endpoints de datos. Readiness y recuperación quedan para M14.
- Dos DeprecationWarning conocidos de dependencias: Starlette usa
  `anyio.abc.BlockingPortal`; google-genai usa `typing._UnionGenericAlias`
  (previsto para eliminación en Python 3.17). No se ocultan.
- En el entorno WSL usado previamente no estaba disponible la integración del
  CLI Docker; Docker Desktop y el contenedor existente se arrancaron desde
  Windows. Es una limitación de ese entorno, no un requisito del proyecto.

## Siguiente trabajo

Continuar M6 por #29 (adquisición, parsing y normalización), seguida de #30
(persistencia idempotente) y #31 (pipeline).
Cuando exista cuota y se solicite, obtener/promover/revisar el baseline real.
Los comandos y requisitos de pruebas viven en el [README](../README.md);
el alcance pendiente, en el plan activo.
