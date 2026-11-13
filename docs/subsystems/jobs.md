# Ingesta asíncrona: cola de jobs y worker (M11.1)

Decisión y alternativas en [D036](../decisions/D036-postgresql-job-queue.md).
Código: [jobs.py](../../src/evidenceops/jobs.py) (SQL de la cola),
[worker.py](../../src/evidenceops/worker.py) (bucle y clasificación de errores),
endpoints en [main.py](../../src/evidenceops/main.py).

## Flujo

`POST /ingestion-jobs → fila queued → worker reclama (SKIP LOCKED) → running con lease
→ ingest_pubmed → succeeded | queued (reintento con backoff) | failed`

La API nunca llama a PubMed: inserta la fila y responde 202. El worker es otro
proceso (`evidenceops worker`). El CLI `evidenceops ingest` sigue siendo síncrono.

## Tabla `ingestion_jobs`

| Columna | Papel |
| --- | --- |
| `status` | `queued`, `running`, `succeeded`, `failed` (CHECK) |
| `query`, `search_limit` | Parámetros de la petición (1–100) |
| `idempotency_key` | Opcional, UNIQUE; repite el job existente |
| `attempts`, `max_attempts` | Intentos consumidos/máximo; `attempts` es el token de fencing |
| `run_after` | Cuándo puede reclamarse (encolado o fin del backoff) |
| `lease_expires_at`, `worker_id` | Propiedad temporal del job en `running`; CHECK: lease presente ⇔ `running` |
| `last_error` | Código estable sin contenido (`search_http_error_503`, `lease_expired`…) |
| `result` | Resumen de la ingesta (contadores y PMIDs fallidos) |
| `created_at`, `updated_at`, `started_at`, `finished_at` | Siempre `now()` de PostgreSQL |

Índices parciales sobre `run_after` (queued) y `lease_expires_at` (running):
la reclamación solo recorre filas reclamables.

## Ciclo de vida

```
            claim (attempts+1, lease)              éxito
 queued ───────────────────────────────▶ running ─────────▶ succeeded
   ▲  ▲                                   │  │  │
   │  └── error transitorio y quedan ─────┘  │  └─ error permanente o sin intentos ─▶ failed
   │      intentos (run_after = backoff)     │
   └── lease caducado: otro worker lo ───────┘     lease caducado sin intentos ─────▶ failed
       reclama directamente (attempts+1)
```

- **Reintentables:** timeout, transporte, 429 y 5xx de NCBI. **Permanentes:**
  4xx, XML inválido, error inesperado de aplicación. Registros inválidos o un
  fallo de persistencia de un documento no son errores del job: aparecen en
  `result.failed`/`result.failures`, como en el CLI.
- **Backoff:** `min(base · 2^(n-1), max)` tras el intento `n` (10 s, 20 s, 40 s…).
- **Parada ordenada:** la primera SIGINT/SIGTERM termina el job en curso y sale.
  Una segunda interrumpe el job y lo libera (`queued`, `released_on_shutdown`)
  sin esperar al lease. Un `kill -9` deja el job en `running` hasta que caduque.

## Conceptos

**At-least-once frente a exactly-once.** El worker escribe publicaciones y
después marca el job como terminado; son dos efectos que no pueden ser atómicos
juntos con un sistema externo de por medio (PubMed, un proceso que puede morir).
Si muere entre ambos, el job se ejecuta otra vez: cada job se procesa *al menos*
una vez. Exactly-once de extremo a extremo no lo da ninguna cola; se consigue
*efecto* exactly-once haciendo idempotente el trabajo. Aquí lo es: el upsert por
`(source, source_id)` convierte una segunda ejecución en `updated`, no en
duplicados. La clave de idempotencia resuelve el mismo problema en la entrada:
un cliente que reintenta el POST no crea dos jobs.

**El lease.** El bloqueo de fila (`FOR UPDATE`) solo dura la transacción de
reclamación; mantenerlo durante toda la ingesta ocuparía una conexión y
liberaría el job en cuanto la conexión cayera, también por un corte breve. El
lease es un bloqueo con caducidad escrito en la fila: «este job es de W hasta T».
Si W muere, nadie lo renueva y, tras T, otro worker puede reclamarlo. El precio:
si W solo era lento, dos workers pueden trabajar a la vez. Por eso las
transiciones finales llevan fencing (`attempts = :attempt`): la escritura del
worker antiguo afecta a 0 filas y se registra `job.lease_lost`. El lease debe
superar la duración esperada del job; no hay heartbeat.

**Worker síncrono frente a async/await.** `async/await` permite que un solo
hilo intercale muchas operaciones que *esperan* E/S (sockets, BD): mientras una
espera, avanza otra. Ayuda cuando hay mucha concurrencia de E/S, como una API
con muchas peticiones simultáneas. No acelera trabajo de CPU/GPU (parsing,
embeddings, inferencia local): una corrutina que calcula bloquea el bucle de
eventos. Este worker procesa un job cada vez, su E/S está limitada por el rate
limit de NCBI y la evolución natural de la cola (indexar con MedCPT) es trabajo
de CPU/GPU; el paralelismo se obtiene con más procesos, no con un bucle de
eventos. Además reutiliza el pipeline y los clientes síncronos sin reescribirlos.

## Operación

Con `.env`, PostgreSQL y `uv run --locked alembic upgrade head`:

```bash
uv run uvicorn evidenceops.main:app --reload            # API
uv run --locked evidenceops worker --metrics-port 9101  # worker (otra terminal)
curl -si -X POST localhost:8000/ingestion-jobs -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-1' -d '{"query": "asthma[Title]", "limit": 10}'
curl -s localhost:8000/ingestion-jobs/<job_id>
```

El worker **sí consulta PubMed**. Configuración `EVIDENCEOPS_JOBS_*` en
[.env.example](../../.env.example): `MAX_ATTEMPTS`, `BACKOFF_BASE_SECONDS`,
`BACKOFF_MAX_SECONDS`, `LEASE_SECONDS`, `POLL_SECONDS`. Para probar la recuperación
en local, un lease corto (p. ej. 20 s) hace visible la reclamación tras `kill -9`.

## Observabilidad

Eventos y métricas en [observabilidad](observability.md#ingesta-asíncrona-m111).

## Pruebas

[test_jobs.py](../../tests/test_jobs.py): transiciones, backoff, permanente frente
a reintentable, SKIP LOCKED y workers concurrentes, lease caducado y fencing,
liberación en parada, idempotencia (también concurrente), pipeline real con
PubMed simulado y API. Sin red ni inferencias.
