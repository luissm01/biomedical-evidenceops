# Tool calling de una ronda — M10.1 (#56)

Decisiones aprobadas y trade-offs: [D032](../decisions/D032-controlled-tool-calling.md).
No hay endpoint nuevo ni agente. El servicio es independiente y efímero.

## Contratos

Referencia ejecutable: [tools.py](../../src/evidenceops/tools.py). Los esquemas de
argumentos se obtienen con `definition.arguments.model_json_schema()` desde
`TOOL_DEFINITIONS`. Tipos estrictos, sin campos adicionales; query normalizada
solo eliminando espacios exteriores. UUID como string; no se aceptan PMIDs en su lugar.

| Herramienta | Argumentos | Propósito y salida |
| --- | --- | --- |
| `search_evidence` | `query`: 1–2.000 caracteres; `top_k`: entero 1–5, default 5; `published_from`: entero positivo o null, opcional | Búsqueda semántica sobre corpus local indexado; filtro inclusivo por año. `data.items` en orden de retrieval, sin rellenar resultados ni umbral de confianza. Cada item incluye etiqueta, UUID, unidad/fingerprint, procedencia, título, año, journal, DOI, URL y score. **Sin abstract, autores ni text**; `detail_level=metadata`. |
| `get_publication` | `publication_id`: UUID interno como string | Bibliografía vigente del corpus persistido, incluso si no está indexada: etiqueta S1, UUID, source/source_id, título, año, journal, DOI, URL, autores y abstract completo o null. `detail_level=abstract` indica el contrato detallado, no garantiza que exista abstract. No obtiene texto completo. |

Campos bibliográficos ausentes conservan null. `source_id` es el PMID cuando
`source=pubmed`. Ni enlaces ni bibliografía proceden del texto generado.
El fingerprint del hit identifica la unidad recuperada; no implica que su texto
se haya entregado al modelo. El score ordena, no mide confianza clínica.

Ejemplos válidos:

```json
{"query":"evidencia sobre intervención X","top_k":3,"published_from":2020}
```

```json
{"publication_id":"123e4567-e89b-42d3-a456-426614174000"}
```

Inválidos: `{"query":" "}`, `{"query":"x","top_k":true}`,
`{"query":"x","top_k":6}`, `{"query":"x","published_from":"2020"}`,
`{"query":"x","mode":"hybrid"}`, `{"publication_id":"12345"}`.
También se rechazan objetos con claves duplicadas, listas y JSON mal formado.

Ejemplos de sobre (los items detallados siguen los modelos anteriores):

```json
{"call_id":"call_1","tool":"search_evidence","status":"ok","data":{"items":[]}}
```

```json
{"call_id":"call_1","tool":"get_publication","status":"error","error":{"code":"publication_not_found","message":"Publication does not exist in the local corpus"}}
```

Cada item satisfactorio lleva `citation_id`; la consulta detallada usa S1. El
servicio devuelve `answer`, `limitations`, `sources`, `tool_result` y `operation_id`.
`sources` contiene exactamente las entradas entregadas al modelo, incluso si este
se abstiene; no es el conjunto de referencias necesariamente citadas.

## Composición y ciclo

`ToolCallingService(model, executor).run(question)`:
propuesta → validar → ejecutar → resultado correlacionado → finalizar.
Una respuesta directa pasa la misma validación con cero fuentes; solo puede
ser la abstención fija. Como máximo una herramienta y dos solicitudes LLM.
Los fallos no disparan retries ni reparación. Nunca se ejecuta una segunda ronda.

`create_tool_executor(sessions, encoder)` enlaza `search` existente en modo
semántico y `get_publication` sobre SQLAlchemy. No cambia la selección RAG.
Las transacciones son de solo lectura y se cierran antes de esperar al LLM.
`ToolExecutor(retrieve, lookup)` permite inyectar dobles; quien compone esos
backends es responsable de sus timeouts y acceso de solo lectura.

`create_deepseek_tool_caller(GenerationSettings(...))` construye el adaptador
con `deepseek_*`, independiente del selector `llm_provider`. Requiere clave para
su construcción, pero no hace inferencia al crear recursos. El llamador posee y
cierra el adaptador y el Engine; el servicio no los cierra. No hay modo live en
la demo ni comando que consuma cuota por defecto. Toda llamada real requiere
otro encargo explícito. No pasar datos clínicos privados.

DeepSeek usa Chat Completions nativo, `thinking.type=disabled`, tools declaradas
en propuesta y `tool_choice=none` más JSON mode en finalización. La segunda
solicitud conserva la llamada del assistant y devuelve el resultado como mensaje
tool con el mismo ID. Solo se conserva lo necesario para esa operación en memoria.
No se añade SDK de OpenAI, proveedor nuevo, estado remoto ni fallback.

