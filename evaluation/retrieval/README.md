# Evaluación de retrieval M7 / #40

Evaluación local de `query → Query Encoder → pgvector → top-5`, independiente
del generador de M4. El [informe](REPORT-v1.md) muestra corpus, relevancias,
resultados y errores. El desarrollador acepta el cierre de #40 el 15 de octubre
de 2026. Las anotaciones son asistidas por Codex; esta aceptación no acredita
una revisión humana de cada etiqueta ni un benchmark clínico o biomédico general.

## Artefactos y construcción

- [corpus-v1.json](corpus-v1.json): 50 publicaciones, 10 por área. Snapshot de
  título, abstract y bibliografía normalizados por el parser M6, con PMID y URL.
  `discovery` conserva las 20 búsquedas ESearch exactas, orden, candidatos y
  seleccionados. Se adquirieron mediante E-utilities el 6 de octubre de 2026.
- [queries-v1.json](queries-v1.json): las 10 queries acordadas, criterios por
  query, relevantes con justificación y casos ambiguos excluidos de positivos.
  La unidad juzgada es **publicación identificada por PMID**.
- [freeze-v1.json](freeze-v1.json): PMIDs, hashes SHA-256 de los bytes de corpus
  y dataset y hora de congelación anterior a MedCPT.
- [baseline-v1.json](baseline-v1.json): ejecución real completa, configuración,
  hashes, entorno, top-5 y ranking completo por query, métricas individuales
  y medias. Es una referencia inicial con los límites descritos en el informe.

La selección reserva 3 publicaciones para cada tema de query y 2 para cada uno
de dos temas vecinos por área. Las búsquedas limitan inglés, abstract disponible
y fecha de publicación 2000–2024. Se toma el primer registro distinto con
abstract en el orden de relevancia de ESearch hasta completar cada cuota.
La excepción documentada es genética de asma grave: se eligió una revisión,
un GWAS de asma moderada-grave y una asociación genética en sensibilización
fúngica tras detectar que la búsqueda inicial solo ofrecía alusiones genéticas
vagas. El refinamiento se hizo antes de congelar los juicios, sin MedCPT.

El corpus incluye revisiones, ensayos, guías, asociaciones y distractores
plausibles. Los estratos son de selección, no clases de relevancia: se valoran
los 50 documentos frente a cada query, también los seleccionados en otro tema.
El orden de PubMed puede cambiar: **reproducir el baseline usa el snapshot
versionado, nunca vuelve a ejecutar ESearch**. Los PMIDs permiten volver a
adquirir fuentes, pero cambios posteriores de PubMed no sustituyen los textos
congelados. El parser M6 normaliza whitespace y conserva etiquetas de secciones
del abstract; no se usa el texto completo de los artículos.

## Juicios y métricas

Los juicios se redactaron usando solo título/abstract, antes de ejecutar el
retriever. No se llama a un LLM evaluador ni se puntúan respuestas generadas.
Se consideran los 500 pares query-publicación contra el criterio de cada query:
la lista `relevant` define etiqueta 1; el resto tiene etiqueta operacional 0.
Los casos ambiguos quedan explícitos en `ambiguous`, con motivo, y reciben 0
para el cálculo conservador. Este cero **no demuestra irrelevancia biomédica
universal**. La cobertura es exhaustiva dentro de este corpus pequeño según
estas anotaciones; no cubre PubMed ni equivale a acuerdo entre expertos.

Para `K=5`, por query:

| Métrica | Cálculo | Qué informa |
| --- | --- | --- |
| Hit Rate@5 | 1 si hay al menos un relevante en top-5; 0 en otro caso | Queries con algún acierto |
| Recall@5 | Relevantes en top-5 / todos los relevantes de la query en este corpus | Cobertura de los positivos anotados |
| Precision@5 | Relevantes en top-5 / 5 | Pureza de los cinco puestos solicitados |
| Reciprocal rank | 1 / puesto del primer relevante; 0 si no aparece | Posición del primer acierto |
| MRR | Media del reciprocal rank de las queries | Rapidez del primer acierto |

