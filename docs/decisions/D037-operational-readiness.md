# D037 — Preparación operativa: dependencias, coste y secretos (M11.2)

## Estado

Decisiones de alcance cerradas por el desarrollador en el encargo de M11.2 (#67).
Implementación con tests deterministas; sin inferencias LLM. Completa, sin
reescribirla, la política de transporte de [D011](D011-gemini.md).

## Problema

Tras M11.1, una caída de PostgreSQL después del arranque producía 500 no
controlados; nada indicaba a un balanceador u orquestador si una instancia podía
recibir tráfico; una llamada LLM no tenía cota total de tiempo (D011); y
cualquiera con acceso de red podía escribir datos o gastar cuota LLM.

## Decisión

**Liveness y readiness.** `GET /health` no comprueba dependencias. Si lo hiciera,
una caída de PostgreSQL haría que el orquestador reiniciara todas las instancias
sanas: más carga sobre la BD en recuperación, arranques que fallan y ningún
arreglo, porque el problema no está en el proceso. `GET /ready` comprueba
conexión y que `alembic_version` coincide con el head de los scripts del código
desplegado (un despliegue con esquema atrasado no debe recibir tráfico); responde
503 con estados sin contenido (`ok`, `unavailable`, `outdated`, `missing`).

**Caída de PostgreSQL.** Un manejador de `OperationalError`, `InterfaceError` y
timeout del pool devuelve 503 `{"detail":{"code":"database_unavailable",...}}`,
la misma forma `{code, message}` que los errores tipados existentes y el mismo
código que el RAG ya usaba. Errores de integridad o programación siguen siendo
500. `pool_pre_ping` descarta las conexiones rotas al reutilizarlas, y la API se
recupera sin reiniciar. `connect_timeout` (5 s) y `statement_timeout` (30 s)
acotan la espera. El worker aplica backoff exponencial con tope (60 s) a fallos
consecutivos del polling y lo reinicia al primer éxito.

**Límite total LLM.** `DeadlineGenerator` envuelve a todos los generadores
creados por la factoría y ejecuta la llamada en un hilo daemon. El llamador espera
como máximo `llm_total_timeout_seconds` (90 s) y recibe
`GenerationErrorCause.DEADLINE_EXCEEDED` (HTTP 504
`generation_deadline_exceeded`). El hilo hereda `contextvars` (request_id, span).

**Autenticación.** Claves estáticas `EVIDENCEOPS_API_KEYS` (≥16 caracteres) en
la cabecera `X-API-Key`, solo en `POST /questions`, `POST /ingestion-jobs`,
generate y RAG. Se compara con `hmac.compare_digest` contra todas las claves,
sin salida temprana. La cabecera se lee directamente para que una clave nunca
vuelva en un 422. Las dependencias de ruta se ejecutan antes que la consulta a
la BD o la validación del cuerpo, así que un anónimo recibe 401 sin aprender
nada más. La API no arranca sin claves: es fail-closed.

**Rate limiting.** Token bucket en memoria por clave (capacidad 5, recarga
0,1/s), compartido por generate y RAG, con 429 `rate_limited` y `Retry-After`
calculado a partir del déficit de tokens. Escrituras sin coste LLM no se limitan.

**Secretos.** `database_url` pasa a `SecretStr`, porque la URL contiene la
contraseña, y se accede con `database_dsn` solo para crear el Engine. Las claves
LLM, PubMed y API ya eran o pasan a ser `SecretStr`. Los errores de validación
no reproducen la URL. Logs y métricas usan causas constantes, nunca la clave ni
su identificador. Además, `published_from` se limita a ≤9999 para que un entero
enorme no provoque un desbordamiento en PostgreSQL y un 500.

## Alternativas descartadas

- **Liveness con BD:** convierte una caída de dependencia en reinicios en cascada.
- **Mapear todo `SQLAlchemyError` a 503:** ocultaría bugs (constraint violada,
  SQL inválido) como si fueran indisponibilidad transitoria.
- **Límite total con señales (`SIGALRM`) o cancelación HTTPX:** las señales solo
  funcionan en el hilo principal (no en el threadpool de FastAPI), y HTTPX no
  tiene deadline global ni controla los reintentos internos del SDK de Gemini.
  Migrar a async (`asyncio.timeout`) sí cancelaría, pero cambia los adaptadores
  y los contratos de M3–M10.
- **Una sola clave en vez de lista:** no permitiría rotar sin cortar el servicio
  ni separar consumidores en el rate limit.
- **OAuth/JWT/usuarios:** sin usuarios reales ni roles, añaden superficie sin
  resolver un problema actual.
- **Rate limit distribuido (Redis) o por IP:** Redis es otro servicio, injustificado
  con una instancia. Limitar por IP no identifica al consumidor detrás de un proxy
  o NAT.
- **Límite de tamaño de cuerpo en la aplicación:** se deja al proxy o ingress
  (M12). Los campos ya están acotados (≤2.000 caracteres) tras el parseo.

## Consecuencias y límites

- La llamada LLM se **abandona, no se cancela**: tras el deadline el proveedor
  puede completar y cobrar, y el hilo termina cuando vencen sus timeouts de
  transporte. Bajo picos pueden coexistir hilos abandonados; el rate limit lo
  acota.
- El rate limit no se comparte entre procesos: con N instancias o workers de
  uvicorn, cada uno tiene sus buckets y el límite efectivo es N veces el
  configurado. Se reinicia con el proceso.
- `pool_pre_ping` detecta conexiones cerradas (reinicio o parada de la BD). Una
  partición de red silenciosa puede esperar hasta los timeouts TCP del sistema.
  `statement_timeout` no cubre esa espera.
- El tool calling de M10 usa su propio cliente DeepSeek y el presupuesto
  cooperativo del agente, no `DeadlineGenerator`. No está expuesto por HTTP.
- Sin TLS, el transporte de la clave depende del despliegue (M12).
