# D027 — Integración HTTP, errores y observabilidad RAG (#46)

## Estado

Implementada y aceptada por el desarrollador al autorizar la entrega de #46.
Conserva el diseño de contexto, citas y abstención de D026.

## Problema y alternativas

El servicio RAG de #45 necesita una interfaz operativa y distinguir abstención de
fallo técnico. Podría vincularse a una pregunta persistida como la generación M3,
o recibir directamente el contrato `query`, `published_from` de D026.

Se elige `POST /rag` con JSON: evita persistencia y pasos adicionales para una
operación efímera. La generación previa conserva su ruta y contrato. No se añade
`external_sources_consulted` a la respuesta RAG: `sources` identifica exactamente
las fuentes incluidas, incluso si no fueron citadas. El esquema HTTP serializa
`RagSource` y su unidad completa sin reinterpretar su procedencia.

## Composición y errores

El lifespan liga `search` de M7 a las sesiones y a una instancia de `LocalMedCPT`,
y comparte el generador de la factoría existente con ambos endpoints. La carga
de pesos sigue siendo diferida. La factory posee el cierre del proveedor y del
engine; el servicio no posee recursos. Se puede inyectar un encoder determinista
para probar la composición real con PostgreSQL sin cargar modelos.

- Abstención local o del modelo: 200, mismo contrato de tres campos.
- Entrada inválida: 422 de FastAPI antes de ejecutar RAG. Query de 1–2000 caracteres
  tras eliminar espacios exteriores; año entero positivo estricto, opcional/null;
  campos adicionales prohibidos, igual que en la creación de preguntas.
- Errores SQLAlchemy en retrieval: 503 `database_unavailable`; configuración
  incompatible: 503 `retrieval_incompatible`; errores de ejecución/carga/valor
  del encoder (`OSError`, `RuntimeError`, `ValueError`): 503 `retrieval_unavailable`.
  `RagRetrievalError` conserva la causa interna sin serializarla. No se captura
  cualquier excepción como falta de evidencia; los otros errores llegan al 500.
- LLM: se reutilizan los códigos HTTP existentes para timeout, cuota,
  autenticación, indisponibilidad, esquema inválido y error desconocido.
- Citas/cobertura/abstención inválidas: 502 `invalid_citations` mediante un subtipo
  de `GenerationError(INVALID_OUTPUT)`. Permite distinguirlo de JSON/esquema
  inválido del proveedor sin cambiar la causa acordada ni inspeccionar mensajes.
- Errores inesperados: 500 existente, con telemetría de causa segura.

No hay reparación de salida, retry RAG ni fallback que oculte errores como
abstenciones. Se conserva la política de transporte de cada proveedor.

## Observabilidad y consecuencias

Se reutilizan logger JSON, correlación, registry Prometheus y tracer de M5.
El servicio observa `operation`, `retrieval`, `context` y `generation` mediante
un context manager pequeño. La métrica opcional mantiene compatible el uso local.
La operación completa incluye retrieval, contexto y generación con validación de
citas; excluye validación de entrada, serialización y transporte HTTP. Contexto
incluye la construcción del mensaje. Generation incluye la validación de citas;
el span hijo del adapter sigue midiendo solo su frontera existente.

Abstención se distingue de éxito con `outcome=abstention` y estado de span OK;
retrieval/context siguen siendo etapas exitosas cuando no hay evidencia. No se
emite generación si se decide abstención local. Los errores se cuentan en la etapa
fallida y en la operación: agregar ambas contaría dos veces el mismo fallo.
No se duplica el contador M5 de generaciones, propio de la ruta anterior; los
contadores de tokens reales del adapter se comparten y no se duplican.

La API usa handlers síncronos, igual que el resto del proyecto; el primer acceso
RAG puede incluir carga de modelos y descarga de pesos si no están en caché.
No se introduce warmup, streaming, workers ni nueva infraestructura. Diagnóstico,
métricas y demostración en el [subsistema](../subsystems/observability.md) y el
[README](../../README.md#rag-desde-la-api-m8--46).


El diagnóstico de validación añade a logs y spans un motivo estable y una
localización numérica (campo, elemento, bloque y offset, cuando proceda).
No cambia aceptación, contrato HTTP, causa INVALID_OUTPUT ni labels de métricas;
no guarda fragmentos ni respuestas. El [procedimiento de diagnóstico](../subsystems/observability.md#diagnosticar-502-invalid_citations-sin-registrar-contenido)
explica precedencia, límites y restricciones que necesitan acuerdo para cambiarse.
