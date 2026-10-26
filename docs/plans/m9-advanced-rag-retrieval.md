# M9 — Advanced RAG & Retrieval

[Milestone M9](https://github.com/luissm01/biomedical-evidenceops/milestone/9).
M9.1 completada localmente, pendiente de integración mediante PR; M9.2 pendiente
de implementación. Secuencia canónica en el [roadmap](../ROADMAP.md).

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

El cierre de la issue se realizará al fusionar la PR revisada; no se cierra
manualmente ni se modifica el baseline M7. No quedan más cambios de retrieval
por implementar dentro de M9.1.

## M9.2 — Reranking & Evaluation (#53)

[Issue #53](https://github.com/luissm01/biomedical-evidenceops/issues/53).
Siguiente tarea, pendiente de implementación y de encargo propio:

- Reranking sobre candidatos obtenidos mediante MedCPT, manteniendo disponible
  la búsqueda semántica como referencia.
- Comparar semantic frente a semantic + reranking con el dataset y métricas
  existentes, preservando corpus, juicios y baseline originales.
- Medir calidad y latencia con configuración y condiciones comparables.
- Documentar mejoras, regresiones y límites por query y decidir si el reranking
  justifica la complejidad adicional.

Antes de implementar, acordar una técnica o modelo utilizable gratis, profundidad
de candidatos, contrato de scores, filtros, desempates y protocolo de latencia.
No se elige modelo en este cierre ni se introduce reformulación de consultas.
La evaluación de retrieval no acredita calidad de respuestas RAG; una ampliación
end-to-end requeriría acordar expresamente su alcance.

## Límites y aprendizaje

Datos biomédicos públicos y recursos gratuitos; tests/CI con dobles y sin
inferencias reales. Las corridas reales requieren su propio encargo; no repetir
las de M9.1 para confirmar resultados ni reutilizar la excepción de M8.
Sin agentes, tools/MCP, colas, nuevos despliegues o adaptación de modelos.

El [registro M9](../learning/m9.md) conserva las decisiones e interpretación
expresadas por el desarrollador; el código generado no acredita comprensión.
El repaso de cierre de M9 usará evidencias existentes y registrará solo
aprendizaje demostrado. M9 no se considera completada por haber terminado M9.1.
