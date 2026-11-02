# D033 — Agente único con LangGraph y presupuestos explícitos (M10.2, #57)

## Estado

Arquitectura y presupuestos aprobados expresamente por el desarrollador, con
precisiones sobre finalización, fuentes y estado mínimo. Implementación aceptada por el
desarrollador, con autorización de commit, push, PR, merge y cierre de #57.
Sin inferencias reales. El repaso de aprendizaje
requiere interacción posterior; no se acredita por generar código ni tests.

## Problema

M10.1 permite una propuesta, una herramienta y una finalización; no puede buscar
y después leer un candidato. Se necesita un ciclo donde el modelo decida la
siguiente acción a partir de resultados, conservando el control en la aplicación.

## Decisión

- Un `StateGraph` con nodos `decide`, `execute` y `close`. Solo `decide` llama al
  LLM; solo `execute` usa el ejecutor existente. Routing determinista según
  propuesta/resultado/estado. `close` valida y construye la salida sin inferencia.
- Estado efímero `TypedDict`: historial único, fuentes por UUID, decisión pendiente,
  firmas de llamadas, contadores, inicio, operation_id y estado/motivo terminal.
  Sin pregunta duplicada, lista paralela de resultados, checkpointer, store,
  memoria persistente, multiagente, MCP ni agente preconstruido.
- DeepSeek comparte transporte, parsing, errores, usage y serialización de
  intercambios con M10.1 mediante un turno sobre historial explícito. Conserva
  el servicio de una ronda y su prompt; el agente tiene instrucciones de ciclo
  propias. No se amplía `Generator`, ni se cambia RAG, retrieval o sus baselines.
- Reutilizar `ToolExecutor`, herramientas, contratos, límites por resultado y
  SQL de M10.1, sin nuevas herramientas ni duplicación de búsqueda/lookup.
- Máximo 4 solicitudes LLM, 3 herramientas secuenciales, 8 entradas en nodos,
  120 s cooperativos y cero reintentos. Cada intento externo cuenta antes de
  ejecutarse, también si falla. Tras la tercera herramienta, reservar la cuarta
  solicitud para finalizar con tools deshabilitadas. Una respuesta validada en
  esa llamada es satisfactoria; pedir otra herramienta es `limit_exceeded`.
- Los límites se comprueban antes del trabajo y el tiempo también al regresar.
  Un fallo o exceso descarta cualquier respuesta candidata. No se fabrica una
  respuesta satisfactoria ni se convierte un fallo técnico en abstención.
- Mantener timeout HTTP por fase acotado al tiempo restante, 5 s SQL por sentencia
  y 15 s cooperativos por herramienta. No hay deadline estricto ni cancelación
  de CPU, carga diferida, conexión/pool o trabajo HTTP continuo. Aislar procesos
  queda fuera de alcance. Un exceso detectado impide nuevas llamadas externas.
- `recursion_limit=10` como defensa adicional. Con la versión fijada en el lock,
  ocho entradas requieren un límite superior a ocho para salir sin error;
  pruebas de 1–10 verifican rechazo seguro y conservación de contadores.
- Historial serializado hasta 64.000 caracteres, sin truncar ni resumir; además
  de los límites de argumentos/resultados de M10.1. No equivale a tokens.
- Repetición exacta por herramienta y argumentos validados/canonicalizados:
  termina antes de repetir backend. IDs nativos reutilizados se rechazan.
  Ciclos con argumentos diferentes terminan por los presupuestos globales.
- Resultados vacíos, publicación inexistente y abstract null no son fallos de
  infraestructura; el modelo puede decidir de nuevo dentro del presupuesto.
  Ausencia de resultados locales no prueba ausencia de literatura.
- Fuentes exclusivamente desde resultados tipados del ejecutor. Registro por
  UUID con etiquetas S1…Sn estables, comprobación de identidad externa y copia
  etiquetada antes de introducir el resultado en el historial. Una búsqueda
  posterior no degrada el detalle ya leído. Ninguna referencia procede del LLM.
- Reutilizar `GeneratedContent`, `validate_tool_answer`, validación RAG de citas
  y abstención fija. Metadata permite describir candidatos, no hallazgos clínicos.
  Instrucciones explícitas: preguntas, metadata y abstracts son datos no confiables.
  Las validaciones estructurales no demuestran apoyo semántico ni resistencia
  absoluta a prompt injection; no se introduce juez ni evaluación clínica.
- Logs/spans M5 de operación, nodos y transiciones con IDs, contadores, duración,
  estado y motivo terminal. Uso observado del proveedor con métricas existentes.
  Sin volcar estado, preguntas, argumentos, abstracts, respuestas ni excepciones.

## Alternativas y trade-offs

- Un agente preconstruido ahorra composición, pero oculta decisiones y puede
  duplicar ejecución/validación. Tres nodos explícitos permiten recorrer el ciclo.
- Repetir `ToolCallingService.run` pierde historial y obliga a finalizar cada ronda.
  Compartir un turno del adaptador conserva contratos con un cambio pequeño,
  protegido por regresión de M10.1. No hay un segundo loop manual redundante.
- Un deadline con procesos aislados permite cancelar CPU, a cambio de lifecycle,
  serialización y complejidad ajenos a este aprendizaje. Se acepta presupuesto
  cooperativo documentado y comprobado con reloj simulado.
- Avisar al modelo de una repetición permitiría recuperación, pero consume otra
  llamada y requiere más política. Cortar la repetición exacta es simple; puede
  interrumpir un reintento que hubiera sido útil. No hay recuperación automática.
- Cortar tras la tercera herramienta desaprovecha evidencia recién obtenida.
  Reservar una finalización permite responder sin superar cuatro solicitudes;
  si falla, el resultado sigue siendo error o límite, con contenido nulo.

## Verificación y límites

Pruebas deterministas del grafo y transporte, integración con PostgreSQL y encoder
simulado, regresión de M10.1 y RAG, demo offline. No prueban aceptación del contrato
por un proveedor vivo, calidad biomédica, groundedness ni comprensión del desarrollador.
Procedimientos y recorrido: [agente](../subsystems/agent.md).
