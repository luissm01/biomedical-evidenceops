# Estado actual

Actualizado: 2026-10-15. Distingue código versionado de trabajo local pendiente.

## Presente

- **M8 — RAG v1**, #44: diseño acordado del contrato, construcción
  de contexto y política de citas en [D026](decisions/D026-rag-v1-contract-context-and-citations.md).
  #45 implementada y aceptada por el desarrollador: servicio
  RAG independiente, contexto top-5 con presupuesto, instrucciones por llamada,
  fuentes desde la aplicación y validación determinista de citas/abstención.
  Tests con dobles y transporte simulado; demo manual local disponible en
  `demo_rag_local.py`, sin inferencias reales ejecutadas por el agente.
  #46 implementada y aceptada por el desarrollador: `POST /rag`
  con query/año y respuesta estructurada, traducción segura de errores y
  observabilidad de operación/retrieval/contexto/generación con M5.
  Tests deterministas HTTP y PostgreSQL/pgvector; demo API preparada en el
  [README](../README.md#rag-desde-la-api-m8--46), sin inferencias reales del agente.
  Diagnóstico seguro de citas: motivo, campo y localización en logs/spans,
  sin volcar contenido ni modificar reglas de D026. Los logs antiguos del fallo
  reportado solo permiten ubicarlo tras DeepSeek, no reconstruir el motivo.
  La prueba HTTP real aportada por el desarrollador termina en rechazo de citas
  tras completar retrieval/contexto/DeepSeek; no acredita una respuesta válida
  ni calidad semántica. Cierre de #46 aceptado con este límite.
  Decisiones de integración en [D027](decisions/D027-rag-http-errors-and-observability.md).

- **M7 — Retrieval & Embeddings** completado: transformación de #38 implementada:
  una unidad por publicación (`whole-publication-v1`),
  título + abstract, identidad determinista, fingerprint del texto y procedencia.
  Sin contenido recuperable devuelve `None`; no divide ni trunca el texto.
  [Contrato y transformación](../src/evidenceops/chunking.py).
  MedCPT local con encoders de consultas/artículos,
  dot product, PostgreSQL + pgvector y filtro inicial por año de publicación.
  Decisiones acordadas en [D024](decisions/D024-retrieval-baseline-and-embeddings.md).
  #39 implementada: frontera MedCPT sustituible,
  indexación idempotente/reindexación, persistencia pgvector y retrieval exacto
  con filtro por año. Revisión de modelos/configuración y exclusión de contenido
  obsoleto; demo manual disponible. #40 completada: corpus fijo de 50
  publicaciones y 10 queries con juicios binarios previos, runner end-to-end
  aislado y baseline real de MedCPT ejecutado. El desarrollador acepta el cierre con corpus, juicios y resultados
  asistidos; esto no acredita revisión experta de las etiquetas.
  [Informe y límites](../evaluation/retrieval/REPORT-v1.md),
  [procedimiento](../evaluation/retrieval/README.md).
  [Operación y contratos](../README.md#embeddings-y-retrieval-local-m7--39).
- **M6 — Biomedical Data Ingestion** implementado: PubMed/NCBI E-utilities,
  parsing y contrato normalizado, persistencia con upsert atómico y CLI
  `evidenceops ingest` sobre un servicio reutilizable. El pipeline coordina lotes,
  transacciones por documento, fallos parciales y resumen de resultados.
  [Plan M6 completado](plans/completed/m6-biomedical-data-ingestion.md).
  Decisiones en [D021](decisions/D021-biomedical-ingestion-source-and-contract.md),
  [D022](decisions/D022-biomedical-publication-persistence.md) y
  [D023](decisions/D023-biomedical-ingestion-pipeline.md).
  Pipeline validado con tests deterministas; adquisición real de PubMed usada
  para el corpus de #40, sin demo del CLI de ingestión.
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

- No existe todavía un baseline real completo y revisado de **generación M4**:
  la cuota impidió completar el run. Obtenerlo es una operación futura, no desarrollo pendiente
  de M4 ni prueba de calidad del modelo. No cambiar proveedor, pagar cuota o
  añadir retries artificiales para conseguirlo.
- Servicio RAG local disponible con fuentes y citas verificadas estructuralmente;
  el endpoint RAG reutiliza retrieval y la generación HTTP previa conserva su
  contrato. La revisión humana aplica una rúbrica limitada; no hay validación factual automática.
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

La evaluación RAG (#47) requiere su propio encargo. La corrida real de retrieval no resuelve
el baseline de generación M4 pendiente.
Cuando exista cuota y se solicite, obtener/promover/revisar el baseline real.
Los comandos y requisitos de pruebas viven en el [README](../README.md);
la secuencia futura, en el roadmap.
