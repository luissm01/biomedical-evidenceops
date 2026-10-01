# D018 — Gemini y DeepSeek tras Generator

## Estado

Aceptada por encargo del desarrollador durante M5. Actualiza la elección de
proveedor único de [D011](D011-gemini.md), la composición descrita en
[D012](D012-generator-boundary.md) y la metadata de [D016](D016-structured-logging.md).
Las razones históricas y la política de retry de Gemini de D011 permanecen.

## Problema y decisión

La API y la evaluación deben poder usar varios proveedores sin cambiar sus
contratos. Se mantienen `Generator`, `GeneratedContent` y las causas de error.
`GeminiGenerator` y `DeepSeekGenerator` son adapters independientes; una factory
pequeña elige uno desde `GenerationSettings`. El proveedor por defecto sigue
siendo Gemini y se conservan sus variables existentes. DeepSeek usa su API HTTP
Chat Completions con JSON mode y validación local Pydantic.

Las instrucciones biomédicas son compartidas. Cada adapter clasifica sus propios
fallos y registra `llm.generation.started` con `provider` y `model`, sin contenido
ni secretos. No se añaden métricas de #22.

## Consecuencias

La factory añade una decisión de composición sencilla; no se adopta una capa
universal ni una dependencia de orquestación. Gemini solicita JSON Schema al
proveedor y permite el retry existente del SDK en 408/5xx. DeepSeek solicita
JSON mode, valida el esquema localmente y no hace retries propios. En DeepSeek,
HTTP 402 indica saldo insuficiente; se traduce a `PROVIDER_UNAVAILABLE` porque
EvidenceOps no tiene una causa específica de billing. El timeout
de ambos es de transporte, no un deadline global. Cambiar de proveedor puede
alterar calidad, cuota y latencia; requiere evaluación comparativa antes de
extraer conclusiones de calidad.
