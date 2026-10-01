# Observabilidad: diagnosticar una generación

Orden de entrega en el [plan M5 completado](../plans/completed/m5-observability.md).

La API configura `logging` de Python para emitir eventos de EvidenceOps como
una línea JSON por evento a stdout. No modifica los handlers del servidor ni
los de librerías externas.

Cada petición HTTP recibe un UUID nuevo, incluso si el cliente envía
`X-Request-ID`. Se devuelve en esa cabecera tanto en éxito como en errores,
incluidos 404, 422 y 500. Un `ContextVar` lo propaga hasta los handlers síncronos
sin ampliar `Generator` ni los contratos de datos. El middleware restaura el
contexto en `finally`, también si la petición falla. Envuelve la capa de errores
de FastAPI para añadir la cabecera a los 500 sin cambiar su respuesta.

| Evento | Nivel | Campos específicos |
| --- | --- | --- |
| `generation.started` | INFO | — |
| `llm.generation.started` | INFO | `provider`, `model` |
| `generation.succeeded` | INFO | `duration_ms`, `outcome: success` |
| `generation.failed` | WARNING | `duration_ms`, `outcome: error`, `cause` segura |
| `generation.failed` ante error inesperado de aplicación | ERROR | `duration_ms`, `outcome: error`, `cause: unexpected_application_error` |

Todos incluyen `timestamp` UTC, `level`, `event` y `request_id`. El timestamp
sirve para situar el evento; la duración usa `perf_counter()` y milisegundos.
Mide la llamada al generador, incluida su validación de salida y posibles
esperas/retries del SDK, excluyendo la consulta previa a PostgreSQL y la
serialización HTTP. No es la duración completa de la petición.

## Métricas agregadas

`GET /metrics` devuelve formato Prometheus mediante `prometheus-client`. El
registro es propio de cada instancia de API. Los logs permiten seguir una
operación con `request_id`; las métricas suman observaciones entre operaciones.

| Métrica | Tipo | Labels |
| --- | --- | --- |
| `evidenceops_generations_total` | Counter | `outcome=success|error` |
| `evidenceops_generation_errors_total` | Counter | `cause` estable de `GenerationErrorCause` o `unexpected_application_error` |
| `evidenceops_generation_duration_seconds` | Histogram | `outcome=success|error` |
| `evidenceops_llm_input_tokens_total` | Counter | `provider`, `model` |
| `evidenceops_llm_output_tokens_total` | Counter | `provider`, `model` |
| `evidenceops_llm_total_tokens_total` | Counter | `provider`, `model` |

El histograma cubre el mismo tramo que `duration_ms`; sus buckets llegan a
120 segundos y conservan la cola superior. Permite derivar percentiles
aproximados a partir de buckets agregados. Un Gauge representaría un valor
instantáneo, por ejemplo trabajo en curso; aquí interesan acumulados y
distribuciones, por eso se usan Counter e Histogram.

`provider` y `model` tienen cardinalidad acotada en la configuración actual.
`request_id`, `question_id`, textos, respuestas y errores crudos no son labels:
crearían series numerosas o expondrían contenido. Gemini aporta `usage` de la
interacción; DeepSeek, `usage` de la respuesta JSON. Se registran los tres
contadores de tokens solo cuando existen input, output y total reales. No se
deducen campos ausentes ni se llama a `count_tokens`. Tokens observados no son
coste facturado: el pricing y tier externos no se conocen de forma fiable.

Se seleccionan explícitamente los campos operativos. No se registran preguntas,
respuestas, limitations, claves, cuerpos del proveedor ni excepciones/tracebacks.
Los mensajes de eventos son constantes. `GenerationError` utiliza sus causas
existentes; su mensaje y su cadena interna no se serializan. Un error inesperado
se vuelve a lanzar para mantener la política HTTP existente.

## Traces de una generación

Un **trace** es el recorrido de una ejecución concreta; un **span** representa
una operación de ese recorrido. La relación **padre/hijo** muestra qué operación
contiene a otra. Aquí, OpenTelemetry crea tres spans:

```text
POST /questions/{question_id}/generate (SERVER)
└── generation
    └── llm.gemini  (o llm.deepseek)
```

El span HTTP cubre la petición; `generation` cubre la llamada a `Generator` y
la respuesta de la ruta; el del proveedor cubre su llamada y validación. Cada
span lleva duración de OpenTelemetry y `evidenceops.outcome=success|error`.
El del proveedor añade `evidenceops.provider` y `evidenceops.model`; ante fallo,
este y sus padres quedan en estado ERROR. `record_exception` recibe una
excepción sintética con una causa estable, pues mensajes y cadenas originales
del SDK podrían incluir contenido sensible. Ni prompts, respuestas, UUID de
pregunta ni mensajes originales entran en spans. La ruta usa una plantilla sin
UUID. No se instrumentan intentos internos o funciones adicionales.

