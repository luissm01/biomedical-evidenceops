# EvidenceOps

Proyecto de AI Engineering aplicado a evidencia biomédica pública.
[Visión](docs/PROJECT_CONTEXT.md) · [Estado y próximo paso](docs/CURRENT_STATE.md) ·
[Mapa documental](docs/README.md) · [Instrucciones para agentes](AGENTS.md).

## Requisitos e instalación

- Python compatible con [pyproject.toml](pyproject.toml); versión local en [.python-version](.python-version).
- uv instalado.
- Docker con Docker Compose para ejecutar PostgreSQL localmente.

Desde la raíz del proyecto:

```bash
uv sync --locked --dev
```

Este comando prepara `.venv/` con las dependencias de ejecución y desarrollo
registradas en `uv.lock`. No es necesario activar el entorno para usar `uv run`.

Si aún no tienes `.env`, créalo a partir del ejemplo (no sobrescribas uno existente):

```bash
cp .env.example .env
```

Configura personalmente `EVIDENCEOPS_GEMINI_API_KEY` antes de arrancar la API.
Los nombres y valores iniciales están en [.env.example](.env.example); las
variables de entorno prevalecen sobre `.env`. Después:

```bash
docker compose up -d --wait postgres
uv run alembic upgrade head
```

El contenedor crea dos bases: `evidenceops` para desarrollo y
`evidenceops_test` para las pruebas. Las credenciales del ejemplo son únicamente
locales. Los archivos `.env` reales no se versionan.

## Ejecutar la API

```bash
uv run uvicorn evidenceops.main:app --reload
```

La API escucha en `http://127.0.0.1:8000`. `--reload` permite recargar los cambios
durante el desarrollo. Detén el servidor con `Ctrl+C`.

Desde otra terminal:

```bash
curl -i http://127.0.0.1:8000/health
```

Respuesta esperada: `200 OK`, contenido JSON y cuerpo `{"status":"ok"}`.
Este endpoint comprueba que la aplicación responde; no verifica servicios externos.

## Registrar y consultar preguntas

```bash
curl -i http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"text": "¿Qué evidencia existe sobre la intervención X?"}'
```

Devuelve `201 Created`, un JSON con `id` (UUID generado por el servidor) y `text`,
y una cabecera `Location` con la ruta de consulta. Copia el identificador recibido:

```bash
curl -i http://127.0.0.1:8000/questions/ID_DEVUELTO
```

- `200 OK`: devuelve la pregunta registrada.
- `404 Not Found`: el UUID es válido, pero no existe una pregunta con ese ID.
- `422 Unprocessable Entity`: el cuerpo o el identificador no cumplen el contrato.

`text` debe ser una cadena de entre 1 y 2.000 caracteres después de quitar los
espacios de los extremos. Se rechazan campos adicionales, incluido un `id`
enviado por el cliente. Cada POST válido crea un registro nuevo, aunque repita
el texto. El endpoint registra preguntas; todavía no busca evidencia ni genera
respuestas. El contrato interactivo está disponible en `http://127.0.0.1:8000/docs`.

Las preguntas se almacenan en PostgreSQL y sobreviven al reinicio de la
aplicación. Alembic mantiene el esquema de la base de datos; una aplicación nueva
debe ejecutar `uv run alembic upgrade head` antes de atender peticiones.

## Generar una respuesta

Con el UUID de una pregunta registrada, sin body:

```http
POST /questions/{question_id}/generate
```

Devuelve `200 OK`:

```json
{
  "answer": "Generated biomedical answer.",
  "limitations": ["Relevant limitation."],
  "external_sources_consulted": false
}
```

Una pregunta inexistente devuelve `404`; un UUID inválido, `422`. Ninguno
invoca al generador. La respuesta no se persiste y repetir la operación puede
producir otra respuesta. No se han consultado fuentes biomédicas externas.


## Operar la generación

