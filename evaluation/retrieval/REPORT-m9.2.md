# M9.2 — Experimento de reranking MedCPT

Ejecutado por Codex el 26 de octubre de 2026 tras autorización explícita del
desarrollador para inferencia real. Ambos runs terminan completos, exit code 0,
con 50 publicaciones públicas y 10 consultas congeladas de M7. No se invocan
LLMs ni se modifican juicios, textos, baseline M7 o resultados M9.1.

**Resultado:** el reranking no mejora las métricas de ninguna consulta y empeora
q05; añade unos 7,06 segundos de etapa Cross-Encoder por consulta en esta CPU.
Decisión aprobada por el desarrollador: conservar `semantic` por defecto y
`reranking` como alternativa experimental. No se justifica el coste añadido en
las condiciones evaluadas. M9.2 completada y lista para integración; no se
promociona ningún baseline.

## Protocolo y artefactos

Una ejecución semántica seguida de una con reranking, cada una con una consulta
de calentamiento no medida y diez consultas medidas. CPU Intel Core i5-12400F,
WSL2 Linux x86_64, float32, cuatro hilos intra-op y seis inter-op de PyTorch.
`OMP_NUM_THREADS=4 MKL_NUM_THREADS=4`; no hubo otros runs de modelos lanzados por
el agente en paralelo. La carga externa del equipo no se midió ni controló.
Entornos y protocolos registrados coinciden. Es una sola pareja de ejecuciones;
no se realizaron repeticiones ni se alternó el orden.

MedCPT Query/Article conserva su configuración M7 y revisiones fijas. El
Cross-Encoder usa `ncbi/MedCPT-Cross-Encoder`, revisión
`71caf65d4927987813984f54c284405a13fcca49`, pares consulta/texto de unidad,
512 tokens por pareja, truncación longest-first, lote de 20 y logits sin
normalización. Se mantienen K=5, ausencia de filtro temporal y desempates por
unit_id. MRR usa los 20 candidatos rerankeados seguidos de la cola semántica,
con profundidad completa de 50. [Contrato](../../docs/decisions/D031-medcpt-reranking.md).

- [semantic.json](experiments/m9.2/semantic.json): 09:57:23–09:57:41 UTC.
- [reranking.json](experiments/m9.2/reranking.json): 09:57:49–09:59:32 UTC.
- [comparison.json](experiments/m9.2/comparison.json): deltas de métricas y
  tiempos por consulta/agregados, configuraciones y PMIDs que entran/salen.
- [manifest.json](experiments/m9.2/manifest.json): comandos, códigos de salida,
  condiciones y hashes de artefactos y referencias preservadas.
- [inputs-and-code.tar.gz](experiments/m9.2/inputs-and-code.tar.gz): fuentes
  exactas, configuración de dependencias y entradas congeladas, sin `.env`.

Los JSON se copiaron byte a byte desde `evaluation/runs/m9.2-*-01.json`.
Ambos runs comparten hashes de código e inputs. El árbol estaba dirty y el
snapshot conserva el código local identificado por los hashes: el commit
registrado por sí solo no reconstruye el experimento. Se verificó integridad
de baseline M7 y artefactos M9.1 contra su manifest previo. El ranking semántico
completo reproduce el orden de PMIDs del baseline M7 en las diez consultas.

## Calidad

| Métrica | Semantic | Reranking | Delta |
| --- | --- | --- | --- |
| Hit Rate@5 | 1,0000 | 1,0000 | 0,0000 |
| Recall@5 | 0,9750 | 0,9500 | −0,0250 |
| Precision@5 | 0,5000 | 0,4800 | −0,0200 |
| MRR | 1,0000 | 1,0000 | 0,0000 |

No hay mejoras métricas por consulta; nueve empatan y q05 empeora. Todos los
primeros resultados siguen siendo relevantes según los juicios existentes.
La tabla conserva también cambios de pertenencia sin mejora ni regresión métrica:

