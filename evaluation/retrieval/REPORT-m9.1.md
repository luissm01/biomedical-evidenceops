# M9.1 — Experimento de Hybrid Retrieval

Experimento completado el 26 de octubre de 2026. Resultados aportados por el
desarrollador y contrastados mediante cálculo offline sobre los dos runs completos
conservados, sin repetir inferencias. M9.1 queda completada en implementación y
evaluación; la integración y el cierre de la issue dependen de revisar y fusionar
la PR. Decisión: mantener `semantic` por defecto y `hybrid` como alternativa
experimental seleccionable. No se promueve un nuevo baseline.

## Entradas, configuraciones y trazabilidad

Se reutilizan las 10 consultas, las 50 publicaciones públicas y los juicios
binarios congelados de M7: [corpus](corpus-v1.json), [queries](queries-v1.json) y
[freeze](freeze-v1.json). Una publicación es una `RetrievableUnit`, con título y
abstract completos y estrategia `whole-publication-v1`. No se cambiaron etiquetas,
criterios, textos ni filtros después de observar los rankings.

| Configuración | Semantic | Hybrid |
| --- | --- | --- |
| Ranking | MedCPT + pgvector exacto, dot product | MedCPT exacto + BM25, fusión RRF |
| Query / Article Encoder | MedCPT Query / Article, 768 dimensiones | Los mismos |
| Representación MedCPT | Par título/abstract, CLS, sin normalización | La misma |
| Límites MedCPT | Query 64 / artículo 512 tokens, truncate-longest-first | Los mismos |
| Filtro temporal | Ninguno (`published_from=null`) | Ninguno |
| Corte de evaluación | `top_k=5` | `top_k=5` |
| Profundidad MRR | Ranking completo de 50 | Ranking completo de 50 |
| Candidatos por rama | Corpus completo de 50 | Hasta 50 por rama, fijos para top-5 y MRR |
| BM25 | No aplica | `k1=1.2`, `b=0.75`, IDF positivo log1p |
| Tokenización BM25 | No aplica | Casefold + secuencias alfanuméricas Unicode; términos únicos de query |
| Fusión | No aplica | RRF `k=60`, rangos desde 1, igual contribución por rama |
| Empates | `unit_id` ascendente | `unit_id` ascendente en cada ranking y en la fusión |

BM25 calcula estadísticas sobre el corpus elegible completo y solo aporta
coincidencias con score positivo. No aplica stemming, stopwords ni sinónimos.
RRF deduplica por `unit_id`. Los scores MedCPT y RRF tienen escalas diferentes;
no se comparan directamente como relevancia o probabilidad.
[Contrato y decisiones](../../docs/decisions/D030-hybrid-retrieval.md).

Las revisiones fijadas son Query Encoder
`d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc` y Article Encoder
`d05a736da4bb84ee4057b7f7999485be6ed85465`. Los runs registran Python 3.14.4,
PyTorch 2.14.1+cpu, Transformers 4.57.6, PostgreSQL 18.6 y pgvector 0.8.7;
CPU, float32 y seis hilos intra/inter-op. La configuración completa, entorno,
fechas UTC, hashes de entradas y fuentes están en los JSON, que se conservan sin
reescribir su metadata:

- [semantic.json](experiments/m9.1/semantic.json): 09:22:57–09:23:17 UTC.
- [hybrid.json](experiments/m9.1/hybrid.json): 09:23:18–09:23:33 UTC.
- [comparison.json](experiments/m9.1/comparison.json): deltas por query y cambios
  de pertenencia al top-5, calculados sin inferencia.
- [manifest.json](experiments/m9.1/manifest.json): SHA-256 de esos tres artefactos
  y del baseline original, para comprobar integridad.

Ambos runs identifican el commit base `1ee065e1cc274f5568519fe0be1c29c8a5ab6491`
y un árbol dirty: el commit base por sí solo no contiene M9.1. Los hashes de
fuentes de ambos runs coinciden entre sí y con el código de esta entrega.
Los JSON originales de `evaluation/runs/` se copiaron byte a byte a la ruta
versionada. No se volvió a ejecutar ni sobrescribir el [baseline M7](baseline-v1.json).
El run semántico nuevo mantiene las métricas y el orden completo de PMIDs de M7;
no se exige igualdad bit a bit de los scores entre entornos.

## Resultados