La API usa Gemini por defecto; selecciona DeepSeek con
`EVIDENCEOPS_LLM_PROVIDER=deepseek` y `EVIDENCEOPS_DEEPSEEK_API_KEY`.
Modelo por defecto: `deepseek-flash`; ajusta modelo, tokens y timeout con las
variables `EVIDENCEOPS_DEEPSEEK_*` de [.env.example](.env.example). La API
requiere la clave del proveedor elegido salvo que se inyecte un generador, como hacen
los tests. No hay inferencia al importar ni al arrancar; startup comprueba
PostgreSQL, pero no la validez remota de la clave. No publiques `.env` ni claves.

El script manual existente llama exclusivamente a Gemini y consume cuota:

```bash
uv run --locked python test_gemini.py
```

Ese script usa `Settings`: exige la URL de PostgreSQL aunque no conecte a la DB.
El runner de [evaluation](evaluation/README.md) usa `GenerationSettings` y no la exige.
La respuesta tiene validación estructural, no garantía de veracidad biomédica.

Errores HTTP: timeout → 504; cuota → 429; autenticación/indisponibilidad del
proveedor → 503; salida inválida u otro fallo de generación → 502. Los mensajes
públicos son fijos y seguros; contrato exacto en OpenAPI y tests de generación.
Gemini conserva el retry del SDK documentado en [D011](docs/decisions/D011-gemini.md);
DeepSeek hace una petición sin retry propio. Ambos usan timeout de transporte
sin deadline total.
Flujo y recursos en [arquitectura](docs/ARCHITECTURE.md).

## Diagnóstico y evaluación

- [Observabilidad](docs/subsystems/observability.md): eventos JSON, X-Request-ID,
  `GET /metrics`, diagnóstico y límites; estado de entrega en el plan M5.
- [Evaluación](evaluation/README.md): dataset, runs, promoción, revisión humana
  y comparación. Un baseline de outputs no certifica calidad biomédica.

