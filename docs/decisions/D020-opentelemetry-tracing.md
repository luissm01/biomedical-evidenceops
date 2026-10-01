# D020 — Tracing OpenTelemetry mínimo para generaciones (#23)

## Estado

Aceptada e implementada localmente; pendiente revisión humana.

## Problema y alternativas

El `request_id` relaciona logs y Prometheus agrega observaciones, pero no
muestra dónde transcurre una generación concreta. Se valoraron marcas de tiempo
propias, instrumentación automática de toda la API y spans manuales de
OpenTelemetry. La primera duplicaría un estándar; la segunda añadiría ruido y
dependencias para operaciones fuera de #23.

## Decisión y consecuencias

Se usan `opentelemetry-sdk` y su API transitiva. Un span SERVER de la ruta de
generación contiene un span `generation`; este contiene `llm.gemini` o
`llm.deepseek`, que abarca llamada y validación del adapter. OpenTelemetry mide
sus duraciones y propaga el contexto entre ASGI y el handler síncrono. La
instrumentación es manual y acotada; no desglosa retries internos del SDK.

Un provider SDK del proceso crea spans. Por defecto no los exporta; la opción
`EVIDENCEOPS_TRACE_CONSOLE=true` añade una salida local a stderr para diagnóstico.
No se despliegan collector, backend ni infraestructura distribuida. La salida
de consola es para desarrollo y su formato no es un contrato estable.

Los atributos conservan ruta plantilla, provider, model, outcome y causa
clasificada. Los errores se marcan con estado ERROR y `record_exception` recibe
una excepción sintética con causa segura: la excepción original del SDK podría
contener texto sensible en mensaje o cadena. Se conserva la excepción original
para el control de flujo HTTP, sin serializarla en spans. No se guardan prompts,
respuestas ni IDs de pregunta. Los logs JSON añaden `trace_id` y `span_id` solo
cuando hay span activo; mantienen `request_id` y sus eventos existentes.