Métricas macro sobre las diez queries; MRR usa el ranking completo, no MRR@5.
Los juicios y denominadores se mantienen según el [método M7](README.md#juicios-y-métricas).
Los JSON conservan precisión completa; las tablas redondean.

| Métrica | Semantic | Hybrid | Delta Hybrid − Semantic |
| --- | --- | --- | --- |
| Hit Rate@5 | 1.0000 | 1.0000 | 0.0000 |
| Recall@5 | 0.9750 | 0.9417 | −0.0333 |
| Precision@5 | 0.5000 | 0.4800 | −0.0200 |
| MRR | 1.0000 | 1.0000 | 0.0000 |

No hay mejoras métricas por query. Solo q07 empeora; las otras nueve mantienen
sus métricas. Hit Rate y reciprocal rank valen 1 en todas las consultas y ambos
modos: mantener el primer relevante no implica conservar todos los relevantes.

| Query | Recall@5 Semantic → Hybrid | Precision@5 Semantic → Hybrid | Sale del top-5 | Entra en top-5 |
| --- | --- | --- | --- | --- |
| q01 | 1.0000 → 1.0000 | 0.40 → 0.40 | — | — |
| q02 | 1.0000 → 1.0000 | 0.60 → 0.60 | 35988550 | 34353454 |
| q03 | 1.0000 → 1.0000 | 0.60 → 0.60 | 36774932 | 24356592 |
| q04 | 1.0000 → 1.0000 | 0.60 → 0.60 | 29627041 | 22000494 |
| q05 | 0.7500 → 0.7500 | 0.60 → 0.60 | — | — |
| q06 | 1.0000 → 1.0000 | 0.20 → 0.20 | — | — |
| q07 | 1.0000 → 0.6667 | 0.60 → 0.40 | 31018251 | 32430550 |
| q08 | 1.0000 → 1.0000 | 0.40 → 0.40 | 29863955, 38924756 | 27184418, 30552067 |
| q09 | 1.0000 → 1.0000 | 0.60 → 0.60 | 33951360, 35263517 | 33650528, 38512301 |
| q10 | 1.0000 → 1.0000 | 0.40 → 0.40 | 35040920 | 35505000 |

Los cambios de pertenencia sin variación métrica ocurren en q02, q03, q04,
q08, q09 y q10. La igualdad de métricas no implica resultados idénticos ni
igual contexto para una futura generación. Los rankings completos conservan
los cambios de orden, incluidos los que no alteran la pertenencia al top-5.

### q07: pérdida de un relevante

Consulta: `effectiveness of immunotherapy in non-small-cell lung cancer`.

| PMID | Juicio q07 | Puesto Semantic | Puesto Hybrid |
| --- | --- | --- | --- |
| 31018251 | Relevante | 2 | 11 |
| 32430550 | No positivo según los juicios congelados | 11 | 5 |

Sale el artículo sobre inhibidores PD-(L)1 frente a quimioterapia y sus
combinaciones en NSCLC (`31018251`); entra *Allergen Immunotherapy for Local
Respiratory Allergy* (`32430550`). El top-5 semántico contiene los tres positivos
anotados; el híbrido conserva dos. Recall pasa de 1 a 2/3 (−0.3333) y Precision
de 0.60 a 0.40 (−0.20). El primer resultado sigue siendo relevante: Hit Rate y
reciprocal rank no cambian. Los títulos y juicios proceden del snapshot M7.

La coincidencia léxica de «immunotherapy» en otro contexto biomédico es una
explicación plausible del ascenso del distractor. Los runs guardan el ranking
semántico y el fusionado, no cada contribución BM25 por término; este análisis
no acredita una atribución causal detallada ni permite generalizar el fallo.
No se ajustan parámetros ni etiquetas para corregir q07.

## Decisión y límites

El desarrollador decide mantener `semantic` como modo predeterminado y baseline
para M9.2: en esta comparación preserva mejor los positivos anotados, mientras
que el híbrido no mejora ninguna métrica y pierde uno en q07. `hybrid` permanece
seleccionable como alternativa experimental. No se optimiza BM25 ni se ajusta
RRF para este dataset y no se introducen más cambios en retrieval dentro de M9.1.
M9.2 es el siguiente trabajo, con alcance propio; esta entrega no elige ni
implementa reranking o reformulación.

Esta conclusión solo corresponde a 10 queries y 50 publicaciones de un corpus
cerrado, seleccionadas para M7, con juicios binarios asistidos sobre título y
abstract y sin consenso clínico experto. Los casos ambiguos reciben cero según
la política conservadora existente. No hay conjunto de prueba independiente,
intervalos de confianza ni demostración de significación estadística. Hit Rate
y MRR ya están saturadas en esta muestra. No demuestra que la búsqueda híbrida
sea generalmente inferior ni evalúa otros dominios, tokenizadores, parámetros,
consultas o volúmenes. Tampoco mide calidad de respuestas RAG, groundedness,
factualidad, latencia de servicio ni memoria bajo carga. Los tiempos de las
corridas incluyen preparación/indexación y no son un benchmark de latencia.

BM25 reconstruye frecuencias en memoria por consulta y lee todo el corpus
elegible; el límite de candidatos no evita ese coste. Es adecuado al volumen
actual y no una solución validada para PubMed completo. Estas limitaciones se
conservan explícitas, sin optimizaciones prematuras.

## Reproducir la comparación sin inferencias

Desde la raíz del repositorio:

```bash
uv run --locked python -m evidenceops.retrieval_comparison \
  evaluation/retrieval/experiments/m9.1/semantic.json \
  evaluation/retrieval/experiments/m9.1/hybrid.json > /tmp/m9.1-comparison.json
cmp evaluation/retrieval/experiments/m9.1/comparison.json /tmp/m9.1-comparison.json
uv run --locked pytest tests/test_lexical.py tests/test_retrieval.py \
  tests/test_retrieval_evaluation.py tests/test_rag_integration.py
```

El comparador valida runs completos, hashes de entradas, configuración de métricas,
texto/juicios por publicación y agregados recalculados. Las pruebas de integración
requieren PostgreSQL/pgvector; usan dobles, sin descargar modelos ni inferir.
La suite completa y `git diff --check` validan la entrega; no son evidencia
adicional de calidad biomédica. Las instrucciones para una futura corrida real
viven en el [runbook](README.md#comparar-semántico-e-híbrido-m91) y requieren
un nuevo encargo; documentar este experimento no autoriza repetirlo.
