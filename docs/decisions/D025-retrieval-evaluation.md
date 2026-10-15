# D025 — Corpus fijo y evaluación binaria de retrieval (#40)

## Estado

Aceptada. El desarrollador da #40 por terminada el 15 de octubre de 2026
y autoriza su entrega. Corpus y anotaciones siguen siendo asistidos, sin
atribuir una revisión experta de las etiquetas.

## Problema

#39 implementa retrieval pero su contrato y tests no dicen qué evidencia recupera
MedCPT. M7 necesita una referencia pequeña antes de conectar generación en M8.

## Decisión

Congelar 50 publicaciones públicas de PubMed, 10 por cada una de cinco áreas,
y las 10 queries acordadas. Versionar textos normalizados, bibliografía, búsquedas,
candidatos seleccionados, PMIDs y hashes. Juzgar publicaciones por PMID usando
solo título y abstract antes de ejecutar MedCPT; explicitar criterios y razones
de cada positivo. Las anotaciones son asistidas y los ambiguos se excluyen conservadoramente
de positivos; la aceptación de la entrega no acredita consenso experto.

Relevancia binaria. Hit Rate@5, Recall@5, Precision@5 y MRR con medias macro.
Precision divide por K solicitado incluso en rankings cortos. Sin relevantes,
Recall es indefinido y se excluye únicamente de su media; las otras métricas
valen cero. MRR usa ranking completo, separado del top-5 operacional. PMIDs
repetidos en un ranking son inválidos. No implementar NDCG.

Reutilizar `index_publication` y `search` con los encoders y pgvector de D024,
en un esquema temporal aislado para garantizar que los candidatos coincidan con
el corpus congelado. Registrar configuración, entorno, hashes de inputs/código,
rankings y métricas. Evaluación independiente del generador y sin HTTP. El
[runbook](../../evaluation/retrieval/README.md) define operación y artefactos.

## Alternativas y trade-offs

- Usar corpus de desarrollo abarata preparación, pero permite contaminación y
  cambios silenciosos de candidatos. El esquema aislado exige permiso de crear
  esquemas, a cambio de evaluar exactamente el snapshot.
- Puntuar vectores en memoria sería sencillo, pero no evalúa el flujo pgvector de
  #39. Se conserva el retriever real y un ranking completo solo para diagnóstico.
- Juicios graduados permitirían NDCG, pero exigen acordar grados y más esfuerzo
  de anotación. Los binarios permiten iniciar Recall sin inventar precisión.
- Juzgar solo resultados del modelo introduciría sesgo de pooling. Se consideran
  todos los pares del pequeño corpus y se congela el dataset antes del ranking.

## Consecuencias

Un baseline trazable permite comparar cambios posteriores sobre una referencia
idéntica. La selección temática, el pequeño tamaño, los abstracts y el único
anotador asistido limitan su validez; buenos números no demuestran calidad clínica
ni generalización. Versionar los juicios no transforma una propuesta en consenso
experto. La revisión posterior que cambie etiquetas requiere otra versión, con
métricas recalculadas en ambos runs comparados. M7 termina en retrieval medido,
sin generación ni estrategias avanzadas de M9.
