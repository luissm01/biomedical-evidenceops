# D034 — MCP local sobre los contratos existentes (M10.3)

## Estado

SDK oficial Python v2 y stdio elegidos por el desarrollador. Implementación
validada y aceptada por el desarrollador; commit, push, PR y merge autorizados.
Sin inferencias LLM reales.

## Problema

Exponer las dos herramientas de M10.1 a un cliente MCP y utilizarlas desde el
agente M10.2 sin duplicar servicios ni sustituir sus políticas de ejecución.

## Decisión

- SDK oficial `mcp>=2,<3`, resolución reproducible en el lock. Servidor de bajo
  nivel v2 con callbacks explícitos para catálogo/ejecución: permite publicar los
  JSON Schemas Pydantic existentes sin redeclarar firmas ni coerción adicional.
- Un proceso local por contexto cliente, transporte stdio; stdout reservado al
  protocolo. Servidor sin LLM ni acceso a PubMed: compone `create_tool_executor`
  con PostgreSQL y `LocalMedCPT`, conservando SQL read-only y timeouts existentes.
- Descubrimiento obligatorio y comprobación de nombres, esquemas de entrada y
  salida antes de entregar el ejecutor al agente. El agente conserva las
  descripciones locales aprobadas; no incorpora instrucciones remotas.
- `AgentToolExecutor` describe únicamente `validate/execute`. El ejecutor directo
  sigue disponible; `MCPToolExecutor` adapta un cliente asíncrono mediante un portal
  AnyIO. No se introduce otro grafo ni se migra el agente a async.
- Validación compartida de argumentos tanto antes del transporte como en el
  servidor. `structured_content` contiene `ToolResult`, validado de nuevo en el
  cliente; texto JSON equivalente para clientes genéricos. El ID nativo del LLM
  se repone en el cliente: no se confunde con el ID de petición MCP.
- Publicación ausente conserva el resultado de dominio recuperable existente
  (`status=error`, `is_error=false`). Fallos técnicos usan `is_error=true` y un
  código fijo estructurado; nunca texto de excepciones. El grafo termina sin
  convertir fallos en abstenciones. Catálogo incompatible o resultados inválidos
  se rechazan; no hay negociación de herramientas nuevas.
- Cliente con timeout de lectura de 15 s por llamada. Servidor mantiene 15 s
  cooperativos y 5 s SQL por sentencia. El timeout no garantiza interrumpir CPU;
  el SDK cierra stdin y espera/termina el subproceso al salir del contexto.
  Descubrimiento y cierre ocurren fuera de la operación del grafo. Sus 120 s
  siguen siendo cooperativos y sus límites 4/3/8 permanecen intactos.
- Se usa `Client.session.call_tool`, la vía pública de bajo nivel, para evitar
  el reenvío automático por `HEADER_MISMATCH` del `Client.call_tool` de v2.
  Sin retries ni rondas interactivas. El propietario del contexto cierra cliente,
  portal y subproceso; el servidor libera su Engine al salir normalmente.

## Alternativas y trade-offs

- Decoradores con firmas paralelas simplifican ejemplos, pero duplican contratos
  y pueden introducir coerción distinta a M10.1. Los callbacks reutilizan schemas
  y ejecutor como única fuente de validación y lógica de negocio.
- Migrar el grafo completo a async facilitaría await directo, a costa de alterar
  M10.2. El portal añade un hilo y lifecycle explícito, manteniendo `run` compatible.
- HTTP remoto exigiría otra frontera operativa y autenticación; queda fuera del
  encargo, al igual que recursos, prompts MCP, nuevas herramientas y multiagente.

## Verificación y límites

Tests SDK, stdio real, timeouts, contratos, errores, límites/citas del grafo y
PostgreSQL con encoder/modelo deterministas. Demo sintética y modo sobre corpus
local sin llamadas al LLM. No acreditan calidad biomédica ni aprendizaje del
desarrollador. [Operación y reproducción](../subsystems/mcp.md).

Referencias: [SDK oficial v2](https://py.sdk.modelcontextprotocol.io/),
[cliente y transporte](https://py.sdk.modelcontextprotocol.io/client/).
