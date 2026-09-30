# D011 — Gemini como único proveedor de M3

## Status

Accepted; proveedor acordado el 2026-09-15 y política de fiabilidad
actualizada en #11 el 2026-09-17.
Sustituye el plan anterior de Gemini seguido de Ollama dentro de M3.

## Problem and decision

Usar únicamente Gemini mediante `google-genai`, con `gemini-3.6-flash`,
2.048 tokens máximos de salida y 60 segundos de timeout de transporte en cada
intento, sin presupuesto total exacto. El modelo
es el acordado por el desarrollador para esta integración; se elimina la
referencia anterior a `gemini-3.8-flash`. El desarrollador configuró la clave
local y confirmó una primera inferencia estructurada correcta. No se publica
la clave ni se repite automáticamente la inferencia. El objetivo sigue siendo
usar la opción gratuita; no se presupone una cuota fija para cada proyecto.

Ollama queda aplazado: podrá reconsiderarse cuando tenga sentido comparar
modelos en Evaluation, sin comprometer ahora su implementación en M4.

La clave sigue siendo opcional en Settings para permitir un Generator inyectado.
Desde #10, si no se inyecta uno, la API falla al arrancar sin clave configurada:
la generación es una dependencia esencial. No se valida la credencial contra
el proveedor ni se hace inferencia al arrancar. Modelo, tokens y timeout se
validan. El script manual detecta la ausencia de clave antes de crear el cliente
y lo cierra mediante `contextlib.closing`.

Política aprobada en #11: cero retries propios; `attempts=1` permite como máximo
un retry del SDK Interactions 2.23.0 para HTTP 408/500/502/503/504. No se reintentan
400/401/403/429 ni contenido inválido. Los tests con transporte simulado muestran
que el SDK traduce timeouts/conexión antes del mecanismo de retries: esos fallos
no se reintentan. Se conserva este comportamiento más conservador, sin parches
privados ni otro bucle de retry, respetando el máximo aprobado.

El backoff configurado es 0,5 s sin jitter. El SDK respeta `Retry-After` y
`retry-after-ms` por encima de `max_delay`. HTTPX aplica el timeout a operaciones
de transporte, incluida la espera entre fragmentos; no es un deadline global.
Por tanto, 120,5 segundos no constituye una cota total. Se acepta no introducir
cancelación externa en M3. Un retry puede repetir una inferencia ya ejecutada
y consumir cuota adicional: un fallo de confirmación no prueba que no se ejecutó.

## Trade-offs

El límite de un retry permite recuperarse de ciertos fallos transitorios sin
encadenar intentos propios y del SDK. A cambio, puede aumentar latencia y cuota;
no reintentar 429 devuelve el control al consumidor en lugar de esperar dentro
de la petición. No añadir cancelación externa mantiene sencilla la integración,
pero deja explícitamente sin garantizar un límite temporal total.

Un proveedor permite cerrar la primera integración con una frontera sencilla.
La API remota depende de disponibilidad y cuotas externas; la primera llamada
real demuestra conectividad y formato, no calidad factual. La generación es
efímera: no se persisten respuestas en PostgreSQL y se solicita `store=False`
a Interactions. Esto no sustituye las condiciones de tratamiento de datos del
proveedor. No se incorporan LangChain ni LangGraph.
