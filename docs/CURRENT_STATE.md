# Estado actual

Actualizado: 2026-10-06. Distingue código versionado de trabajo local pendiente.

## Presente

- **M7 — Retrieval & Embeddings**: transformación de #38 implementada:
  una unidad por publicación (`whole-publication-v1`),
  título + abstract, identidad determinista, fingerprint del texto y procedencia.
  Sin contenido recuperable devuelve `None`; no divide ni trunca el texto.
  [Contrato y transformación](../src/evidenceops/chunking.py).
  Diseño posterior: MedCPT local con encoders de consultas/artículos,
  dot product, PostgreSQL + pgvector y filtro inicial por año de publicación.
  Decisiones acordadas en [D024](decisions/D024-retrieval-baseline-and-embeddings.md).
  Todavía no hay
  embeddings, persistencia de unidades ni búsqueda vectorial.
- **M6 — Biomedical Data Ingestion** implementado: PubMed/NCBI E-utilities,
  parsing y contrato normalizado, persistencia con upsert atómico y CLI
  `evidenceops ingest` sobre un servicio reutilizable. El pipeline coordina lotes,
  transacciones por documento, fallos parciales y resumen de resultados.
  [Plan M6 completado](plans/completed/m6-biomedical-data-ingestion.md).
  Decisiones en [D021](decisions/D021-biomedical-ingestion-source-and-contract.md),
  [D022](decisions/D022-biomedical-publication-persistence.md) y
  [D023](decisions/D023-biomedical-ingestion-pipeline.md).
  Validación determinista sin red; no se ha realizado una demo real de PubMed.
- **M5 — Observability** completado. El
  [plan M5](plans/completed/m5-observability.md) conserva su orden.
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

El siguiente paso técnico, bajo un nuevo encargo, es integrar embeddings y almacenamiento en
#39 según D024, concretando límites del encoder y compatibilidad de representaciones.
Cuando exista cuota y se solicite, obtener/promover/revisar el baseline real.
Los comandos y requisitos de pruebas viven en el [README](../README.md);
la secuencia futura, en el roadmap.
