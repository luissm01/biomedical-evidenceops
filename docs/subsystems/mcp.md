# MCP local (M10.3)

`AgentService → MCPToolExecutor → SDK Client → stdio → Server → ToolExecutor → servicios/DB`.

El servidor publica únicamente `search_evidence` y `get_publication`, con los
[contratos de M10.1](tools.md). Búsqueda semántica top-5 y lectura por UUID local;
no indexa, ingiere ni consulta PubMed. Los esquemas se derivan directamente de
Pydantic y los servicios conservan SQL read-only, timeout y límites de tamaño.
No se publica ningún recurso ni prompt MCP. Decisión: [D034](../decisions/D034-local-mcp-integration.md).

## Composición y propiedad

```python
from evidenceops.agent import AgentService
from evidenceops.mcp_client import connect_mcp_tools

# model implementa AgentModel; crear/cerrar el adaptador sigue siendo responsabilidad
# del llamador. Esta composición por sí sola no hace inferencias.
with connect_mcp_tools() as executor:
    agent = AgentService(model, executor)
    # response = agent.run(question)  # usar solo con autorización de inferencia
```

El contexto inicia un subproceso con el mismo Python del cliente, descubre y
verifica el catálogo, y al salir cierra cliente, portal AnyIO y proceso. Debe
abarcar todo el run. El ejecutor directo de M10.1 sigue funcionando. El grafo
conserva presupuestos 4 LLM / 3 herramientas / 8 nodos / 120 s cooperativos,
registro estable de citas y validación final. Las descripciones aprobadas son
locales; el descubrimiento no amplía el conjunto de herramientas del modelo.

`ToolResult` viaja en `structured_content`, junto al JSON equivalente en `content`.
El cliente valida esquema, coherencia, herramienta y tamaño; sustituye el ID de
correlación del servidor por el ID nativo del LLM. `publication_not_found` es un
resultado de dominio (`status=error`, `is_error=false`) recuperable por el agente.
Fallos técnicos son `is_error=true`, con `structured_content={"code": "…"}` y texto
fijo; no contienen argumentos ni excepciones del backend. Códigos de M10.1 se
conservan. `mcp_connection_error` cubre transporte/proceso; `mcp_contract_error`,
catálogo incompatible o respuestas inválidas. El grafo devuelve error y contenido
null. No hay retries ni rondas de solicitud de datos adicionales.

Timeout de lectura de 15 s por llamada; en servidor, 15 s cooperativos y 5 s SQL
por sentencia. CPU/carga de modelos no se interrumpen necesariamente al cancelar
la petición. La salida del contexto aplica el cierre acotado del SDK al proceso.
El arranque/descubrimiento y cierre están fuera del tiempo del grafo. Una carga
MedCPT en frío puede agotar el timeout; no se amplía ni reintenta automáticamente.

## Demo reproducible sin LLM ni DB

Desde la raíz:

```bash
uv sync --locked --dev
uv run --locked python -m evidenceops.mcp_demo
uv run --locked pytest tests/test_mcp.py
```

Usa stdio real y el grafo real con datos sintéticos y un modelo de decisiones
prefijadas. Resultado esperado: `answered`, 3 decisiones simuladas, 2 herramientas,
6 nodos, fuente `S1` con abstract y `real_llm_calls=0`. No necesita API keys,
red, pesos de modelos ni DB. No genera afirmaciones biomédicas.

## Demo real sobre la base de datos local, sin LLM

Requiere `.env` con `EVIDENCEOPS_DATABASE_URL`, PostgreSQL con migraciones,
publicaciones ya ingeridas e índice MedCPT compatible vigente. Preparación de
corpus/índice en [README](../../README.md#embeddings-y-retrieval-local-m7--39).
La demo solo lee; no reindexa automáticamente.

```bash
docker compose up -d --wait postgres
uv sync --locked --dev --extra medcpt
uv run --locked alembic upgrade head
uv run --locked --extra medcpt python -m evidenceops.mcp_demo --local-db --query 'type 2 diabetes treatment'
```

Este modo ejecuta el encoder MedCPT de consultas local (los pesos deben estar
presentes o se descargarán al primer uso); no usa LLM, API de pago ni claves LLM.
El texto final es una confirmación prefijada de lectura del abstract, no una
síntesis clínica. Una búsqueda vacía/publicación sin abstract da abstención.
`llm_calls` cuenta decisiones del doble por compatibilidad del grafo;
`real_llm_calls` permanece en cero. Un fallo técnico conserva estado/motivo de error.

Para evitar descargas con pesos ya disponibles:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --locked --extra medcpt python -m evidenceops.mcp_demo --local-db --query 'type 2 diabetes treatment'
```

Si la demo termina en `backend_error` en la primera herramienta, ese código
por sí solo no identifica qué dependencia falló. Comprueba primero que se ejecuta
con `--extra medcpt`: `uv sync --locked --dev` retira los extras opcionales no
solicitados, aunque los pesos y los embeddings persistidos sigan presentes.
La falta de `transformers`/`torch` falla al codificar la query, antes de consultar
el índice. No requiere reingerir publicaciones ni reindexar; se resuelve con
`uv sync --locked --dev --extra medcpt` o con el comando de demo anterior.

El índice puede estar preparado aunque falte el encoder de consultas en el
entorno Python. A la inversa, tener el encoder instalado no garantiza que haya
publicaciones ni embeddings vigentes. Con el encoder operativo, un índice vacío
produce una búsqueda vacía y la demo se abstiene. El buscador devuelve los vecinos
más próximos sin umbral de relevancia: un corpus de asma puede devolver candidatos
para una query de diabetes. `answered` en esta demo solo confirma la lectura de un
abstract; no acredita pertinencia del corpus ni una respuesta clínica a la query.

El subproceso normal lee `.env` desde el directorio actual. El cliente propaga
explícitamente la URL DB del entorno y las variables HF de caché/offline; el SDK
hereda su entorno mínimo de sistema. No propaga claves LLM del entorno. Usar
`StdioServerParameters` personalizados queda reservado a comandos locales de confianza.

Para un host MCP externo local, configurar comando `uv`, argumentos
`["run", "--locked", "python", "-m", "evidenceops.mcp_server"]` y directorio de trabajo
igual a la raíz del repo. El servidor funciona por stdin/stdout hasta EOF; no es
un comando que imprima una demo y termine. Reservar stdout al protocolo; cualquier
diagnóstico debe ir a stderr. Sin puerto, autenticación ni despliegue remoto.

## Validación

```bash
uv run --locked pytest tests/test_mcp.py tests/test_tools.py tests/test_agent.py
uv run --locked pytest tests/test_mcp_integration.py
uv run --locked pytest
```

La integración requiere `evidenceops_test` según el README; usa servicios reales,
stdio y pgvector con encoder/modelo deterministas. Compara resultados MCP/directos,
lee el abstract, conserva datos y limpia filas de prueba. Los tests sin DB verifican
catálogo, ambas herramientas, errores, timeout de transporte, correlación,
presupuestos y citas. Ningún test hace inferencias reales ni descargas.
