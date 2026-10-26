# M9 — Advanced RAG & Retrieval

[Milestone M9](https://github.com/luissm01/biomedical-evidenceops/milestone/9).
M9.1 integrada mediante PR #54; M9.2 completada con decisión aprobada.
M9 lista para cierre tras integrar #53. Secuencia canónica en el [roadmap](../ROADMAP.md).

## M9.1 — Hybrid Retrieval (#52)

[Issue #52](https://github.com/luissm01/biomedical-evidenceops/issues/52).
BM25 real en Python, MedCPT + pgvector y fusión RRF con k=60, filtros compartidos,
deduplicación por unit_id y desempates deterministas. Selector explícito con
semantic por defecto. [Contrato y decisiones](../decisions/D030-hybrid-retrieval.md).

Implementación, pruebas deterministas y comparación real completadas. El
[informe](../../evaluation/retrieval/REPORT-m9.1.md) conserva los runs y resultados:
Hybrid pierde Recall@5/Precision@5 en q07 y mantiene métricas en las otras nueve
queries; no mejora ninguna métrica. El desarrollador mantiene semantic por defecto
y como baseline para M9.2, sin ajustar BM25/RRF al dataset. Hybrid se conserva
como alternativa experimental. No se generaliza inferioridad del híbrido.

M9.1 se integró mediante PR #54 y la issue #52 está cerrada. No se modifica
el baseline M7. No quedan más cambios de retrieval
por implementar dentro de M9.1.

## M9.2 — Reranking & Evaluation (#53)

[Issue #53](https://github.com/luissm01/biomedical-evidenceops/issues/53).
Implementación local preparada con las decisiones explícitas del desarrollador:
Cross-Encoder MedCPT único, candidatos semánticos top20, top5 final, pares consulta
con título/abstract y 512 tokens, logits descendentes y desempates por unidad.
`semantic` permanece por defecto. Modelo y revisión fijos, extra opcional,
filtros, scores originales y trazabilidad preservados.

Evaluación/comparación amplían el mecanismo existente: mismos corpus/juicios y
métricas, candidatos de entrada, ranking compuesto completo para MRR, latencias
separadas y deltas por consulta. Pruebas con dobles e integración PostgreSQL/RAG,
sin descarga de modelos ni inferencias reales.
[Contrato y trade-offs](../decisions/D031-medcpt-reranking.md).

Experimento real ejecutado por petición explícita: [informe y artefactos](../../evaluation/retrieval/REPORT-m9.2.md).
Recall@5/Precision@5 empeoran en q05, ninguna query mejora métricas y el coste
medio total CPU pasa de 0,0318 a 7,0983 s en una pareja de runs con calentamiento.
Decisión aprobada: mantener `semantic` por defecto y `reranking` experimental.
M9.2 completada; M9 lista para cierre tras la integración. No hay promoción de baseline.
No repetir inferencias para confirmar el resultado. Baseline M7 y resultados
M9.1 intactos; no se amplía generación ni evaluación RAG end-to-end.

## Límites y aprendizaje

Datos biomédicos públicos y recursos gratuitos; tests/CI con dobles y sin
inferencias reales. Las corridas reales requieren su propio encargo; no repetir
las de M9.1 para confirmar resultados ni reutilizar la excepción de M8.
Sin agentes, tools/MCP, colas, nuevos despliegues o adaptación de modelos.

El [registro M9](../learning/m9.md) conserva las decisiones e interpretación
expresadas por el desarrollador; el código generado no acredita comprensión.
El repaso de cierre de M9 usará evidencias existentes y registrará solo
aprendizaje demostrado. Las dos issues tienen implementación, evaluación y decisión completas;
la integración de #53 es el último paso de entrega de M9.
