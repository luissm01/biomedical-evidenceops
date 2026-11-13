# D036 — Cola de jobs propia sobre PostgreSQL para la ingesta (M11.1)

## Estado

Decisiones de alcance cerradas por el desarrollador en el encargo de M11.1 (#65).
Implementación con tests deterministas; sin inferencias LLM.

## Problema

`evidenceops ingest` ejecuta la ingesta PubMed en primer plano: quien la lanza
espera a NCBI (límite de 3 peticiones/s sin clave), y un fallo transitorio de red
o un 429/5xx termina la ejecución sin reintento. Se necesita aceptar peticiones de
ingesta por HTTP, procesarlas fuera de la petición, reintentar lo transitorio y
sobrevivir a la caída de un worker, entendiendo los mecanismos de base.

## Alternativas

| Opción | A favor | En contra |
| --- | --- | --- |
| **Tabla de jobs en PostgreSQL + `FOR UPDATE SKIP LOCKED`** | Sin servicio nuevo; encolar es transaccional con los datos; estado consultable con SQL; mecanismos visibles (claim, lease, fencing) | Polling; cada worker ocupa conexiones; el throughput depende de la BD principal; reintentos, backoff y recuperación se programan a mano |
| Redis + RQ/arq | Latencia baja, push en lugar de polling; arq es async | Otro servicio que operar y asegurar; la durabilidad depende de la configuración de persistencia de Redis; el estado del job vive fuera de PostgreSQL; la librería oculta los mecanismos que M11 quiere enseñar |
| Celery (con Redis/RabbitMQ) | Ecosistema maduro: reintentos, rutas, scheduling, monitorización | Broker + backend de resultados; mucha configuración (acks tardíos, prefetch, visibility timeout) para un único flujo; capa de abstracción mayor que el problema |

## Decisión

- Tabla `ingestion_jobs`; un job es una petición `query + limit` que reutiliza
  `ingest_pubmed` y su upsert idempotente por `(source, source_id)`.
- Reclamación con un único `UPDATE … FROM (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`
  en una transacción corta. La transacción no se mantiene durante el trabajo:
  el lease (`lease_expires_at`) sustituye al bloqueo de fila mientras se ejecuta.
- Estados `queued → running → succeeded | failed`, con `running → queued` para
  reintentos. `attempts` se incrementa en cada reclamación y actúa como token de
  fencing: las transiciones finales exigen `status = 'running' AND attempts = :attempt`.
- Reintentos solo para errores transitorios de PubMed (timeout, transporte, 429,
  5xx), hasta `max_attempts` (3 por defecto, copiado al job al encolar), con
  backoff exponencial `base · 2^(n-1)` limitado por un máximo y sin jitter.
  4xx, XML inválido y errores inesperados de aplicación fallan directamente.
- Lease fijo (300 s por defecto) sin heartbeat. Un lease caducado se reclama
  como un intento más; si ya no quedan intentos, el job pasa a `failed` con
  `lease_expired`. Semántica at-least-once.
- Clave de idempotencia opcional (`Idempotency-Key`) con restricción única;
  `ON CONFLICT DO NOTHING` + lectura del job existente. Misma clave con otros
  parámetros → 409.
- Worker síncrono, un job a la vez por proceso, polling configurable; se escala
  lanzando más procesos. Todas las marcas de tiempo usan `now()` de PostgreSQL.

## Consecuencias y trade-offs

- Encolar y consultar estado no requieren infraestructura nueva; un job es una
  fila y su historia mínima (intentos, último error, resultado) se lee con SQL.
- Polling: latencia de arranque hasta `poll_seconds` y una consulta por intervalo
  y worker. LISTEN/NOTIFY queda fuera de alcance.
- Sin heartbeat, un job más largo que el lease puede ejecutarse dos veces en
  paralelo. El fencing evita que el resultado viejo sobrescriba al nuevo y el
  upsert evita duplicados, pero se repite trabajo y peticiones a NCBI. El lease
  debe superar holgadamente la duración esperada (≤100 publicaciones, pocos
  segundos).
- Un job reintentable repite la ingesta completa: es seguro por el upsert, pero
  no reanuda donde quedó. Para lotes grandes convendría dividir en jobs menores.
- Varios workers comparten la IP ante NCBI; el limitador de cada cliente no los
  coordina entre procesos. Con pocos workers y backoff ante 429 es aceptable.
- Sin jitter, varios jobs que fallan a la vez reintentan a la vez. Con un único
  flujo y pocos workers no compensa la complejidad de probarlo.

## Cuándo migrar a un broker

Cuando el volumen o la latencia lo midan como necesario: miles de jobs por
minuto o latencias de arranque sub-segundo, la tabla de jobs compitiendo con la
carga transaccional principal (bloat por actualizaciones, vacuum, conexiones),
muchos tipos de tarea con rutas, prioridades, scheduling o workflows encadenados,
o consumidores en otros lenguajes/servicios. Entonces Redis+arq (si el trabajo
es I/O async) o un broker con acks (RabbitMQ/Celery) se justifican mejor que
seguir ampliando la tabla.

## Fuera de alcance

Health/readiness, autenticación, rate limiting, secretos (M11.2), LISTEN/NOTIFY,
prioridades, scheduling periódico, varias colas, cancelación y aplicar la cola
a RAG u otros flujos. Operación y conceptos: [subsistema jobs](../subsystems/jobs.md).
