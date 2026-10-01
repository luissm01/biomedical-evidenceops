# M6 — Biomedical Data Ingestion: plan activo

## Alcance y orden

Adquirir literatura biomédica pública, normalizar metadata y abstracts, y
persistir publicaciones mediante un flujo local reejecutable. Alcance canónico
en el [roadmap](../ROADMAP.md#m6--biomedical-data-ingestion). Las decisiones
duraderas están en [D021](../decisions/D021-biomedical-ingestion-source-and-contract.md).

1. [#28: fuente y contrato](https://github.com/luissm01/biomedical-evidenceops/issues/28):
   completada; decisiones tomadas y documentadas en D021.
2. [#29: adquisición, parsing y normalización](https://github.com/luissm01/biomedical-evidenceops/issues/29):
   completada. Depende de #28.
3. [#30: persistencia e idempotencia](https://github.com/luissm01/biomedical-evidenceops/issues/30):
   siguiente issue; depende del contrato y de #29. Proteger `(source, source_id)`
   y aplicar reingestión mediante update.
4. [#31: pipeline y validación end-to-end](https://github.com/luissm01/biomedical-evidenceops/issues/31):
   depende de #29 y #30; CLI fina, fallos parciales y resumen de ejecución.

## Decisiones abiertas y evidencia

No queda abierta la elección de fuente, contrato conceptual, identidad,
reingestión ni interfaz: ver D021. #30 y #31 concretarán persistencia y pipeline.
Tests y CI no harán llamadas reales; una demo pequeña requiere autorización
explícita. No introducir retrieval, embeddings, chunks, RAG ni infraestructura
de milestones posteriores.
