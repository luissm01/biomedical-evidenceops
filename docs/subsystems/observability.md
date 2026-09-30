# Observabilidad: diagnosticar una generación

Estado de entrega en el [plan M5](../plans/active/m5-observability.md).
Este runbook corresponde al código local pendiente de #21. La PR documental
conserva estas instrucciones, pero no incorpora esa implementación ni sus tests;
sus eventos y cabeceras no están disponibles en un checkout de esa PR.

La API configura `logging` de Python para emitir eventos de EvidenceOps como
una línea JSON por evento a stdout. No modifica los handlers del servidor ni
los de librerías externas. No requiere dependencias nuevas.

Cada petición HTTP recibe un UUID nuevo, incluso si el cliente envía
`X-Request-ID`. Se devuelve en esa cabecera tanto en éxito como en errores,
incluidos 404, 422 y 500. Un `ContextVar` lo propaga hasta los handlers síncronos
sin ampliar `Generator` ni los contratos de datos. El middleware restaura el
contexto en `finally`, también si la petición falla. Envuelve la capa de errores
de FastAPI para añadir la cabecera a los 500 sin cambiar su respuesta.

| Evento | Nivel | Campos específicos |
| --- | --- | --- |
| `generation.started` | INFO | — |
| `gemini.generation.started` | INFO | `model` |
| `generation.succeeded` | INFO | `duration_ms`, `outcome: success` |
| `generation.failed` | WARNING | `duration_ms`, `outcome: error`, `cause` segura |
| `generation.failed` ante error inesperado de aplicación | ERROR | `duration_ms`, `outcome: error`, `cause: unexpected_application_error` |

Todos incluyen `timestamp` UTC, `level`, `event` y `request_id`. El timestamp
sirve para situar el evento; la duración usa `perf_counter()` y milisegundos.
Mide la llamada al generador, incluida su validación de salida y posibles
esperas/retries del SDK, excluyendo la consulta previa a PostgreSQL y la
serialización HTTP. No es la duración completa de la petición.

Se seleccionan explícitamente los campos operativos. No se registran preguntas,
respuestas, limitations, claves, cuerpos del proveedor ni excepciones/tracebacks.
Los mensajes de eventos son constantes. `GenerationError` utiliza sus causas
existentes; su mensaje y su cadena interna no se serializan. Un error inesperado
se vuelve a lanzar para mantener la política HTTP existente.

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

Esta operación manual sí llama a Gemini y puede consumir cuota. Copiar el valor de `X-Request-ID`:

```bash
rg 'ID_COPIADO' /tmp/evidenceops-events.jsonl
```

Deben aparecer inicio, modelo Gemini y resultado con el mismo identificador.
`generation.succeeded` confirma éxito; `generation.failed` muestra la causa
segura y `duration_ms` permite identificar una operación lenta. Si falla por
cuota, se conserva `rate_limit` sin exponer el mensaje del proveedor. Un UUID
inválido o una pregunta ausente no inicia generación, aunque recibe cabecera.

La comprobación automatizada equivalente utiliza fakes y transporte simulado:

```bash
uv run --locked pytest tests/test_observability.py tests/test_gemini_adapter.py -q
```

Los dos tests del adaptador que recorren HTTP y persistencia necesitan PostgreSQL;
ninguno realiza inferencias reales.

## Límites

- Se observa la operación de generación, no cada intento interno del SDK.
  No se cambia su política ni se usan APIs privadas para instrumentar retries.
- Fuera de HTTP, `request_id` es null si se configura este formatter. Esta issue
  configura la salida en el arranque de la API; no instrumenta el runner offline.
- Los logs propios son JSON; los logs de Uvicorn y librerías mantienen su
  configuración. La lista de campos no sanea mensajes arbitrarios: al añadir
  eventos deben mantenerse nombres constantes y metadata segura. No activar
  debug del SDK con datos sensibles. Los errores inesperados siguen pudiendo
  producir diagnósticos del servidor; los errores del SDK se traducen a las
  causas seguras existentes antes de llegar a esa capa.
- No hay métricas, tokens, coste, tracing ni plataforma de observabilidad.