Los logs cuentan **qué ocurrió**, las métricas **cuánto ocurre** entre muchas
ejecuciones y los traces **dónde ocurrió** en una ejecución. Los eventos JSON
emitidos dentro de spans añaden `trace_id` y `span_id`; `request_id` permanece.
Los logs fuera de spans mantienen su formato anterior.

La exportación está desactivada por defecto. Para demostrar #23 con la API y
PostgreSQL preparados, iniciar en una terminal (con la clave del proveedor en
`.env`):

```bash
EVIDENCEOPS_TRACE_CONSOLE=true uv run --locked uvicorn evidenceops.main:app --no-access-log \
  > /tmp/evidenceops-events.jsonl 2> /tmp/evidenceops-traces.jsonl
```

En otra terminal, sustituir el UUID por una pregunta ya registrada:

```bash
curl -sS -D - -o /dev/null -X POST \
  http://127.0.0.1:8000/questions/UUID_DE_LA_PREGUNTA/generate
rg 'llm.gemini|llm.deepseek|generation|trace_id|duration|evidenceops.outcome' \
  /tmp/evidenceops-traces.jsonl
```

El exportador de consola escribe un objeto por span en stderr. Los tres objetos
comparten `trace_id`; `parent_id` enlaza proveedor → generación → HTTP. El span
`llm.gemini` o `llm.deepseek` muestra modelo, `start_time`, `end_time` (su
diferencia es la duración) y outcome. Si falla, muestra causa y excepción
segura. Copiar `trace_id` a los logs y comparar
con `generation.succeeded` o `generation.failed`; consultar `GET /metrics` para
los agregados. La petición manual llama al proveedor y puede consumir cuota.
El formato exacto del exportador de consola no es estable.

## Comprobación manual corta

Con PostgreSQL y la configuración local preparados, iniciar en una terminal:

```bash
uv run uvicorn evidenceops.main:app --no-access-log | tee /tmp/evidenceops-events.jsonl
```

En otra terminal, usar una pregunta ya registrada (sustituir el UUID):

```bash
curl -sS -D - -o /dev/null -X POST \
  http://127.0.0.1:8000/questions/UUID_DE_LA_PREGUNTA/generate
```

Esta operación manual sí llama al proveedor configurado y puede consumir cuota. Copiar el valor de `X-Request-ID`:

```bash
rg 'ID_COPIADO' /tmp/evidenceops-events.jsonl
```

Deben aparecer inicio, proveedor/modelo y resultado con el mismo identificador.
`generation.succeeded` confirma éxito; `generation.failed` muestra la causa
segura y `duration_ms` permite identificar una operación lenta. Si falla por
cuota, se conserva `rate_limit` sin exponer el mensaje del proveedor. Un UUID
inválido o una pregunta ausente no inicia generación, aunque recibe cabecera.

La comprobación automatizada equivalente utiliza fakes y transporte simulado:

```bash
uv run --locked pytest tests/test_observability.py tests/test_gemini_adapter.py tests/test_deepseek_adapter.py -q
```

Los dos tests del adaptador que recorren HTTP y persistencia necesitan PostgreSQL;
ninguno realiza inferencias reales.

## Límites

- Se observa la operación de generación, no cada intento interno del proveedor.
  No se cambia su política ni se usan APIs privadas para instrumentar retries.
- Fuera de HTTP, `request_id` es null si se configura este formatter. Esta issue
  configura la salida en el arranque de la API; no instrumenta el runner offline.
- Los logs propios son JSON; los logs de Uvicorn y librerías mantienen su
  configuración. La lista de campos no sanea mensajes arbitrarios: al añadir
  eventos deben mantenerse nombres constantes y metadata segura. No activar
  debug del SDK con datos sensibles. Los errores inesperados siguen pudiendo
  producir diagnósticos del servidor; los errores del SDK se traducen a las
  causas seguras existentes antes de llegar a esa capa.
- Gemini usa el retry configurado en su SDK para 408/5xx; DeepSeek hace una sola
  petición, sin retry propio. Ambos tienen timeout de transporte, sin deadline
  total. DeepSeek usa JSON mode y Pydantic valida el esquema; Gemini envía
  además JSON Schema al proveedor.
- No hay cálculo de coste monetario ni plataforma de observabilidad desplegada.
