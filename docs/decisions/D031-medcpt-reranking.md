# D031 — MedCPT Cross-Encoder sobre candidatos semánticos

Estado: aceptada para #53; implementación y evaluación completadas.
Decisión aprobada: `semantic` por defecto; `reranking` como alternativa experimental.
Fecha: 2026-10-26. Alcance: M9.2.

## Problema y decisión

Añadir una segunda etapa que valore conjuntamente consulta y publicación,
conservando MedCPT semántico como referencia y comportamiento predeterminado.
El desarrollador elige exclusivamente `ncbi/MedCPT-Cross-Encoder`, 20 candidatos
semánticos y 5 resultados. No se implementan otros modelos, reformulación ni
optimización BM25/RRF. El modo explícito se llama `reranking`.

Cada par contiene la consulta y el texto de unidad (`título + "\n\n" + abstract`),
sin alterar la publicación almacenada. Tokenización conjunta con tokens especiales,
`max_length=512`, truncación `longest_first` y padding del lote. Se siguen los
pares y logits del [ejemplo oficial](https://huggingface.co/ncbi/MedCPT-Cross-Encoder).
El tokenizer y el modelo comparten la revisión fija
`71caf65d4927987813984f54c284405a13fcca49`, verificada en metadatos públicos.
Inferencia CPU/float32, `eval()` e `inference_mode()`, lote máximo 20.

La frontera sustituible permite dobles deterministas para este único modelo.
La carga es diferida y reutiliza el extra opcional `medcpt`; importar o arrancar
la aplicación no descarga modelos. No hay nueva infraestructura.

## Contrato e integración

`semantic → filtro/compatibilidad SQL → top20 → Cross-Encoder → top5`.
Los filtros y controles de contenido vigente actúan antes del LIMIT. Se conserva
la identidad, fingerprint, metadata y procedencia de las unidades. Cada resultado
rerankeado contiene el logit en `score` y el dot product en `retrieval_score`.
Scores descendentes y `unit_id` ascendente en empate, también en la selección
inicial. Los scores son logits, no probabilidades ni magnitudes comparables con
los scores semánticos o RRF. Se rechaza cardinalidad incorrecta o valores no finitos.

Corpus vacío no invoca el reranker; corpus corto devuelve menos resultados.
No hay fallback silencioso al modo semántico. RAG conserva su traducción segura
de errores y su contrato HTTP, prompts y generador. La configuración de arranque
`EVIDENCEOPS_RETRIEVAL_MODE=reranking` activa la etapa; logs seguros registran
modelo/revisión y número de candidatos, sin texto ni logits.
`search` admite top_k entre 1 y 20 en este modo; RAG solicita 5.

## Evaluación y alternativas

Se reutilizan corpus, juicios, Hit Rate@5, Recall@5, Precision@5 y MRR de M7.
Para conservar MRR sobre el corpus completo, se reordenan únicamente los 20
candidatos y se añade la cola semántica intacta. Es un ranking compuesto,
no un Cross-Encoder sobre 50 documentos. Puntuar todo el corpus violaría el
presupuesto operacional acordado; limitar MRR al top5 cambiaría la métrica.
Los artefactos registran candidatos iniciales, ambos scores, tipo de score,
ranking compuesto completo, configuraciones, hashes, entorno y resultados.
La comparación conserva deltas agregados/por query y PMIDs que entran/salen.

La latencia usa reloj monotónico: retrieval (encoder de consulta + SQL + validación),
etapa del reranker (tokenización, forward, validación, ordenación y eventual
carga diferida), total de búsqueda. La medición del reranker representa el coste
operacional de inferencia, no exclusivamente el kernel del forward.
Se excluyen indexación, ranking diagnóstico, métricas y escritura. Las consultas
medidas no reutilizan embeddings de consultas anteriores; el diagnóstico sí.
`--warmup` hace una consulta previa no medida en cada run, recomendada para
comparación estable. Sin ella, la primera medición puede incluir descarga/carga;
no es comparable con un run caliente. Medias, medianas y p95 son descriptivos,
con diez consultas y hardware local no constituyen un benchmark general.

## Consecuencias y límites

El reranker solo puede mejorar el orden de los candidatos: no rescata publicaciones
fuera del top20. La truncación puede omitir evidencia; añade memoria y latencia
local. Empates son deterministas, pero resultados numéricos entre versiones o
hardware no están garantizados bit a bit. El experimento real no justifica
adoptar el reranking por defecto en las condiciones evaluadas. Implementar y
probar el mecanismo no acredita mejora IA ni calidad end-to-end de RAG.
Se preservan baseline M7 y todos los artefactos M9.1; no se promociona otro baseline.

## Resultado experimental posterior

La comparación real del 26-10-2026 se ejecutó por petición explícita del
desarrollador: [informe y artefactos](../../evaluation/retrieval/REPORT-m9.2.md).
No mejora ninguna métrica por query; q05 empeora en Recall@5/Precision@5.
El total medio CPU pasa de 0,0318 a 7,0983 s en una pareja de runs calientes.
El desarrollador aprueba mantener `semantic` por defecto y conservar `reranking`
como alternativa experimental: no se justifica su coste en estas condiciones.
La decisión cierra M9.2 tras integración, sin generalizar inferioridad del modelo.
No se promueve baseline ni se repiten inferencias.
