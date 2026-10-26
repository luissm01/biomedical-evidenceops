# D030 — Retrieval híbrido BM25 + MedCPT (M9.1)

Estado: aceptada; implementación y experimento M9.1 completados, integración mediante PR pendiente.

## Problema y decisión

MedCPT sigue disponible y es el modo por defecto. M9.1 añade coincidencias
léxicas mediante BM25 real en Python, sin servicios ni dependencias nuevas.
El selector `search(..., mode="semantic" | "hybrid")` conserva el contrato
`RetrievalResult(unit, score)`. La API RAG elige modo al arrancar mediante
`EVIDENCEOPS_RETRIEVAL_MODE`; no cambia prompts ni lógica de generación.
La demo y el runner de retrieval ofrecen `--mode`.

BM25 aplica sobre el texto completo de cada unidad (título + abstract):
`casefold` y secuencias alfanuméricas Unicode; puntuación, guiones y underscore
separan términos. Conserva números y acentos; no hace stemming, stopwords,
sinónimos ni expansión biomédica. Cada término de query cuenta una vez, con
orden de suma estable. Se usa `k1=1.2`, `b=0.75`,
`idf(t)=ln(1+(N-df(t)+0.5)/(df(t)+0.5))` y contribución
`idf(t)*tf(t)*(k1+1)/(tf(t)+k1*(1-b+b*len/avglen))`.
Referencia de la [fórmula BM25 de Elastic](https://www.elastic.co/blog/practical-bm25-part-3-considerations-for-picking-b-and-k1-in-elasticsearch).
Solo scores positivos producen candidatos léxicos: una query sin tokens o sin
coincidencias deja únicamente la rama semántica.

Las dos ramas usan las mismas filas indexadas compatibles y vigentes, con filtro
inclusivo por año antes del ranking; años desconocidos quedan fuera al filtrar.
No incluye publicaciones sin embedding ni snapshots obsoletos. Un corpus mixto
incompatible sigue fallando aunque el filtro temporal lo excluya. Se obtiene un
snapshot con una única consulta SQL para ambas ramas; BM25 calcula estadísticas
sobre ese corpus elegible, por lo que cambiar filtros también cambia sus scores.
La metadata se obtiene de la publicación actual. Se mantiene la protección de
identidad, fingerprint y texto; en híbrido se valida todo el corpus elegible.

Se toman `max(top_k, candidate_k)` candidatos por rama (`candidate_k=50` por
defecto), ordenados por score descendente y `unit_id` ascendente. RRF suma
`1/(60+rank)` con rank desde 1; una unidad ausente aporta cero, una duplicada
contribuye una vez por rama. Deduplicación por `RetrievableUnit.unit_id` y
empates finales por ese ID ascendente. No se mezclan escalas de scores.
Referencia de [RRF](https://doris.apache.org/docs/4.x/key-features/reciprocal-rank-fusion/).
El score híbrido representa fusión de posiciones, no similitud MedCPT ni
probabilidad de relevancia. Cambiar `top_k` por encima de la profundidad elegida
amplía candidatos y puede cambiar el prefijo: para comparar rankings, fijar una
profundidad común suficiente.

## Alternativas y consecuencias

Un motor externo o extensión especializada de PostgreSQL añadiría operación y
acoplamiento sin necesidad medida. Una suma de scores exigiría calibrar escalas.
Una librería BM25 es válida, pero la fórmula pequeña y probada evita otra
dependencia y deja explícita su variante de IDF.

Se reconstruyen frecuencias BM25 por consulta, sin caché que invalidar. Se leen
todas las unidades elegibles y sus scores semánticos; memoria proporcional al
texto y vocabulario, más filas ORM, y ordenación del corpus completo en DB.
No es una solución para PubMed completo. El límite de candidatos reduce la
fusión, no la lectura ni el cálculo BM25. El modo híbrido conserva la dependencia
de MedCPT/PostgreSQL; no es fallback frente a caídas del encoder o DB.

La evaluación usa el corpus y juicios congelados M7, las mismas métricas y una
profundidad común igual al corpus para top-5 y MRR completo. Registra modo,
tokenizador, constantes BM25/RRF y profundidad. El comparador offline valida
entradas/configuración de métricas, muestra deltas por query y entradas/salidas
del top-5. No reescribe ni promociona el baseline. Tests con fakes acreditan
mecanismo. El experimento real y su interpretación se documentan en el
[informe M9.1](../../evaluation/retrieval/REPORT-m9.1.md).
Reranking y reformulación quedan fuera de M9.1.


## Resultado del experimento y adopción

Con el corpus M7 (10 queries, 50 publicaciones, top-5), el híbrido obtiene
Recall@5 0.9417 frente a 0.9750 y Precision@5 0.4800 frente a 0.5000;
Hit Rate@5 y MRR permanecen en 1. Solo q07 pierde un positivo del top-5.
La decisión explícita del desarrollador mantiene `semantic` como modo por
defecto y baseline para M9.2; `hybrid` queda como alternativa experimental.
No se ajustan BM25/RRF al dataset ni se introducen más cambios de retrieval
en M9.1. La inferioridad observada es de esta configuración en este experimento
limitado, no una conclusión general sobre búsqueda híbrida. Los runs, deltas,
configuraciones y límites se conservan en el informe, sin sustituir el baseline M7.