Evaluación RAG end-to-end (#47): [casos para revisión previa](evaluation/rag/CASES-v1.md)
y [runner, rúbrica y baseline](evaluation/rag/README.md).
[Baseline RAG v1](evaluation/rag/REPORT-v1.md) real revisado y promocionado
con 58 pass, 0 fail y 2 N/A y límites de muestra y revisión asistida.

## Ingestión PubMed (M6)

`PubMedClient` en [pubmed.py](src/evidenceops/pubmed.py) usa ESearch para obtener
PMIDs desde una query con `limit` obligatorio (1–100) y EFetch XML para adquirir
PMIDs explícitos en lotes de hasta 200. `fetch(pmids)` devuelve documentos
`BiomedicalDocument` y errores de registros individuales; un fallo HTTP, timeout
o respuesta XML inválida lanza `PubMedError` y puede invalidar el lote completo.
El cliente PubMed no persiste ni se conecta con la generación.

La persistencia de #30 está en [publications.py](src/evidenceops/publications.py):
`upsert_publication(session, document, candidate_id=...)` ejecuta una sola sentencia PostgreSQL
y deja el commit o rollback al llamador. Aplica las migraciones con
`uv run alembic upgrade head` antes de usarla. `as_biomedical_document` copia
una fila al contrato normalizado. La CLI compone cliente y PostgreSQL sobre
[ingest_pubmed](src/evidenceops/ingestion.py), reutilizable sin HTTP.

Con `.env`, PostgreSQL y las migraciones preparados:

```bash
uv run --locked evidenceops ingest --pmid 12345 67890
uv run --locked evidenceops ingest --pmid 12345 --pmid 67890
uv run --locked evidenceops ingest --query 'asthma[Title]' --limit 5
```

Estos comandos **sí consultan PubMed**; son instrucciones operativas, no tests.
No requieren claves LLM ni arrancar la API. `--pmid` y `--query` son excluyentes;
`--limit` es obligatorio para query (1–100) y no se admite con PMIDs. Los PMIDs
son cadenas decimales no vacías. ESearch puede devolver menos resultados o ninguno;
la query no es un snapshot reproducible. Usa PMIDs explícitos para repetir las
identidades; PubMed puede actualizar su metadata.

El servicio deduplica antes de adquirir, coordina lotes de hasta 200 y abre una
transacción por documento después de recibir y normalizar el lote. Una caída
externa marca todos sus PMIDs como fallidos y permite continuar otros lotes.
Un error de persistencia revierte ese documento y permite continuar los demás.
No hay retries automáticos ni rollback global de documentos ya confirmados.

La última línea de stdout es un resumen JSON con `created`, `updated`, `omitted`,
`failed`, `requested` (entradas, incluidos duplicados), `unique`, `batches`,
`unidentified_invalid`, `failures` (PMID cuando se conoce y causa segura),
`run_id`, `source` y `duration_ms`. Antes se emiten eventos JSON de inicio/fin.

- `created`: inserción confirmada con el UUID candidato de la escritura.
- `updated`: escritura confirmada que devuelve el UUID existente, incluso si la
  metadata no cambia. No hay consulta previa ni pérdida de atomicidad.
- `omitted`: ocurrencias repetidas de un PMID en esta ejecución, procesado una vez.
- `failed`: registros inválidos/ausentes, afectados por fallo del lote o persistencia.
  Un registro cuyo PMID no se puede identificar añade un fallo y aumenta
  `unidentified_invalid`; no se adivina qué PMID solicitado representa. Puede
  contarse tanto ese registro como los PMIDs ausentes de la respuesta.
  Si ESearch falla, cuenta una operación fallida sin PMID; `requested` queda en 0.

Exit code: **0** sin fallos (también búsqueda vacía), **1** con fallos o error
de configuración y **2** con argumentos inválidos. Errores de preparación
emiten diagnóstico JSON seguro a stderr. La duración cubre búsqueda, espera
NCBI, adquisición, parsing y commits. Política en
[D023](docs/decisions/D023-biomedical-ingestion-pipeline.md).

`PubMedSettings` no requiere base de datos. Sus variables opcionales están en
[.env.example](.env.example): clave API, email de contacto, nombre de herramienta
y timeout. La clave permite un límite por instancia de 10 peticiones/s; sin ella,
3 peticiones/s. Cada proceso o cliente independiente comparte el límite de la IP
ante NCBI y debe coordinarse si se ejecuta en paralelo. NCBI recomienda registrar
`tool` y `email` antes de usos sostenidos; configurar los parámetros no equivale
a registrarlos. No hay retries automáticos ni llamadas reales en tests. Los
abstracts pueden tener condiciones de copyright; respeta las condiciones de
uso de NCBI y del contenido. [Reglas de E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/).

## Pruebas y CI

La suite completa usa PostgreSQL local; las fixtures exigen `evidenceops_test`,
aplican migraciones y limpian los datos afectados antes/después de cada test.
Configura `EVIDENCEOPS_TEST_DATABASE_URL` según el ejemplo.

```bash
docker compose up -d --wait postgres
uv run --locked pytest
```

Las pruebas usan fakes y transporte simulado: no requieren API key ni hacen
inferencias reales. Para trabajar solo en evaluación, sin PostgreSQL:

```bash
uv run --locked pytest tests/test_evaluation.py tests/test_evaluation_dataset.py tests/test_evaluation_review.py
```

[CI](.github/workflows/ci.yml) define comandos y servicios exactos para pushes/PRs;
no despliega. `--locked` exige coherencia del lock sin modificarlo. Distingue errores
de preparación del entorno, assertions fallidas y warnings. Limitaciones vigentes
en [estado](docs/CURRENT_STATE.md); no se mantiene aquí un contador de tests.

## Navegación del código

[src/evidenceops](src/evidenceops): aplicación; [tests](tests): comportamiento
verificado; [migrations](migrations): esquema; [compose.yaml](compose.yaml):
servicios locales; [evaluation](evaluation): dataset y runbook.
El mapa de responsabilidades está en [arquitectura](docs/ARCHITECTURE.md),
los motivos en [ADRs](docs/decisions/README.md) y la dirección en el
[roadmap](docs/ROADMAP.md).

## Embeddings y retrieval local (M7 / #39)

PostgreSQL debe incluir pgvector; Compose y CI usan la imagen oficial
`pgvector/pgvector:0.8.7-pg18-trixie`. La migración
`20261006_01` instala `vector` (requiere permisos para crear la extensión) y
crea `unit_embeddings` con `vector(768)`. Conserva el volumen existente de
PostgreSQL 18 al recrear el servicio; no borres volúmenes para actualizarlo.

```bash
docker compose up -d --wait postgres
uv run --locked alembic upgrade head
```

[index_publication](src/evidenceops/retrieval.py) recibe una factory de sesiones,
UUID de publicación y encoder. Indexa una publicación ya persistida y confirma
su propia transacción. Devuelve `indexed`, `unchanged` u `omitted` (sin texto).
Mismo ID/fingerprint/configuración y par efectivo título/abstract reutiliza el
vector; contenido diferente lo
sustituye. Si el contenido desaparece elimina su vector. Una publicación que
cambia durante la inferencia aborta la escritura; se puede repetir la operación.
La ingestión no indexa automáticamente.

`search(sessions, encoder, query=..., top_k=..., published_from=...)` devuelve
hasta `top_k` resultados con `unit: RetrievableUnit` y `score` (dot product).
Incluye UUID, PMID, texto, título/abstract, fingerprint, estrategia y procedencia.
Orden descendente; empates por `unit_id`. Año mínimo inclusivo, aplicado antes del
LIMIT; año desconocido no pasa el filtro. Corpus vacío, filtro sin coincidencias
o menos candidatos devuelven respectivamente `[]`, `[]` o los disponibles.
Query vacía, `top_k` no entero positivo (también bool) o año no entero positivo
lanzan `ValueError`. Se valida la query con el encoder incluso con corpus vacío.

La configuración registrada incluye ambos modelos y revisiones, dimensiones,
política de entrada/pooling, límites, normalización, estrategia y métrica.
Incompatibilidad lanza `EmbeddingCompatibilityError`; no se mezclan espacios
por compartir dimensiones. `replace_incompatible=True` en la indexación autoriza
regenerar esa publicación; completa todas las filas incompatibles antes de buscar.
Los vectores obsoletos por cambios de título/abstract se excluyen de búsqueda
antes del ranking, aunque no se haya vuelto a indexar. La metadata devuelta y el
año del filtro son los actuales de `Publication`.

### Demo manual con MedCPT real

Los tests/CI solo instalan dependencias normales y usan dobles. El extra
`medcpt` incorpora PyTorch CPU (Linux/Windows) y Transformers; el adapter carga
cada encoder al primer uso. No necesitas claves LLM, API ni endpoint de retrieval.
Con algunas publicaciones públicas ya ingeridas (por ejemplo, siguiendo M6):

```bash
uv sync --locked --dev --extra medcpt
uv run --locked --extra medcpt python -m evidenceops.retrieval_demo \
  --query 'diabetes treatment' --index-limit 5 --top-k 3 --published-from 2020
```

La primera ejecución descarga los dos encoders de Hugging Face a su caché;
requiere red, espacio y memoria local. Las siguientes reutilizan las revisiones
fijadas y los vectores compatibles. `--index-limit` limita publicaciones a indexar,
no el corpus consultado: la búsqueda incluye todas las filas indexadas compatibles.
Emite estado por publicación y resultados JSON. No adquiere documentos nuevos.
Se prepara esta prueba, sin ejecutarla como parte de la implementación.

MedCPT codifica título/abstract como par y toma CLS sin normalizar; queries como
texto simple. Límites: 512 tokens para artículo y 64 para query, incluidos tokens
especiales. El tokenizer aplica `truncation=True` y el `max_length` correspondiente
solo a la entrada efectiva del encoder; la unidad y su procedencia conservan el
texto completo. Esta política de truncamiento y los límites forman parte de la
configuración persistida. Referencias oficiales:
[Article Encoder](https://huggingface.co/ncbi/MedCPT-Article-Encoder) y
[Query Encoder](https://huggingface.co/ncbi/MedCPT-Query-Encoder).
Ranking exacto de pgvector, sin índice aproximado ni umbral de score. Un score
mayor ordena antes; no representa probabilidad ni calidad biomédica.
La evaluación end-to-end de #40 y su baseline real se describen en
[evaluation/retrieval](evaluation/retrieval/README.md), con juicios asistidos
y límites explícitos del corpus.

## RAG v1 (M8 — #45)

Servicio local independiente de HTTP, sin persistencia de respuestas. Reutiliza
la búsqueda M7 y el generador configurado; el llamador posee y cierra sus recursos:

```python
from functools import partial
from evidenceops.rag import RagService
from evidenceops.retrieval import search

# sessions, encoder y generator ya compuestos con la configuración existente.
rag = RagService(partial(search, sessions, encoder), generator)
response = rag.generate("¿Qué evidencia hay sobre X?", published_from=2020)
# response.answer, response.limitations, response.sources
```

`published_from` es opcional; top-5 es fijo. El contexto incluye fuentes completas
hasta 20.000 caracteres del JSON compacto de evidencia; omite las que no caben y
continúa sin truncar ni buscar candidatos adicionales. `sources` conserva la
unidad completa y score de todas las fuentes incluidas, citadas o no; las citas
inline usan sus etiquetas locales `[S1]`, `[S2]`, etc. El score no mide confianza.

La aplicación valida citas existentes y cobertura al final de cada párrafo o
elemento de lista de `answer` y `limitations`. Solo permite sin citas la abstención
fija acordada. Sin resultados o si ninguna fuente cabe, no llama al LLM. Errores
de citas producen `GenerationError` con causa `INVALID_OUTPUT`, sin retries ni
sustitución por abstención. Los fallos de retrieval se clasifican con causas seguras;
los de generación conservan la frontera existente.
No valida apoyo semántico. El presupuesto en caracteres no garantiza caber en la
ventana de tokens del proveedor. Detalles en [D026](docs/decisions/D026-rag-v1-contract-context-and-citations.md).

Pruebas del servicio y de compatibilidad de instrucciones por llamada, sin DB ni
modelos reales (los dos casos HTTP/DB de Gemini se excluyen en este comando):

```bash
uv run --locked pytest tests/test_rag.py tests/test_generation_contract.py tests/test_gemini_adapter.py tests/test_deepseek_adapter.py -k 'not http_database_and_real_adapter_flow'
```

## RAG desde la API (M8 / #46)

`POST /rag` ejecuta el servicio anterior sin registrar una pregunta ni persistir
la respuesta. Requiere PostgreSQL con pgvector, publicaciones previamente
[ingeridas e indexadas](#embeddings-y-retrieval-local-m7--39), el extra `medcpt`
y la clave del proveedor elegido en `.env` (`EVIDENCEOPS_LLM_PROVIDER=deepseek`
o `gemini`, junto a su correspondiente API key). No indexa automáticamente.

Entrada JSON: `query` obligatoria, texto de 1–2000 caracteres tras eliminar
espacios exteriores; `published_from` opcional/null, entero positivo estricto,
filtro inclusivo. No admite campos adicionales ni selección de top-k.

```bash
uv run --locked --extra medcpt uvicorn evidenceops.main:app --no-access-log
```

En otra terminal, esta llamada ejecuta MedCPT y el proveedor real si hay fuentes
utilizables; puede consumir cuota:

```bash
curl -sS -i -X POST http://127.0.0.1:8000/rag \
  -H 'Content-Type: application/json' \
  -d '{"query":"association between childhood obesity and asthma risk","published_from":2020}'
```

Respuesta 200: `{"answer":"… [S1].","limitations":[],"sources":[…]}`.
Cada fuente es `{"citation_id":"S1","unit":{…},"score":0.75}`: `unit`
contiene identidad, UUID de publicación, estrategia, índice, fingerprint,
source/source_id, título, abstract, texto íntegro, autores, revista, DOI, año y URL
según el [contrato de unidad](src/evidenceops/chunking.py). `score` es producto
interno, no confianza. Los valores anteriores son ilustrativos; la API devuelve
metadata real. OpenAPI con todos los campos está disponible en `/docs`.
No añade `status`, `confidence` ni `external_sources_consulted`.

La abstención devuelve 200 con la frase fija de D026 y una limitación operativa.
Si no hay fuentes o ninguna cabe, `sources=[]` y no se invoca el LLM. Si el modelo
se abstiene, se conservan las fuentes que recibió.

| Caso | HTTP | `detail.code` |
| --- | --- | --- |
| Entrada inválida | 422 | Validación estándar FastAPI |
| Fallo de BD durante retrieval | 503 | `database_unavailable` |
| Corpus/configuración incompatible | 503 | `retrieval_incompatible` |
| Encoder/retrieval no disponible | 503 | `retrieval_unavailable` |
| Timeout LLM | 504 | `generation_timeout` |
| Cuota/rate limit LLM | 429 | `generation_rate_limited` |
| Autenticación o indisponibilidad LLM | 503 | `generation_unavailable` |
| JSON/esquema de salida LLM inválido | 502 | `invalid_generation` |
| Citas/cobertura/abstención inválidas | 502 | `invalid_citations` |
| Otro fallo clasificado del proveedor | 502 | `generation_failed` |
| Error inesperado | 500 | Respuesta estándar del servidor |

Los errores controlados usan `{"detail":{"code":"…","message":"…"}}` con
mensajes seguros, sin texto original de excepciones. Todas las respuestas llevan
`X-Request-ID`. Sin retries RAG ni reparación de citas.

Para la demostración end-to-end con logs, métricas y trazas, sustituir el arranque
anterior por:

```bash
EVIDENCEOPS_TRACE_CONSOLE=true uv run --locked --extra medcpt uvicorn evidenceops.main:app --no-access-log \
  > /tmp/evidenceops-rag-events.jsonl 2> /tmp/evidenceops-rag-traces.jsonl
```

Ejecutar el mismo curl, copiar su `X-Request-ID` y buscarlo en los eventos.
Comprobar la relación HTTP → RAG → etapas → proveedor por `trace_id`/`parent_id`
y consultar los agregados:

```bash
rg 'rag|llm.generation.started' /tmp/evidenceops-rag-events.jsonl
rg 'rag|llm.deepseek|llm.gemini|evidenceops.outcome' /tmp/evidenceops-rag-traces.jsonl
curl -sS http://127.0.0.1:8000/metrics | rg 'evidenceops_rag_|evidenceops_llm_'
```

Se esperan retrieval, contexto y generación cuando hay evidencia utilizable;
sin ella no hay etapa ni span de generación ni proveedor. Una salida inválida se
rechaza con 502 aunque el adapter haya completado correctamente su llamada.
No demuestra groundedness ni calidad semántica: corresponden a #47.
El primer acceso puede cargar/descargar los pesos de MedCPT y tardar más.
Métricas y causas en [observabilidad](docs/subsystems/observability.md#rag-end-to-end-m8--46);
decisiones en [D027](docs/decisions/D027-rag-http-errors-and-observability.md).

Pruebas nuevas sin modelos ni red externa (la segunda requiere PostgreSQL de pruebas):

```bash
uv run --locked pytest tests/test_rag_api.py tests/test_rag.py -q
uv run --locked pytest tests/test_rag_integration.py -q
```


Si DeepSeek termina correctamente pero la API devuelve `502 invalid_citations`,
consultar el [diagnóstico seguro por motivo y localización](docs/subsystems/observability.md#diagnosticar-502-invalid_citations-sin-registrar-contenido).
Los eventos nuevos distinguen referencias desconocidas, corchetes/formato,
cobertura y abstención inválida sin registrar contenido. El contrato HTTP no
incluye esos detalles de desarrollo.

## Retrieval híbrido (M9.1)

`search(..., mode="hybrid")` fusiona candidatos MedCPT y BM25 con RRF (`k=60`).
El modo omitido o `mode="semantic"` conserva el ranking semántico y sus scores.
Para RAG, configura `EVIDENCEOPS_RETRIEVAL_MODE=hybrid` antes de arrancar la API;
por defecto sigue en `semantic`. La demo local admite `--mode hybrid`.

BM25 tokeniza título y abstract completos mediante casefold y términos
alfanuméricos Unicode; no aplica stemming ni stopwords. Usa las mismas unidades
indexadas vigentes y filtros temporales que MedCPT. Lee el corpus elegible en
memoria en cada consulta: adecuado para el corpus pequeño actual. Los 50
candidatos por rama por defecto no limitan esa lectura. El score híbrido es RRF,
no dot product. [Decisión, fórmula y límites](docs/decisions/D030-hybrid-retrieval.md).
[Comandos de evaluación y comparación](evaluation/retrieval/README.md#comparar-semántico-e-híbrido-m91).
