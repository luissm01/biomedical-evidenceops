# Auditoría documental de las etiquetas RAG v1

Fecha: 2026-10-24. Revisión asistida de los **50 títulos y abstracts completos**
del snapshot [corpus-v1.json](../retrieval/corpus-v1.json) frente a las diez
preguntas. Se conserva el corpus M7 intacto y las diez clasificaciones. No se
consultaron rankings ni respuestas RAG; no se ejecutó inferencia. Esta auditoría
no acredita revisión clínica experta ni añade fuentes fuera del corpus.

El desarrollador aprobó los diez casos en la conversación, solicitando corregir
r09, contrastar las etiquetas contra todo el corpus y comprobar la separación
de anotaciones/entradas. La corrección y esta comprobación preceden a cualquier
corrida real. Los hashes finales están en [freeze-v1.json](freeze-v1.json).

## Resultado por pregunta

| Caso | Documentos pertinentes y contraste con el resto | Resultado |
| --- | --- | --- |
| r01 | 29627041 y 35988550 describen riesgo infantil, peor control y exacerbaciones. 34353454 trata asma en mujeres y obesidad, sin resolver la relación infantil completa. Los documentos de obesidad/metabolismo no añaden una estimación causal que permita hablar de cura. El resto no estudia esa relación. | Suficiente para una síntesis asociativa, con límites. |
| r02 | 30552067 enumera GATA3, MUC5AC, KIAA1109 y la señal no asociada al incluir asma leve; 31090575 corrobora los loci y la distinción de gravedad. 28371335 estudia otros genes en sensibilización fúngica. Ninguno de los restantes contradice esa lectura del GWAS ni aporta intervención genética. | Suficiente; ancla primaria del ensayo original, revisión complementaria admisible. |
| r03 | 27493136 contiene población sin tratamiento previo, comparación de combinación/monoterapias, 24 semanas y cambios de HbA1c. 38763510 compara metformina con atorvastatina a 16 semanas; 22000494 es una revisión general. Los demás documentos metabólicos, cardiovasculares y de insulina no sustituyen el ensayo de empagliflozina. | Suficiente para ese desenlace y horizonte. |
| r04 | 33301246 especifica dos dosis, edad ≥16 años, eficacia del 95% frente a COVID-19 y mediana de dos meses de seguridad. 35636910 revisa vacunas COVID-19, pero su abstract no añade cifras ni seguimiento para la pregunta. Los documentos de gripe no responden al ensayo BNT162b2. | Suficiente; no equivale a eficacia actual ni seguridad de largo plazo. |
| r05 | 33050934 es el único documento del corpus sobre NAVIGATOR/tezepelumab. Expone diseño de fase 3 en curso, población y 52 semanas; el hasta 71% se atribuye explícitamente a PATHWAY fase 2b. 37364283 presenta resultados de ensifentrina en EPOC; 33829619 también trata EPOC; 32430550, inmunoterapia en alergia local. Ninguno de los otros 49 abstracts aporta el resultado final de NAVIGATOR. | **Parcial**, aunque se examine todo el corpus. Puede describirse el diseño; falta el resultado final solicitado. |
| r06 | 27494630 describe protección materna y neonatal general, pero no una estimación para nacidos antes de 32 semanas. 33650528 menciona embarazadas y grupos vulnerables sin esa estimación; 27813430 evalúa vacuna de alta dosis en mayores, no prematuros. 28292619 menciona consecuencias reproductivas de obesidad; 38697182 estudia insulina en embarazo. Ninguno de los demás abstracts da eficacia antigripal para el subgrupo. | **Parcial**, incluso con los 50 documentos. El «50% como máximo» general no es una estimación específica para prematuros. |
| r07 | 30552067 y 31090575 son asociación genética/revisión de asma; 28371335 estudia asociaciones en asma con sensibilización fúngica. Los demás estudios respiratorios no editan MUC5AC. Las referencias a genómica y terapias dirigidas en oncología tampoco estudian cura CRISPR de asma. Ninguno de los 50 abstracts demuestra el ensayo solicitado. | Ausente en este snapshot. Una negación fundamentada o una abstención justificada pueden aprobar. |
| r08 | 24356592 trata control intensivo poblacional; 38697182 compara sistemas de insulina en embarazadas. Los estudios de diabetes, resistencia a insulina y metformina no aportan factores individuales, pauta basal, sensibilidad, insulina activa ni un protocolo que resuelva la dosis solicitada. El resto tampoco. | Ausente para calcular esa dosis individual; no implica ausencia de evidencia sobre insulina en general. |
| r09 | 35263517: SHINE, menores de 16 años, TB no grave y tratamiento estándar de primera línea, cuatro frente a seis meses. 33951360: otro ensayo con rifapentina ± moxifloxacino; su abstract no especifica el rango de edad. Los ensayos pediátricos 35040920 y 33683325 son neumonía, no TB. No hay apoyo en el resto para extrapolar automáticamente el régimen con rifapentina-moxifloxacino a todos los niños. | Distractores plausibles; se elimina «régimen adulto» sin inventar edades ausentes del abstract. |
| r10 | 37364283: ENHANCE estudia ensifentrina en EPOC. 33829619 trata farmacología de EPOC; 33050934, tezepelumab en asma. Los demás documentos respiratorios no prueban eficacia de ensifentrina en asma grave. | Distractores plausibles; «no demuestra eficacia en asma» es una respuesta pertinente, distinta de afirmar ineficacia demostrada. |

Los casos parciales no exigen inventar la parte ausente ni abstenerse de la parte
respondible. Los casos ausentes no exigen una respuesta positiva. La clasificación
del corpus no se pasa al LLM ni modifica sus instrucciones, fuentes o ranking.
`expected_pmids` sigue siendo un conjunto de anclajes diagnósticos, no una whitelist
que restrinja qué documentos pueden recuperarse o citarse.

## Cobertura del corpus inspeccionado

Se inspeccionaron las cinco áreas completas, incluidos documentos vecinos que
podrían confundirse por población, intervención o enfermedad. Este inventario
permite identificar qué snapshot se revisó, sin duplicar los abstracts ni alterar
las etiquetas binarias de retrieval M7.

| Área | PMIDs inspeccionados |
| --- | --- |
| respiratory | 29627041, 35988550, 34353454, 31090575, 30552067, 28371335, 32430550, 33050934, 37364283, 33829619 |
| metabolic | 27493136, 38763510, 22000494, 28467922, 37425065, 34767960, 24356592, 38697182, 36774932, 28292619 |
| cardiovascular | 38141902, 35653320, 29669543, 33793326, 35896123, 37161520, 28460827, 38184132, 24315724, 36519436 |
| oncology | 38512301, 29863955, 31018251, 35115765, 33198517, 38857504, 36252154, 27184418, 38924756, 37879444 |
| infectious | 35040920, 35505000, 33683325, 33650528, 27494630, 27813430, 33301246, 35636910, 35263517, 33951360 |
