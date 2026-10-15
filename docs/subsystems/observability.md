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

## Ingestión biomédica por CLI

`evidenceops ingest` configura el mismo logger JSON. `ingestion.started` incluye
`source` y `run_id`; `ingestion.finished` conserva ambos y añade `duration_ms`,
`outcome`, `requested`, `unique`, `batches`, `created`, `updated`, `omitted`,
`failed` y `unidentified_invalid`. La duración cubre toda la ejecución del
servicio, incluida búsqueda y commits. El `run_id` correlaciona inicio/fin;
`request_id` es null fuera de HTTP. El resumen final añade causas seguras y
PMIDs conocidos; los eventos no incluyen títulos, abstracts, query, credenciales
ni mensajes de excepciones. Errores inesperados de programación se propagan con
evento final `outcome: error` y causa segura. No se añaden métricas ni spans de
ingestión. Operación y semántica en el
[README](../../README.md#ingestión-pubmed-m6).

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
- Fuera de HTTP, `request_id` es null si se configura este formatter. La API y la CLI de ingestión
  configuran la salida; el runner offline no está instrumentado.
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

## RAG end-to-end (M8 / #46)

`POST /rag` reutiliza la correlación HTTP y la exportación de M5. El servicio
emite `rag.started` y `rag.finished` para cada `stage`:
`operation`, `retrieval`, `context`, `generation`. Cada final añade `duration_ms`,
`outcome=success|abstention|error` y `cause` segura (null cuando no hay fallo).
Los eventos incluyen `request_id`, `trace_id` y `span_id`; no contienen query,
filtro, documentos, PMIDs, UUID de publicación, fuentes, respuesta ni excepciones
originales. Las duraciones usan `perf_counter`, sin depender del reloj de pared.

La operación cubre todo el servicio después de validar la entrada: retrieval
(incluida codificación de query y posible carga inicial de MedCPT), construcción
de contexto/mensaje y generación con validación determinista de citas. Excluye
validación/serialización y transporte HTTP, que cubre el span del servidor.
La etapa de generación incluye el adapter y validación posterior de citas.
La abstención local registra operación `abstention`, retrieval/context `success`
y ninguna generación. La abstención del modelo registra operación y generación
`abstention`. Ambas son resultados normales con estado de span OK.

| Métrica | Tipo | Labels |
| --- | --- | --- |
| `evidenceops_rag_operations_total` | Counter | `stage`, `outcome` |
| `evidenceops_rag_duration_seconds` | Histogram | `stage`, `outcome` |
| `evidenceops_rag_errors_total` | Counter | `stage`, `cause` |

`stage` y `outcome` tienen únicamente los valores anteriores. `cause` procede de
`GenerationErrorCause`, o es `database_unavailable`, `retrieval_incompatible`,
`retrieval_unavailable`, `invalid_citations`, `unexpected_application_error`.
No se usan textos ni identificadores como labels. El registry es el mismo de
cada aplicación M5 y `/metrics` expone ambas familias. Para contar operaciones o
calcular su latencia, seleccionar `stage="operation"`; los otros valores observan
etapas y no deben sumarse a la operación. Los histogramas usan los buckets de M5.
Un fallo cuenta en la etapa fallida y en la operación que lo contiene.

No se incrementa `evidenceops_generations_total` con RAG: ese contador sigue
midiendo el endpoint M3. Los tokens observados se añaden una sola vez desde
Gemini/DeepSeek a los contadores existentes, incluidos los de respuestas que
posteriormente fallen validación de citas. Sin generación no hay consumo LLM.

```text
POST /rag (SERVER)
└── rag
    ├── rag.retrieval
    ├── rag.context
    └── rag.generation
        └── llm.gemini (o llm.deepseek)
```

Los spans de etapas son secuenciales. Se marcan ERROR la etapa que falla, `rag`
y HTTP; los spans anteriores completados conservan OK. Un fallo de citas deja
el span del adapter OK si completó correctamente su salida estructurada, y
`rag.generation` ERROR con `invalid_citations`. `GenerationError` conserva su
causa `INVALID_OUTPUT` como exige D026. Los eventos de excepción usan la misma
excepción sintética segura de M5. El span HTTP clasifica errores como `http_error`;
la causa precisa está en el servicio/etapa. Un 422 solo genera el span HTTP.

El [README](../../README.md#rag-desde-la-api-m8--46) contiene los requisitos,
curl y procedimiento de demostración con el pipeline real. Las pruebas nuevas
validan logs JSON, métricas, jerarquía, errores y privacidad sin modelos ni red:

```bash
uv run --locked pytest tests/test_rag.py tests/test_rag_api.py tests/test_rag_integration.py -q
```

El último archivo requiere PostgreSQL con pgvector de pruebas. Usa búsqueda M7
real y encoder/LLM deterministas. No mide calidad IA ni adelanta la evaluación #47.

### Diagnosticar `502 invalid_citations` sin registrar contenido

Un span `llm.deepseek` OK confirma transporte y salida estructurada válidos para
el adapter; las reglas de citas se ejecutan después, dentro de `rag.generation`.
Por tanto, un adapter OK y RAG ERROR son compatibles. Los logs antiguos con solo
`cause=invalid_citations` no permiten reconstruir qué regla falló ni la salida
rechazada. Los logs del incidente aportado por el desarrollador confirman esa
secuencia, pero no identifican una regla concreta. No se repite automáticamente
la petición para investigarlo.

Los eventos `rag.finished` fallidos de generación y operación incorporan ahora
el mismo diagnóstico seguro; los spans `rag.generation` y `rag` lo incorporan
con el prefijo `evidenceops.`. No cambia el cuerpo ni código HTTP del error.

| `validation_reason` | Regla que falló |
| --- | --- |
| `unknown_citation` | Etiqueta con formato `[S1]` que no pertenece a las fuentes incluidas |
| `malformed_citation` | Quedan corchetes fuera de etiquetas válidas, incluidos `[S0]`, `[S01]`, `[S1,S2]` o corchetes de otro uso |
| `block_missing_citation` | Párrafo/elemento no vacío sin ninguna cita válida |
| `block_not_cited_at_end` | Bloque con cita válida, pero sin el sufijo de cita/puntuación admitido |
| `invalid_abstention` | Answer exactamente igual a la abstención fija con limitations no vacío |

`validation_field` es `answer` o `limitations`. `limitation_index`, si procede,
identifica el elemento de limitations. `block_index` identifica el bloque del
campo o elemento; `character_offset` es su posición dentro de ese texto, en
caracteres Unicode, no bytes. Todos los índices empiezan en cero. Las posiciones
se refieren al `GeneratedContent` ya validado por Pydantic (espacios exteriores
eliminados, JSON decodificado), no a offsets del JSON de transporte.

Para una cita desconocida o corchete mal formado, el offset apunta al inicio de
la cita o al primer corchete que sobra. Para cobertura apunta al primer carácter
no blanco del bloque que falla. `invalid_abstention` señala `limitations[0]` sin
inventar bloque/offset: falla la condición de lista vacía, no su prosa.

Se informa solo del primer fallo según la precedencia conservada: abstención
exacta; después, en answer y cada limitations por orden, referencias desconocidas,
corchetes mal formados y cobertura. Puede haber otros fallos posteriores. Una
abstención redactada libremente se valida como cualquier otro texto: sin cita
produce `block_missing_citation`. No se intenta inferir semánticamente si el
modelo pretendía abstenerse.

Ejemplo de fragmento de un evento, sin contenido generado:

```json
{"event":"rag.finished","stage":"generation","cause":"invalid_citations","validation_reason":"block_missing_citation","validation_field":"limitations","limitation_index":0,"block_index":0,"character_offset":0}
```

No se registran fragmentos, etiquetas desconocidas, prompts, queries, fuentes,
abstracts ni respuestas, tampoco a nivel DEBUG. No se ha añadido un modo de
volcado de contenido. Los diagnósticos no son labels Prometheus; las métricas
conservan su esquema y causa `invalid_citations`.

Para reproducir las cinco categorías con DeepSeek simulado, sin red, claves ni
base de datos:

```bash
uv run --locked pytest tests/test_rag_api.py -k deepseek_success_then_citation_failure -q
```

Para diagnosticar una nueva llamada real, reiniciar la API con el código actual
(y PostgreSQL/corpus indexado/proveedor configurado como en el README):

```bash
EVIDENCEOPS_TRACE_CONSOLE=true uv run --locked --extra medcpt uvicorn evidenceops.main:app --no-access-log \
  > /tmp/evidenceops-rag-events.jsonl 2> /tmp/evidenceops-rag-traces.jsonl
```

En otra terminal, realizar explícitamente una sola petición; este ejemplo descarta
el cuerpo para dejar únicamente status/cabeceras en la terminal y puede consumir
cuota real:

```bash
curl -sS -D - -o /dev/null -X POST http://127.0.0.1:8000/rag \
  -H 'Content-Type: application/json' \
  -d '{"query":"association between childhood obesity and asthma risk","published_from":2020}'
```

Copiar el nuevo `X-Request-ID` y filtrar únicamente esa petición:

```bash
rg -F 'ID_COPIADO' /tmp/evidenceops-rag-events.jsonl
```

Si vuelve a fallar, leer `validation_reason` y localización en el evento de
`stage=generation`; `stage=operation` repite el mismo diagnóstico. Con el
`trace_id` se localizan los spans y se comprueba el adapter OK/generación ERROR.
La salida del modelo puede variar entre llamadas: no se promete reproducir el
fallo histórico. Si ya se dispone localmente del objeto de salida rechazado,
puede validarse offline con `validate_citations` y las fuentes exactas incluidas,
sin repetir la inferencia; `InvalidCitationsError.diagnostic()` devuelve solo
metadata segura.

#### Restricciones actuales que requieren decisión antes de flexibilizar

Los tests caracterizan estos casos sin cambiar las reglas de D026 ni las
instrucciones al modelo:

- `**Texto [S1].**`, una comilla de cierre tras la cita o puntuación como `。`
  fallan `block_not_cited_at_end`. El sufijo implementado admite solo
  `. ! ? ; : …`; la referencia de D026 a puntuación final es más general.
  Una futura normalización de envoltorios Markdown o ampliación de puntuación
  debe acordarse antes de modificar la aceptación.
- Un encabezado separado por línea en blanco falla `block_missing_citation`,
  aunque sea solo organizativo. El validador no distingue encabezados de
  párrafos con afirmaciones; eximirlos requiere acordar ese criterio.
- Un intervalo entre corchetes, como `Intervalo [0.1, 0.2] [S1].`, falla
  `malformed_citation`. Es la restricción explícita de las instrucciones actuales
  de no usar otros corchetes; distinguirlos de citas cambiaría la política.
- Una limitación operativa escrita por el modelo sin cita también se rechaza;
  D026 reserva esas limitaciones sin citas a la aplicación.

Un rechazo estructural no prueba falta de apoyo científico, igual que una cita
aceptada no demuestra apoyo semántico. La segmentación de bloques sigue siendo
la existente: párrafos separados por línea en blanco y listas con `-`, `+`, `*`
o numeración `1.`/`1)`. Un salto de línea simple puede ser continuación de párrafo.