MRR usa el **ranking completo de 50**, no MRR@5. El runner ejecuta `search` con
`top_k=5`, y obtiene además el ranking completo para diagnóstico y MRR, reutilizando
el mismo embedding de query y comprobando que el prefijo coincide con top-5.
No modifica el orden ni aplica un segundo retriever.

Las medias son macro: cada query pesa igual. Una query sin positivos tiene
recall indefinido (`null`) y se excluye solo de la media de recall; Hit Rate,
Precision y reciprocal rank valen cero y se incluyen. Se informa del número
de queries y de queries con positivos. No hay queries sin positivos en v1.
Un ranking corto mantiene denominador 5 para Precision. Rankings con PMIDs
duplicados se rechazan para evitar contar chunks repetidos como aciertos.
No se implementa NDCG con etiquetas binarias.

## Ejecutar y reproducir

Requiere PostgreSQL con la extensión `vector` instalada por las migraciones
del proyecto y permiso para crear un esquema. Usa `EVIDENCEOPS_DATABASE_URL`
de `Settings` (entorno o `.env`), sin claves LLM. Preparación de DB y dependencias
en el [README principal](../../README.md#embeddings-y-retrieval-local-m7--39).

```bash
uv sync --locked --dev --extra medcpt
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 uv run --locked --extra medcpt \
  python -m evidenceops.retrieval_evaluation --live \
  --output evaluation/runs/retrieval-candidate.json
```

`--dataset-dir` permite seleccionar otro directorio con sus tres archivos de
entrada. El runner exige hashes congelados y coherencia entre corpus y juicios
antes de inferir. `--live` explicita la descarga/carga de pesos e inferencia local;
no consume cuota de un proveedor LLM. El destino debe ser nuevo: no sobrescribe
ningún run, ni siquiera uno fallido.

Cada ejecución crea un esquema aleatorio aislado, copia únicamente las 50
publicaciones, llama a `index_publication` y `search` de #39 y elimina **solo ese
esquema** al terminar, incluso ante fallo ordinario. No usa el corpus de desarrollo
ni modifica sus tablas. Un cierre abrupto del proceso puede dejar un esquema
`retrieval_eval_*`; inspecciona cuál pertenece a ese run antes de eliminarlo.

El archivo registra revisiones fijadas de ambos encoders/tokenizers, estrategia,
768 dimensiones, par título/abstract, CLS, sin normalización, dot product,
límites/truncamiento, K, ausencia de filtro temporal, desempate y profundidad
MRR. Incluye versiones de paquetes/PostgreSQL/pgvector, CPU, dtype e hilos,
commit, estado dirty y hashes de los módulos fuente. El árbol estaba dirty:
los hashes identifican código local, pero el commit por sí solo no lo reconstruye;
conserva los archivos revisados junto al baseline. La caché de Hugging Face puede
reutilizar los pesos fijados. No se promete identidad de scores bit a bit entre
hardware o versiones distintas; un cambio de ranking sí debe inspeccionarse.

Checkpoint después de cada query. Un fallo queda `status: failed`, con tipo de
error seguro y los resultados disponibles, sin agregado de un run incompleto.
No lo uses como baseline completo. El CLI devuelve fallo si la operación falla.

## Validar y comparar después

```bash
uv run --locked pytest tests/test_retrieval_evaluation.py
```

Los tests usan rankings conocidos y dobles del encoder. Los tests del runner
requieren la DB de pruebas según el README; nunca descargan modelos ni infieren.
El test del artefacto verifica hashes y recalcula métricas del baseline guardado
sin red, DB ni modelos. Las pruebas del mecanismo no acreditan calidad IA.

Para una comparación posterior usa corpus y juicios con los mismos hashes,
K=5, filtro y definición de métricas. Alinea `results` por `query_id`, compara
métricas por query, positivos que entran/salen del top-5 y sus puestos en el
ranking completo, además de las medias. Totales iguales pueden ocultar cambios
entre queries. Conserva diferencias de configuración y scores como contexto;
los scores de sistemas distintos no son probabilidades comparables. Si la
revisión cambia los juicios, crea una nueva versión y recalcula **ambos** runs
contra ella: no reescribas v1 ni optimices etiquetas mirando el ranking.

No hay RAG, generación, LLM-as-a-judge ni estrategias de M8/M9.