| Query | Recall@5 antes → después | Precision@5 antes → después | Entra en top5 | Sale de top5 |
| --- | --- | --- | --- | --- |
| q01 | 1,00 → 1,00 | 0,40 → 0,40 | — | — |
| q02 | 1,00 → 1,00 | 0,60 → 0,60 | — | — |
| q03 | 1,00 → 1,00 | 0,60 → 0,60 | 34767960 | 29669543 |
| q04 | 1,00 → 1,00 | 0,60 → 0,60 | 37161520 | 29627041 |
| q05 | 0,75 → 0,50 | 0,60 → 0,40 | 35896123 | 37161520 |
| q06 | 1,00 → 1,00 | 0,20 → 0,20 | 29669543 | 36519436 |
| q07 | 1,00 → 1,00 | 0,60 → 0,60 | — | — |
| q08 | 1,00 → 1,00 | 0,40 → 0,40 | 27184418, 35040920 | 29863955, 38924756 |
| q09 | 1,00 → 1,00 | 0,60 → 0,60 | — | — |
| q10 | 1,00 → 1,00 | 0,40 → 0,40 | 35636910 | 35040920 |

En q05 (`association between hypertension and cardiovascular disease risk`),
el PMID relevante 37161520 baja del puesto 3 al 6 y el PMID 35896123, etiquetado
operacionalmente no relevante, sube del 6 al 2. Ambos estaban entre los candidatos:
la pérdida se produce al ordenar, no por exclusión del top20 inicial.
Esto describe el ranking observado; no atribuye una causa al modelo o truncación
ni sustituye la revisión biomédica de las etiquetas. Los empates métricos pueden
ocultar cambios de orden; los rankings completos permiten inspeccionarlos.

## Latencia

Segundos por consulta, después del calentamiento. Las duraciones totales del run
incluyen otras operaciones y no deben confundirse con estos tiempos de búsqueda.

| Etapa | Semantic media / mediana / p95 | Reranking media / mediana / p95 |
| --- | --- | --- |
| Retrieval | 0,0318 / 0,0305 / 0,0397 | 0,0381 / 0,0338 / 0,0664 |
| Reranker | 0 / 0 / 0 | 7,0602 / 7,0248 / 7,2171 |
| Total | 0,0318 / 0,0305 / 0,0397 | 7,0983 / 7,0577 / 7,2545 |

La diferencia de medias totales es +7,0665 s (aproximadamente 223 veces el total
semántico observado). La etapa del reranker incluye tokenización, forward,
validación y ordenación; no es exclusivamente tiempo del kernel. Se excluyen
indexación, carga/calentamiento, ranking completo de diagnóstico, cálculo de
métricas y escritura. Cada consulta medida vuelve a codificarse; el diagnóstico
reutiliza su vector. p95 es nearest-rank y coincide con el máximo en diez muestras.

Esta pareja de runs mide el coste observado en CPU y esta configuración. No
establece significación estadística, variabilidad entre repeticiones ni rendimiento
en otro hardware. No se justifica adoptar este coste sin una mejora observada;
no se cambia hardware, modelo, etiquetas o parámetros para forzarla.

## Reproducir el análisis sin inferencia

```bash
uv run --locked python -m evidenceops.retrieval_comparison \
  evaluation/retrieval/experiments/m9.2/semantic.json \
  evaluation/retrieval/experiments/m9.2/reranking.json
```

El resultado debe coincidir con `comparison.json`; hashes y cálculo de métricas
se verifican sin modelos. Los comandos de inferencia realmente ejecutados están
en el manifest; sus destinos ya existen y el runner los protege. No repetirlos
para confirmar este resultado. Nuevos runs requieren rutas nuevas y su propio
encargo. [Procedimiento](README.md#comparar-semántico-y-reranking-m92).

Los juicios son los de M7, asistidos por Codex, sin consenso clínico experto;
no se cambiaron después de observar los outputs ni se añadió revisión humana
atribuida al desarrollador. Muestra pequeña y corpus cerrado. Esta evaluación
real de retrieval no acredita calidad de respuestas RAG ni de generación.
