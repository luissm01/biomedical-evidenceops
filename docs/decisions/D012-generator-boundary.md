# D012 — Frontera LLM con un Protocol de una operación

## Status

Accepted e implementada en #9.

## Problem and decision

La generación debe poder sustituirse por un fake en tests y el resto de la
aplicación no debe depender del SDK Gemini. El desarrollador eligió un
`Protocol` con `generate(question_text: str) -> GeneratedContent`.

`GeneratedContent` contiene solo `answer` y `limitations`. Gemini recibe un
JSON Schema derivado de ese modelo y el adaptador vuelve a validar su salida
con Pydantic. La estructura válida no prueba veracidad. EvidenceOps añade
`external_sources_consulted: false` en `GenerationResponse`, separado del modelo
interno: es conocimiento de la aplicación sobre su ejecución, no del LLM.

Se adopta `GenerationError` con una causa identificable, sin jerarquía adicional.
En #11 se clasifican `TIMEOUT` (transporte/408), `RATE_LIMIT` (429),
`AUTHENTICATION` (401/403), `PROVIDER_UNAVAILABLE` (conexión/5xx),
`INVALID_OUTPUT` (contenido inválido) y `UNKNOWN` (errores restantes). Se recorren las causas explícitas
para encontrar el error de transporte, y los atributos `status_code`/`code`
para el HTTP, sin importar clases privadas del SDK.

La API traduce esas causas a 504, 429, 503, 503, 502 y 502 respectivamente.
Credenciales inválidas del proveedor no son un 401 del consumidor: se exponen
como `generation_unavailable`, igual que indisponibilidad. `detail` contiene
`code` y `message` fijos; ni la excepción ni su cadena se serializan al cliente.
La causa original se conserva para diagnóstico interno. No se exponen tipos
del SDK en el contrato ni se cambia GeneratedContent/Generator.

## Trade-offs

La frontera añade poco código y permite tests sin proveedor real. La clase
concreta gestiona el cierre del SDK; el Protocol conserva una sola operación.
No se añaden factories, registries, managers, repositorios ni frameworks de DI.

## Integración HTTP y ownership (#10)

`create_app` recibe opcionalmente un Generator. El handler lo obtiene mediante
`Depends(get_generator)` desde `app.state`, sin construir GeminiGenerator. Esto
mantiene la frontera de #9 y permite utilizar FakeGenerator sin llamadas reales.

El lifespan crea y reutiliza GeminiGenerator cuando no hay uno inyectado y lo
cierra al apagar la aplicación. Un generador externo pertenece a quien lo
entrega: la aplicación no llama a su `close()`. El Engine se libera incluso
si falla el cierre del generador. Esta regla hace explícita la responsabilidad
sobre los recursos sin ampliar el Protocol ni introducir otra capa.
