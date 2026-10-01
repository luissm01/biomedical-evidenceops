# Decisiones de ingeniería

Lee solo la decisión pertinente. Los IDs anteriores se conservan para referencias
en Git/issues. El estado de entrega vive en GitHub y el trabajo local en los planes.

| ID | Tema | Estado |
| --- | --- | --- |
| [D001](D001-uv.md) | Use uv for Python project management | Aceptada |
| [D002](D002-src-layout.md) | Use a src/ project layout | Aceptada |
| [D003](D003-dependency-groups.md) | Separate runtime and development dependencies | Aceptada |
| [D004](D004-incremental-api.md) | Start with the smallest useful API | Aplicada en M0 |
| [D005](D005-in-memory.md) | Registro temporal de preguntas en memoria | Sustituida por D007/D008 |
| [D006](D006-github-workflow.md) | Seguimiento de trabajo y revisión en GitHub | Aceptada |
| [D007](D007-postgresql.md) | PostgreSQL local para la primera persistencia duradera | Aceptada |
| [D008](D008-persistence.md) | SQLAlchemy ORM síncrono, Psycopg y Alembic | Aceptada |
| [D009](D009-startup.md) | Fallar al arrancar si PostgreSQL no está disponible | Aceptada |
| [D010](D010-ephemeral-generation.md) | Generación efímera vinculada a preguntas en M3 | Aceptada |
| [D011](D011-gemini.md) | Gemini como único proveedor de M3 | Aceptada |
| [D012](D012-generator-boundary.md) | Frontera LLM con un Protocol de una operación | Aceptada |
| [D013](D013-evaluation-dataset.md) | Dataset inicial de contenido para M4 (#15) | Aceptada |
| [D014](D014-evaluation-runner.md) | Runner offline sobre Generator y baseline de outputs (#16) | Aceptada |
| [D015](D015-human-review.md) | Revisión humana estructurada y regresiones por dimensión (#17) | Aceptada |
| [D016](D016-structured-logging.md) | Logging estructurado y correlación HTTP mínima (#21) | Aceptada |
| [D017](D017-context-architecture.md) | Arquitectura documental y carga progresiva | Aceptada por el encargo de refactor |
| [D018](D018-multiple-llm-providers.md) | Gemini y DeepSeek tras Generator | Aceptada |
| [D019](D019-prometheus-metrics.md) | Métricas Prometheus de generación y tokens observados (#22) | Aceptada |
| [D020](D020-opentelemetry-tracing.md) | Spans OpenTelemetry mínimos para generaciones (#23) | Aceptada localmente |
| [D021](D021-biomedical-ingestion-source-and-contract.md) | Fuente PubMed y contrato de ingestión biomédica (#28) | Accepted |
| [D022](D022-biomedical-publication-persistence.md) | Persistencia atómica de publicaciones biomédicas (#30) | Aceptada |

| [D023](D023-biomedical-ingestion-pipeline.md) | Pipeline local, fallos parciales y semántica del resumen (#31) | Aceptada |

Nueva decisión: siguiente ID, problema, alternativas, decisión, consecuencias
y estado. Cambios de dirección enlazan a la decisión sustituida; no reescribas
el razonamiento histórico como si siempre hubiera sido el actual.