## Referencias y ausencia de evidencia

El modelo usa exclusivamente [S1]…[Sn]. Se reutiliza la validación RAG de
pertenencia, formato y citas al final de cada bloque, también en limitations.
Las URLs, DOI y referencias PMID explícitas en prosa se rechazan; la metadata
bibliográfica se devuelve desde la aplicación. Sin fuentes, la única salida
válida es `ABSTENTION_ANSWER` con `limitations=[]`; la aplicación añade después
la limitación operacional. Una búsqueda vacía no prueba ausencia de literatura.

La búsqueda solo permite descubrir candidatos; sus instrucciones no autorizan
describir hallazgos clínicos. Se añade una limitación de solo metadata en las
respuestas no abstencionistas. Los controles estructurales no detectan toda
bibliografía inventada en lenguaje libre ni prueban que una cita apoye una
afirmación. No son una evaluación de groundedness ni calidad IA.

## Límites y fallos

| Control | Semántica |
| --- | --- |
| 4.000 caracteres de argumentos | Medidos sobre el JSON recibido, incluidos escapes; exceso es `invalid_arguments`. |
| 20.000 caracteres de resultado | JSON compacto completo, metadata y sobre incluidos, Unicode literal. Igual al límite cabe; exceso es `result_too_large`. Sin truncar abstracts ni omitir resultados silenciosamente. |
| HTTP: 60 s por defecto | Timeout efectivo por fase connect/read/write/pool; se toma de `deepseek_timeout_seconds`. No es deadline total; una respuesta que siga enviando datos puede prolongarse. |
| SQL: 5 s por sentencia | `SET LOCAL statement_timeout`, solo en transacciones de las herramientas. No limita la espera de checkout/conexión ni el encoder. Cancelación PostgreSQL 57014 → `sql_timeout`. |
| Herramienta: 15 s cooperativos | Se mide el trabajo y se comprueba al regresar; exceso → `tool_budget_exceeded`, sin finalización LLM. No interrumpe MedCPT, PyTorch ni carga diferida. No es cancelación efectiva ni deadline global. |

`unknown_tool`, `invalid_arguments` y `invalid_call` rechazan el protocolo antes
de ejecutar; `call_limit_exceeded` rechaza propuestas múltiples antes del backend;
`round_limit_exceeded` rechaza una nueva propuesta al finalizar. Una publicación
inexistente devuelve el error de dominio correlacionado al LLM; búsqueda vacía
devuelve éxito con lista vacía. `backend_error`, `tool_timeout`, `sql_timeout`,
`tool_budget_exceeded` y `result_too_large` terminan sin respuesta satisfactoria.
Errores del proveedor conservan las causas existentes de `GenerationError`.
Citas inválidas usan `INVALID_OUTPUT`; referencias directas prohibidas producen
`invalid_references`. Ninguno se convierte silenciosamente en abstención.

Logs/spans `tool_calling.*`: operation, proposal, validation, execution, result,
finalization. JSON conserva `operation_id`, `call_id`, `tool`, estado, duración y
causa; IDs de trace/span vienen de M5. El proveedor genera spans `llm.deepseek`
y usage observado opcional con `GenerationMetrics`. No se registran preguntas,
argumentos, abstracts, respuestas, claves ni excepciones originales.

## Demo y pruebas sin inferencias

```bash
uv run --locked python -m evidenceops.tool_calling_demo --scenario search
uv run --locked python -m evidenceops.tool_calling_demo --scenario publication --logs
uv run --locked python -m evidenceops.tool_calling_demo --scenario second-round
```

Escenarios: `search`, `publication`, `empty`, `not-found`, `invalid`, `unknown`,
`second-round`, `backend-error`. Siempre `httpx.MockTransport`, clave ficticia,
datos sintéticos, sin DB, red ni descargas. Una demostración satisfactoria realiza
dos solicitudes **simuladas**. El texto es prefijado, no una respuesta clínica.

```bash
uv run --locked pytest tests/test_tools.py tests/test_tool_calling.py tests/test_deepseek_tools.py
uv run --locked pytest tests/test_tools_integration.py tests/test_rag_integration.py
```

La segunda orden requiere PostgreSQL de pruebas preparado según el README.
Prueba el retrieval y lookup reales con encoder y LLM dobles, timeout SQL real,
transacción de solo lectura y liberación de conexión antes de la finalización.
Las pruebas de transporte verifican serialización, IDs, límites, errores y
configuración de timeout; el ReadTimeout HTTP se inyecta, no mide una red viva.
Contrato externo de referencia y límites de la evidencia: [D032](../decisions/D032-controlled-tool-calling.md#evidencia-y-verificación).
