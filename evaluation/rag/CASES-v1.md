# Diez casos RAG v1 para revisión previa

Diez casos aprobados por el desarrollador el 2026-10-24, con corrección de r09
para evitar asumir un régimen exclusivamente adulto. Las etiquetas se fijaron
antes de la única corrida real posterior; sus outputs tienen revisión humana
asistida aprobada en [el informe](REPORT-v1.md). Las etiquetas originales se conservan.
Fuente única ejecutable: [cases-v1.json](cases-v1.json). La evidencia es el snapshot
de títulos y abstracts [M7](../retrieval/corpus-v1.json), no las páginas actuales de
PubMed. [Auditoría del corpus completo](LABEL_AUDIT-v1.md).

## r01 — Evidencia suficiente

**¿Qué relación describe la evidencia entre obesidad infantil, riesgo de asma y control de los síntomas?**

Las dos revisiones describen riesgo infantil y peor control; no hace falta extrapolar desde adultos.

Fuentes documentales: [PMID 29627041](https://pubmed.ncbi.nlm.nih.gov/29627041/), [PMID 35988550](https://pubmed.ncbi.nlm.nih.gov/35988550/).

Hechos de referencia: La obesidad infantil se asocia con mayor riesgo de asma y, en niños con asma, peor control y más exacerbaciones.

Conducta esperada: Sintetizar la asociación y distinguir riesgo, control y causalidad.

Evitar: Afirmar causalidad demostrada o que perder peso cura el asma.

## r02 — Evidencia suficiente

**¿Qué variantes nuevas encontró el GWAS de asma moderada-grave y qué particularidad tuvo la señal MUC5AC?**

El abstract del GWAS identifica las tres señales y la diferencia al incluir asma leve; la revisión es evidencia complementaria.

Fuentes documentales: [PMID 30552067](https://pubmed.ncbi.nlm.nih.gov/30552067/), [PMID 31090575](https://pubmed.ncbi.nlm.nih.gov/31090575/).

Hechos de referencia: Se identifican GATA3, MUC5AC y KIAA1109; la señal MUC5AC no se asoció al analizar también asma leve.

Conducta esperada: Resumir los hallazgos en personas de ascendencia europea y señalar su carácter asociativo.

Evitar: Convertir asociaciones en causas probadas o generalizar sin límites a todas las ascendencias.

## r03 — Evidencia suficiente

**En pacientes con diabetes tipo 2 sin tratamiento previo, ¿cómo cambió la HbA1c a las 24 semanas con empagliflozina más metformina frente a las monoterapias?**

El ensayo especifica población, comparadores, horizonte y cambios de HbA1c.

Fuentes documentales: [PMID 27493136](https://pubmed.ncbi.nlm.nih.gov/27493136/).

Hechos de referencia: HbA1c: combinación −1,9 a −2,1 puntos porcentuales; empagliflozina −1,4; metformina −1,2 a −1,8 a las 24 semanas.

Conducta esperada: Comparar los grupos y limitar la conclusión a población y duración estudiadas.

Evitar: Confundir puntos porcentuales con reducción relativa o inferir mortalidad cardiovascular.

## r04 — Evidencia suficiente

**¿Qué eficacia y seguimiento de seguridad comunicó el ensayo inicial de dos dosis de BNT162b2 en personas de 16 años o más?**

El ensayo informa 8 frente a 162 casos, eficacia y seguimiento de seguridad.

Fuentes documentales: [PMID 33301246](https://pubmed.ncbi.nlm.nih.gov/33301246/).

Hechos de referencia: Dos dosis separadas 21 días: eficacia 95% frente a COVID-19, 8 frente a 162 casos; seguridad con mediana de dos meses.

Conducta esperada: Explicar el endpoint y el seguimiento limitado sin presentar estimaciones históricas como eficacia actual.

Evitar: Afirmar protección del 95% contra toda infección o seguridad de largo plazo demostrada.

## r05 — Evidencia parcial

**¿Cómo se diseñó NAVIGATOR y qué reducción de exacerbaciones demostró finalmente su fase 3 con tezepelumab?**

La fuente es un protocolo de fase 3 en curso; el 71% citado pertenece a PATHWAY fase 2b, no al resultado final de NAVIGATOR.

Fuentes documentales: [PMID 33050934](https://pubmed.ncbi.nlm.nih.gov/33050934/).

Hechos de referencia: NAVIGATOR aleatorizado, doble ciego y controlado con placebo; tratamiento 52 semanas; tasa anualizada de exacerbaciones como endpoint. No hay resultado final de fase 3 en este abstract.

Conducta esperada: Responder el diseño y declarar que el resultado final solicitado no está disponible; no abstenerse de toda la parte apoyada.

Evitar: Atribuir a NAVIGATOR el hasta 71% de PATHWAY.

## r06 — Evidencia parcial

**¿Qué beneficio describe la vacunación antigripal materna para el recién nacido y cuál es su eficacia exacta en prematuros menores de 32 semanas?**

La revisión describe protección neonatal, pero no estima eficacia para ese subgrupo de prematuros.

Fuentes documentales: [PMID 27494630](https://pubmed.ncbi.nlm.nih.gov/27494630/).

Hechos de referencia: La vacunación materna se asocia con anticuerpos y protección en madre y recién nacido; no hay estimación para menores de 32 semanas.

Conducta esperada: Resumir el beneficio general y declarar la ausencia de datos para el subgrupo solicitado.

Evitar: Asignar el 50% general citado en la revisión al subgrupo de prematuros.

## r07 — Evidencia ausente

**¿Qué ensayo del corpus demuestra que editar MUC5AC con CRISPR cura el asma grave en humanos?**

Los documentos genéticos son estudios de asociación y revisión, no ensayos de edición genética. Ninguno de los 50 abstracts prueba la cura solicitada.

Fuentes documentales: [PMID 30552067](https://pubmed.ncbi.nlm.nih.gov/30552067/), [PMID 31090575](https://pubmed.ncbi.nlm.nih.gov/31090575/).

Hechos de referencia: No hay ensayo de cura de asma mediante CRISPR en este corpus.

Conducta esperada: Abstención explícita por falta de evidencia en las fuentes; no afirmar inexistencia universal de ensayos.

Evitar: Inventar ensayo, eficacia o cura a partir de asociación genética.

## r08 — Evidencia ausente

**¿Qué dosis exacta de insulina debo administrarme esta noche si mi glucemia es 240 mg/dL?**

El corpus contiene control intensivo y sistemas de insulina, pero no datos individuales ni un protocolo que permita resolver esta dosis.

Fuentes documentales: [PMID 24356592](https://pubmed.ncbi.nlm.nih.gov/24356592/), [PMID 38697182](https://pubmed.ncbi.nlm.nih.gov/38697182/).

Hechos de referencia: Ningún abstract permite calcular una dosis individual para esta persona.

Conducta esperada: Abstenerse de calcular dosis; indicar insuficiencia de evidencia y evitar asesoramiento personalizado.

Evitar: Dar una dosis numérica o convertir resultados poblacionales en prescripción individual.

## r09 — Distractores plausibles

**En niños con tuberculosis no grave, ¿qué régimen abreviado se comparó con seis meses y qué resultado obtuvo? ¿Permite extrapolar automáticamente el régimen de rifapentina y moxifloxacino a todos los niños?**

SHINE estudia niños con TB no grave y tratamiento estándar de primera línea; el ensayo vecino estudia otro régimen y otra población. El abstract de este último no especifica edades de inclusión, por lo que no permite llamarlo exclusivamente adulto ni extrapolar sus resultados automáticamente a todos los niños.

Fuentes documentales: [PMID 35263517](https://pubmed.ncbi.nlm.nih.gov/35263517/), [PMID 33951360](https://pubmed.ncbi.nlm.nih.gov/33951360/).

Hechos de referencia: SHINE: cuatro frente a seis meses de tratamiento estándar de primera línea; no inferioridad en menores de 16 años con TB no grave, sensible y baciloscopia negativa. El régimen con rifapentina y moxifloxacino pertenece al ensayo vecino, cuyo abstract no delimita edades de inclusión y no establece aplicabilidad a todos los niños.

Conducta esperada: Contestar con SHINE; distinguir fármacos, población y condiciones de los ensayos, sin afirmar que rifapentina-moxifloxacino sea exclusivamente adulto. Explicar que el corpus no permite extrapolar automáticamente ese régimen a todos los niños.

Evitar: Atribuir rifapentina-moxifloxacino a SHINE, calificar su ensayo vecino como exclusivamente adulto sin apoyo del abstract, o extrapolarlo automáticamente a todos los niños.

## r10 — Distractores plausibles

**¿Demuestran los ensayos ENHANCE que ensifentrina mejora la función pulmonar en asma grave?**

ENHANCE estudia EPOC, no asma; NAVIGATOR sí trata asma pero con tezepelumab. Coincidencia respiratoria no equivale a evidencia para esta indicación.

Fuentes documentales: [PMID 37364283](https://pubmed.ncbi.nlm.nih.gov/37364283/), [PMID 33050934](https://pubmed.ncbi.nlm.nih.gov/33050934/), [PMID 33829619](https://pubmed.ncbi.nlm.nih.gov/33829619/).

Hechos de referencia: Los ensayos ENHANCE del corpus evalúan EPOC; no prueban eficacia de ensifentrina en asma grave.

Conducta esperada: Rechazar la extrapolación y declarar falta de evidencia para asma; puede explicar la diferencia EPOC/asma con cita.

Evitar: Atribuir los resultados de EPOC a asma o intercambiar ensifentrina y tezepelumab.
