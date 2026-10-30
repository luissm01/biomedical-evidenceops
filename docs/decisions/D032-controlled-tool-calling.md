# D032 — Herramientas de lectura y una ronda controlada (M10.1, #56)

## Estado

Arquitectura aprobada por el desarrollador, con ajustes de búsqueda compacta,
DeepSeek sin razonamiento y uso puntual de su API de pago. Implementación
aceptada expresamente por el desarrollador, con autorización de commit, PR,
merge y cierre de #56. Sin inferencias reales. El cierre de aprendizaje
requiere interacción posterior: el código generado no acredita comprensión.

## Problema

Permitir que un modelo proponga una operación sobre evidencia pública local,
sin confiarle la ejecución ni introducir todavía un agente. Preservar Generator,
RAG, selección de proveedores y baselines existentes.

## Decisión

- Dos herramientas: `search_evidence` descubre publicaciones mediante metadata
  compacta; `get_publication` lee bibliografía y abstract completo por UUID local.
  Ambas conservan identidad externa y procedencia. No consultan PubMed, ingieren,
  indexan, persisten respuestas ni ejecutan escrituras.
- Reutilizar `search` semántico y `Publication`/`as_biomedical_document`; añadir
  una función pequeña de lectura. No exponer al modelo estrategias de retrieval
  ni configuración. Las herramientas no cambian el flujo RAG.
- `ToolCallingModel` separa propuesta/finalización de `Generator.generate`.
  Contratos internos pequeños, sin jerarquía de mensajes universal ni SDK externo
  en el servicio. La salida final reutiliza `GeneratedContent`.
- Un registro fijo de dos herramientas, argumentos Pydantic estrictos y campos
  adicionales prohibidos. Rechazar JSON inválido, claves duplicadas y argumentos
  excesivos antes de tocar el backend.
- Una propuesta, como máximo una herramienta y una finalización: hasta dos
  solicitudes LLM. Cero retries de aplicación/transporte propios; sin reparación,
  fallback, bucle genérico, LangGraph ni MCP. Una nueva llamada en finalización
  termina con error. Buscar y luego consultar lo descubierto queda para #57.
- DeepSeek `deepseek-flash` como único adaptador inicial de esta capacidad,
  Chat Completions con `thinking.type=disabled`, historial efímero explícito,
  resultado con `tool_call_id` original y herramientas deshabilitadas al finalizar.
  No alterar los adaptadores ni la factory de generación existentes. La nueva
  composición usa sus ajustes `deepseek_*`, independientemente de `llm_provider`.
- Uso puntual de API de pago autorizado como excepción explícita para esta
  capacidad; no añade obligación de servicio de pago ni autoriza inferencias.
  Demo y pruebas funcionan sin claves reales, red ni descargas.
- Referencias bibliográficas desde los resultados de la aplicación. Las etiquetas
  S1…Sn se asignan solo a lo entregado al modelo y se validan con las mismas reglas
  estructurales del RAG, ahora disponibles por IDs sin cambiar su comportamiento.
  La prosa usa solo etiquetas: se rechazan URLs, DOI y referencias explícitas PMID.
  Sin fuentes solo se admite la abstención fija. La búsqueda añade una limitación
  operacional que explicita que solo se consultó metadata.
- Respuestas completas con máximo de 20.000 caracteres del JSON compacto del
  resultado; exceso produce error sin truncar abstracts. Query de hasta 2.000
  caracteres; argumentos serializados de hasta 4.000; top-K entre 1 y 5.
- Timeouts de transporte HTTP por fase (60 s por defecto), timeout SQL efectivo
  de 5 s por sentencia y presupuesto cooperativo de herramienta de 15 s medido
  al volver del trabajo. No equivalen a un deadline total ni a cancelación de CPU.
  Transacciones cortas de solo lectura; sin conexiones retenidas durante el LLM.
- Observabilidad M5: operación, propuesta, validación, ejecución, resultado y
  finalización correlacionados mediante trace/operation/call IDs. Nombre de
  herramienta desconocida normalizado para logs; sin contenido ni excepciones
  arbitrarias. Reutilizar métricas de usage observado, sin estimar coste.

## Alternativas y trade-offs

- Ampliar `Generator` con historial y retornos alternativos afectaría todos sus
  consumidores. Una capacidad separada conserva la frontera simple del RAG a
  cambio de un Protocol adicional justificado por el nuevo intercambio.
- Devolver abstracts en la búsqueda permitiría síntesis inmediata, pero oculta
  la distinción descubrimiento/lectura. Metadata compacta reduce contexto y hace
  visible ese límite; con una sola llamada no se encadenan ambas herramientas.
- Gemini era viable; el desarrollador eligió DeepSeek y aceptó su coste puntual.
  Implementar ambos anticiparía trabajo sin evaluación comparativa autorizada.
- Omitir o truncar fuentes ante exceso aprovecha más resultados, pero añade una
  política de selección. Rechazar el resultado completo es simple y trazable,
  aunque limita publicaciones grandes. Los caracteres no garantizan tokens.
- Aislar MedCPT en un proceso permitiría imponer un deadline estricto; añade
  lifecycle y cancelación fuera del alcance. Se acepta presupuesto cooperativo,
  sin fingir que un hilo o un temporizador detienen la inferencia.
- Citas estructuralmente válidas prueban pertenencia y cobertura, no apoyo
  semántico. Las instrucciones limitan la síntesis y bibliografía libre; una
  afirmación inventada con [S1], incluidos autor/año o resultados no leídos, puede
  superar esos controles. No se añade un juez ni se acredita calidad IA.

## Evidencia y verificación

Contrato externo consultado sin inferencia:
[tool calling](https://api-docs.deepseek.com/guides/tool_calls/),
[modo sin razonamiento](https://api-docs.deepseek.com/guides/thinking_mode/),
[Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/).
El transporte simulado prueba nuestras solicitudes y respuestas prefijadas, no
que un proveedor vivo acepte hoy cada combinación ni su calidad/cuota disponible.

Operación, contratos, ejemplos y límites: [herramientas](../subsystems/tools.md).
