# M7 / #40 — Corpus, juicios y baseline para revisión

Implementación y corrida real completadas. El desarrollador acepta el cierre de #40 y autoriza su entrega el 15 de octubre de 2026. Corpus y juicios son asistidos por Codex; esta aceptación no acredita revisión experta de cada etiqueta. Los juicios se fijaron usando solo título y abstract antes de MedCPT; no hay generación ni modelo evaluador.

## Corpus final y construcción

50 publicaciones: 10 por área. PubMed ESearch/EFetch, inglés, abstract disponible, publicación 2000–2024. Cuotas 3/3/2/2 por área: dos temas de queries y dos vecinos. El snapshot conserva los textos normalizados por el parser M6. Las búsquedas exactas, candidatos y orden de selección están en `corpus-v1.json → discovery`.

Una primera búsqueda sin campos producía documentos excesivamente amplios; se refinó a título/abstract antes de anotación e inferencia. Para genética de asma grave, se eligieron una revisión, un GWAS y un estudio de sensibilización fúngica con cobertura explícita, documentando esa excepción. No se cambió el corpus ni las etiquetas después de ver el ranking.

| Área de selección | PMID | Título |
| --- | --- | --- |
| respiratory | [29627041](https://pubmed.ncbi.nlm.nih.gov/29627041/) | Obesity and asthma. |
| respiratory | [35988550](https://pubmed.ncbi.nlm.nih.gov/35988550/) | Obesity-related asthma in children and adolescents. |
| respiratory | [34353454](https://pubmed.ncbi.nlm.nih.gov/34353454/) | Unique Aspects of Asthma in Women. |
| respiratory | [31090575](https://pubmed.ncbi.nlm.nih.gov/31090575/) | Asthma severity, nature or nurture: genetic determinants. |
| respiratory | [30552067](https://pubmed.ncbi.nlm.nih.gov/30552067/) | Moderate-to-severe asthma in individuals of European ancestry: a genome-wide association study. |
| respiratory | [28371335](https://pubmed.ncbi.nlm.nih.gov/28371335/) | Genetic susceptibility to severe asthma with fungal sensitization. |
| respiratory | [32430550](https://pubmed.ncbi.nlm.nih.gov/32430550/) | Allergen Immunotherapy for Local Respiratory Allergy. |
| respiratory | [33050934](https://pubmed.ncbi.nlm.nih.gov/33050934/) | NAVIGATOR: a phase 3 multicentre, randomized, double-blind, placebo-controlled, parallel-group trial to evaluate the efficacy and safety of tezepelumab in adults and adolescents with severe, uncontrolled asthma. |
| respiratory | [37364283](https://pubmed.ncbi.nlm.nih.gov/37364283/) | Ensifentrine, a Novel Phosphodiesterase 3 and 4 Inhibitor for the Treatment of Chronic Obstructive Pulmonary Disease: Randomized, Double-Blind, Placebo-controlled, Multicenter Phase III Trials (the ENHANCE Trials). |
| respiratory | [33829619](https://pubmed.ncbi.nlm.nih.gov/33829619/) | Pharmacological treatment of stable chronic obstructive pulmonary disease. |
| metabolic | [27493136](https://pubmed.ncbi.nlm.nih.gov/27493136/) | Initial Combination of Empagliflozin and Metformin in Patients With Type 2 Diabetes. |
| metabolic | [38763510](https://pubmed.ncbi.nlm.nih.gov/38763510/) | Efficacy and Safety of Metformin and Atorvastatin Combination Therapy vs. Monotherapy with Either Drug in Type 2 Diabetes Mellitus and Dyslipidemia Patients (ATOMIC): Double-Blinded Randomized Controlled Trial. |
| metabolic | [22000494](https://pubmed.ncbi.nlm.nih.gov/22000494/) | Metformin effects revisited. |
| metabolic | [28467922](https://pubmed.ncbi.nlm.nih.gov/28467922/) | Metabolic Flexibility in Health and Disease. |
| metabolic | [37425065](https://pubmed.ncbi.nlm.nih.gov/37425065/) | Pathophysiology of obesity and its associated diseases. |
| metabolic | [34767960](https://pubmed.ncbi.nlm.nih.gov/34767960/) | Obesity and insulin resistance: Pathophysiology and treatment. |
| metabolic | [24356592](https://pubmed.ncbi.nlm.nih.gov/24356592/) | The diabetes control and complications trial/epidemiology of diabetes interventions and complications study at 30 years: overview. |
| metabolic | [38697182](https://pubmed.ncbi.nlm.nih.gov/38697182/) | Comparing advanced hybrid closed loop therapy and standard insulin therapy in pregnant women with type 1 diabetes (CRISTAL): a parallel-group, open-label, randomised controlled trial. |
| metabolic | [36774932](https://pubmed.ncbi.nlm.nih.gov/36774932/) | Contemporary medical, device, and surgical therapies for obesity in adults. |
| metabolic | [28292619](https://pubmed.ncbi.nlm.nih.gov/28292619/) | Obesity and female infertility: potential mediators of obesity's impact. |
| cardiovascular | [38141902](https://pubmed.ncbi.nlm.nih.gov/38141902/) | Oral Health and Cardiovascular Disease. |
| cardiovascular | [35653320](https://pubmed.ncbi.nlm.nih.gov/35653320/) | Hypertension and the kidneys. |
| cardiovascular | [29669543](https://pubmed.ncbi.nlm.nih.gov/29669543/) | Diabetes, cardiovascular disease and the microcirculation. |
| cardiovascular | [33793326](https://pubmed.ncbi.nlm.nih.gov/33793326/) | Guideline-Driven Management of Hypertension: An Evidence-Based Update. |
| cardiovascular | [35896123](https://pubmed.ncbi.nlm.nih.gov/35896123/) | Hypertension in children and adolescents. |
| cardiovascular | [37161520](https://pubmed.ncbi.nlm.nih.gov/37161520/) | Comprehensive effects of lifestyle reform, adherence, and related factors on hypertension control: A review. |
| cardiovascular | [28460827](https://pubmed.ncbi.nlm.nih.gov/28460827/) | Heart failure. |
| cardiovascular | [38184132](https://pubmed.ncbi.nlm.nih.gov/38184132/) | Beta-blocker therapy in heart failure with preserved ejection fraction (B-HFpEF): A systematic review and meta-analysis. |
| cardiovascular | [24315724](https://pubmed.ncbi.nlm.nih.gov/24315724/) | Comparison of the efficacy and safety of new oral anticoagulants with warfarin in patients with atrial fibrillation: a meta-analysis of randomised trials. |
| cardiovascular | [36519436](https://pubmed.ncbi.nlm.nih.gov/36519436/) | Atrial Fibrillation Detection and Management in Hypertension. |
| oncology | [38512301](https://pubmed.ncbi.nlm.nih.gov/38512301/) | Neoadjuvant Chemoimmunotherapy for NSCLC: A Systematic Review and Meta-Analysis. |
| oncology | [29863955](https://pubmed.ncbi.nlm.nih.gov/29863955/) | Atezolizumab for First-Line Treatment of Metastatic Nonsquamous NSCLC. |
| oncology | [31018251](https://pubmed.ncbi.nlm.nih.gov/31018251/) | PD-(L)1 inhibitors vs. chemotherapy vs. their combination in front-line treatment for NSCLC: An indirect comparison. |
| oncology | [35115765](https://pubmed.ncbi.nlm.nih.gov/35115765/) | The Role of Progesterone Receptors in Breast Cancer. |
| oncology | [33198517](https://pubmed.ncbi.nlm.nih.gov/33198517/) | Triple-negative breast cancer: promising prognostic biomarkers currently in development. |
| oncology | [38857504](https://pubmed.ncbi.nlm.nih.gov/38857504/) | Global biomarker trends in triple-negative breast cancer research: a bibliometric analysis. |
| oncology | [36252154](https://pubmed.ncbi.nlm.nih.gov/36252154/) | Treatment of Metastatic Colorectal Cancer: ASCO Guideline. |
| oncology | [27184418](https://pubmed.ncbi.nlm.nih.gov/27184418/) | Pharmacokinetics of metronomic chemotherapy: a neglected but crucial aspect. |
| oncology | [38924756](https://pubmed.ncbi.nlm.nih.gov/38924756/) | Amivantamab plus Lazertinib in Previously Untreated EGFR-Mutated Advanced NSCLC. |
| oncology | [37879444](https://pubmed.ncbi.nlm.nih.gov/37879444/) | Amivantamab plus chemotherapy with and without lazertinib in EGFR-mutant advanced NSCLC after disease progression on osimertinib: primary results from the phase III MARIPOSA-2 study. |
| infectious | [35040920](https://pubmed.ncbi.nlm.nih.gov/35040920/) | Short- vs Standard-Course Outpatient Antibiotic Therapy for Community-Acquired Pneumonia in Children: The SCOUT-CAP Randomized Clinical Trial. |
| infectious | [35505000](https://pubmed.ncbi.nlm.nih.gov/35505000/) | Legionnaires' Disease: Update on Diagnosis and Treatment. |
| infectious | [33683325](https://pubmed.ncbi.nlm.nih.gov/33683325/) | Short-Course Antimicrobial Therapy for Pediatric Community-Acquired Pneumonia: The SAFER Randomized Clinical Trial. |
| infectious | [33650528](https://pubmed.ncbi.nlm.nih.gov/33650528/) | Influenza vaccination: protecting the most vulnerable. |
| infectious | [27494630](https://pubmed.ncbi.nlm.nih.gov/27494630/) | Influenza immunization during pregnancy: Benefits for mother and infant. |
| infectious | [27813430](https://pubmed.ncbi.nlm.nih.gov/27813430/) | Fluzone® High-Dose Influenza Vaccine. |
| infectious | [33301246](https://pubmed.ncbi.nlm.nih.gov/33301246/) | Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine. |
| infectious | [35636910](https://pubmed.ncbi.nlm.nih.gov/35636910/) | COVID-19 Vaccines. |
| infectious | [35263517](https://pubmed.ncbi.nlm.nih.gov/35263517/) | Shorter Treatment for Nonsevere Tuberculosis in African and Indian Children. |
| infectious | [33951360](https://pubmed.ncbi.nlm.nih.gov/33951360/) | Four-Month Rifapentine Regimens with or without Moxifloxacin for Tuberculosis. |

Congelación: `2026-10-06T14:33:13.902114+00:00`. Inicio del baseline: `2026-10-06T14:33:59.363841+00:00`. Los hashes constan en [freeze-v1.json](freeze-v1.json) y el run conserva los mismos hashes de entrada.

## Dataset y juicios previos

Unidad: publicación/PMID, relevancia binaria. Se consideraron todos los 500 pares bajo los criterios explícitos. 26 positivos; las demás etiquetas operacionales son 0, incluidos 13 casos ambiguos. El cero no acredita irrelevancia fuera de esta definición. Nueve queries tienen múltiples relevantes; q06 solo uno. Ninguna está sin positivos.

Los criterios se encuentran en [queries-v1.json](queries-v1.json). Se admiten revisiones y evidencia negativa cuando respondan a la query; no se exige que un tratamiento sea eficaz para que un estudio de eficacia resulte relevante. Adultos y niños son elegibles si la query no restringe edad. q02 admite asma moderada-grave y subfenotipos graves; q07 usa inmunoterapia checkpoint y combinaciones, con la frontera de anticuerpos dirigidos a EGFR marcada para revisión.

### q01 — `association between childhood obesity and asthma risk`

- **Relevante 29627041**: El abstract identifica la obesidad como factor de riesgo de asma en niños y adultos y revisa su epidemiología por edad.
- **Relevante 35988550**: Compara niños con obesidad y peso saludable y afirma mayor riesgo de asma en los primeros.

- **Ambiguo, excluido 34353454**: La revisión trata asma en mujeres y obesidad; enumera infancia entre etapas hormonales, pero no establece el vínculo obesidad infantil-riesgo de asma.

### q02 — `genetic factors associated with severe asthma`

- **Relevante 31090575**: Revisa determinantes genéticos de gravedad e identifica loci GATA3, MUC5AC y KIAA1109 y variantes asociadas a desenlaces más graves.
- **Relevante 30552067**: GWAS de asma moderada-grave con señales de asociación y variantes que regulan mucinas; no se limita a susceptibilidad a asma leve.
- **Relevante 28371335**: Estudia SNPs y asociaciones con asma grave con sensibilización fúngica, comparando asma atópica y controles.

- **Ambiguo, excluido 35988550**: Menciona genética/genómica y mayor gravedad en el fenotipo obeso infantil, pero no identifica una asociación genética con gravedad.
- **Ambiguo, excluido 29627041**: Incluye genética del asma asociada a obesidad y exacerbaciones graves, sin establecer una relación genética-gravedad en el abstract.

### q03 — `effectiveness of metformin for type 2 diabetes`

- **Relevante 27493136**: Ensayo con brazos de metformina sola y combinaciones con empagliflozina; comunica cambios de HbA1c en diabetes tipo 2.
- **Relevante 38763510**: Ensayo con metformina, atorvastatina y combinación que informa cambios de HbA1c y efecto glucémico de metformina en diabetes tipo 2.
- **Relevante 22000494**: La revisión resume eficacia de metformina para tratamiento de diabetes tipo 2, además de prevención y otros mecanismos.


### q04 — `relationship between obesity and insulin resistance`

- **Relevante 28467922**: Explica resistencia a insulina e inflexibilidad metabólica en obesidad y diabetes tipo 2, con mecanismos de metabolismo energético.
- **Relevante 37425065**: Relaciona expansión del tejido adiposo y secreción de adipocinas/citoquinas con inducción de resistencia a insulina.
- **Relevante 34767960**: Revisa directamente obesidad metabólicamente no saludable, resistencia a insulina y mecanismos endocrinos, inflamatorios y de estrés.

- **Ambiguo, excluido 36774932**: La pérdida de peso mejora diabetes y otras complicaciones, pero el abstract no explicita resistencia a insulina ni su relación mecanística con obesidad.

### q05 — `association between hypertension and cardiovascular disease risk`

- **Relevante 29669543**: Revisa la coexistencia de hipertensión y enfermedad cardiovascular en diabetes y el mayor impacto de hipertensión en esta población.
- **Relevante 33793326**: Revisa valoración de riesgo cardiovascular y umbrales/objetivos de presión arterial en hipertensión para prevenir enfermedad cardiovascular y mortalidad.
- **Relevante 37161520**: Relaciona control de hipertensión con prevención de eventos cardiovasculares y comunica reducción del riesgo cardiovascular vinculada a hábitos saludables.
- **Relevante 36519436**: Informa mayor probabilidad de fibrilación auricular en hipertensos y trata reducción de riesgo de fibrilación y complicaciones cardiovasculares con control de presión.

- **Ambiguo, excluido 35653320**: Afirma en la introducción que hipertensión es factor de riesgo cardiovascular y menciona beneficios cardiovasculares al final; el objetivo y desarrollo del abstract son renales, sin detallar la asociación cardiovascular.
- **Ambiguo, excluido 35896123**: Propone estudios futuros que vinculen hipertensión infantil a riesgo cardiovascular adulto; el abstract no ofrece evidencia de ese vínculo.

### q06 — `effect of lifestyle interventions on blood pressure`

- **Relevante 37161520**: Describe intervenciones sobre dieta, sal, ejercicio y peso y comunica reducción de presión sistólica de 3,5 mmHg asociada a hábitos saludables.

- **Ambiguo, excluido 33793326**: Incluye manejo del estilo de vida entre temas de la revisión, pero el abstract no especifica su efecto sobre presión arterial.
- **Ambiguo, excluido 35896123**: Recomienda estrategias centradas en estilo de vida en población pediátrica, sin resultados del efecto en presión arterial.
- **Ambiguo, excluido 36774932**: Describe mejoría de hipertensión tras pérdida de peso, pero mezcla estilo de vida, fármacos y cirugía sin aislar la intervención de estilo de vida.

### q07 — `effectiveness of immunotherapy in non-small-cell lung cancer`

- **Relevante 38512301**: Metaanálisis que compara quimioinmunoterapia neoadyuvante y quimioterapia en NSCLC con supervivencia, respuesta patológica y eventos adversos.
- **Relevante 29863955**: Ensayo de atezolizumab añadido a bevacizumab y quimioterapia en NSCLC con supervivencia global y libre de progresión.
- **Relevante 31018251**: Compara inhibidores PD-1/PD-L1, quimioterapia y combinación en NSCLC con resultados de supervivencia y seguridad.

- **Ambiguo, excluido 38924756**: Amivantamab-lazertinib mejora supervivencia libre de progresión en NSCLC con EGFR mutado, pero el abstract presenta tratamiento dirigido a EGFR y no inmunoterapia checkpoint; excluido según criterio operacional.
- **Ambiguo, excluido 37879444**: Ensayo de amivantamab con quimioterapia y/o lazertinib en NSCLC EGFR mutado; anticuerpo y eficacia no bastan para clasificarlo como inmunoterapia checkpoint.

### q08 — `biomarkers associated with breast cancer prognosis`

- **Relevante 35115765**: Identifica el receptor de progesterona como biomarcador pronóstico y asocia expresión alta con tumores de mejor pronóstico basal.
- **Relevante 33198517**: Revisa biomarcadores pronósticos establecidos y en desarrollo en cáncer de mama triple negativo y enumera candidatos concretos.

- **Ambiguo, excluido 38857504**: Analiza tendencias y redes de investigación de biomarcadores de TNBC, pero no establece qué marcadores se asocian con pronóstico ni sus resultados clínicos.

### q09 — `antibiotic treatment outcomes in community-acquired pneumonia`

- **Relevante 35040920**: SCOUT-CAP compara 5 frente a 10 días de antibióticos en neumonía comunitaria pediátrica con respuesta clínica, efectos adversos y resistencia.
- **Relevante 33683325**: SAFER compara 5 frente a 10 días de amoxicilina en neumonía comunitaria pediátrica con tasas de curación clínica.
- **Relevante 35505000**: Revisión de neumonía por Legionella que vincula terapia antibiótica inadecuada o tardía con peor pronóstico y aborda tratamiento empírico de neumonía comunitaria grave; evidencia principalmente observacional.


### q10 — `effectiveness of influenza vaccination in older adults`

- **Relevante 33650528**: Revisa baja efectividad de vacunas de influenza en personas mayores por inmunosenescencia y estrategias de dosis alta o adyuvantes.
- **Relevante 27813430**: Resume estudios de vacuna de influenza de dosis alta en mayores de 65 años con protección frente a influenza y hospitalizaciones frente a dosis estándar.

- **Ambiguo, excluido 27494630**: El foco es vacunación materna y protección del recién nacido; compara brevemente eficacia con mayores, sin evaluar efectividad en esa población.

## Métricas implementadas y resultados

Hit Rate@5: presencia de al menos un positivo. Recall@5: positivos en top-5 / positivos del corpus para esa query. Precision@5: positivos en top-5 / 5. MRR: media de 1 / puesto del primer positivo en ranking completo de 50. Medias macro, sin NDCG. Política para ausencia de positivos, rankings cortos y duplicados en el [runbook](README.md#juicios-y-métricas).

**Baseline real: Hit Rate@5 1,00; Recall@5 0,975; Precision@5 0,50; MRR 1,00.** 25 de 26 pares relevantes aparecen en top-5. Recall macro no es el mismo cálculo que 25/26 (micro).

| Query | Positivos | Hit@5 | Recall@5 | Precision@5 | RR | Top-5 PMIDs, en orden |
| --- | --- | --- | --- | --- | --- | --- |
| q01 | 2 | 1.00 | 1.00 | 0.40 | 1.00 | 35988550, 29627041, 34353454, 31090575, 30552067 |
| q02 | 3 | 1.00 | 1.00 | 0.60 | 1.00 | 31090575, 30552067, 28371335, 29627041, 35988550 |
| q03 | 3 | 1.00 | 1.00 | 0.60 | 1.00 | 22000494, 38763510, 27493136, 29669543, 36774932 |
| q04 | 3 | 1.00 | 1.00 | 0.60 | 1.00 | 34767960, 37425065, 28292619, 28467922, 29627041 |
| q05 | 4 | 1.00 | 0.75 | 0.60 | 1.00 | 33793326, 38141902, 37161520, 29669543, 35653320 |
| q06 | 1 | 1.00 | 1.00 | 0.20 | 1.00 | 37161520, 33793326, 35896123, 36774932, 36519436 |
| q07 | 3 | 1.00 | 1.00 | 0.60 | 1.00 | 38512301, 31018251, 29863955, 38924756, 37879444 |
| q08 | 2 | 1.00 | 1.00 | 0.40 | 1.00 | 33198517, 35115765, 38857504, 29863955, 38924756 |
| q09 | 3 | 1.00 | 1.00 | 0.60 | 1.00 | 35040920, 33683325, 35505000, 33951360, 35263517 |
| q10 | 2 | 1.00 | 1.00 | 0.40 | 1.00 | 33650528, 27813430, 27494630, 33301246, 35040920 |

[baseline-v1.json](baseline-v1.json) guarda los 500 puestos, sus scores, PMID, unit_id, fingerprint, relevancia y top-5. Configuración efectiva:

- `whole-publication-v1`; Article Encoder `ncbi/MedCPT-Article-Encoder`, revisión `d05a736da4bb84ee4057b7f7999485be6ed85465`.
- Query Encoder `ncbi/MedCPT-Query-Encoder`, revisión `d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc`.
- 768 dimensiones; CLS; par título/abstract; vectores sin normalizar; dot product exacto en pgvector; desempate por unit_id.
- `top_k=5`, sin filtro temporal; ranking completo únicamente para MRR y diagnóstico, con el mismo vector de query.
- Truncamiento longest-first: 512 tokens para artículo y 64 para query, incluidos tokens especiales. La unidad conserva el abstract entero.
- CPU, float32, 4 hilos de cómputo. Paquetes y versiones de PostgreSQL/pgvector en el run. Commit base más estado dirty y hashes fuente; pendiente de versionar tras revisión.

## Análisis de errores

**Aciertos claros.** q01 recupera primero 35988550 y segundo 29627041: sus abstracts vinculan obesidad infantil con riesgo de asma. q02 pone en los primeros tres puestos los tres textos de genética de gravedad; q09 ordena primero SCOUT-CAP (35040920) y segundo SAFER (33683325), con resultados explícitos de antibióticos en neumonía comunitaria.

**Falsos positivos según estos juicios.** En q05, 38141902 aparece segundo (score 61,8988), casi empatado con el positivo 33793326 (61,9050): analiza salud periodontal como exposición principal, no el vínculo hipertensión-riesgo cardiovascular. En q04, 28292619 aparece tercero: obesidad e infertilidad comparten términos metabólicos, pero el abstract no establece la relación con resistencia a insulina. En q09 los ensayos de tuberculosis 33951360 y 35263517 ocupan puestos 4 y 5: antibióticos y desenlaces próximos temáticamente, otra enfermedad. Estas interpretaciones proceden de los abstracts; la coincidencia temática es una causa plausible, no un mecanismo interno demostrado.

**Relevantes demasiado abajo.** En q04, 28467922 queda cuarto, por debajo del distractor sobre infertilidad; su título sobre flexibilidad metabólica es menos literal aunque el abstract sí responde al vínculo. Se recupera dentro de top-5, pero tiene margen de ordenación. En q05, 36519436 queda séptimo (59,4640), detrás de documentos centrados en otros riesgos o en riñón.

**Relevante no recuperado en top-5.** Ese PMID 36519436 es el único positivo fuera del corte: vincula hipertensión con mayor probabilidad de fibrilación auricular y prevención de complicaciones cardiovasculares. q05 cubre 3/4 positivos (Recall@5 0,75). La especificidad de “atrial fibrillation” frente a “cardiovascular disease risk” y el solapamiento lexical de distractores son hipótesis. No hay positivos ausentes del ranking completo: la búsqueda es exacta y devuelve los 50 candidatos.

**Ambigüedad recuperada.** q01 incluye en el puesto 3 una revisión de asma en mujeres (34353454); infancia, obesidad y asma aparecen, pero falta el vínculo solicitado. q06 devuelve recomendaciones sin efecto explícito en puestos 2–4. q07 devuelve anticuerpos dirigidos a EGFR en puestos 4–5: la etiqueta depende de la definición checkpoint usada, que debe revisarse. q08 pone tercero el estudio bibliométrico 38857504: biomarcadores y pronóstico son su contexto, pero no demuestra relaciones pronósticas. q10 pone tercero la revisión sobre embarazo (27494630), con una comparación breve con mayores. Son ceros conservadores, no falsos positivos clínicamente resueltos.

## Limitaciones del dataset

- Selección deliberadamente guiada por las queries y por relevancia de PubMed; documentos cercanos y títulos literales favorecen altas métricas. No es muestra representativa ni conjunto de test independiente para optimizar modelos.
- Solo 50 publicaciones, cinco áreas, inglés y rango 2000–2024. Muchas revisiones y pocos estudios específicos en algunos temas; un solo relevante en q06 hace su Recall poco discriminativo.
- Con 26 positivos y K=5, el máximo Precision macro posible aquí es 26/50 = 0,52. Observar 0,50 refleja también esa composición; no equivale a que la mitad de PubMed sea recuperada mal. Los 13 pares ambiguos pueden cambiar números tras revisión.
- Un único anotador asistido, sin consenso experto ni medición de acuerdo. Los criterios distinguen asociación genética de gravedad, recomendaciones frente a efectos y checkpoint frente a tratamientos dirigidos; otras definiciones legítimas exigirían otra versión.
- Solo título/abstract normalizados. No se evalúan texto completo, calidad de estudio, causalidad, certeza de evidencia ni aplicabilidad clínica. Truncamiento del encoder puede omitir partes; no se ha medido su contribución a cada error.
- Ranking exacto en un corpus diminuto, sin evaluación de escala, latencia de servicio ni filtros temporales. Hit Rate y MRR perfectos no informan del resto del ranking ni de generación o veracidad.
- No se ha modificado ninguna etiqueta después de inferencia. Revisarlas implica versionar y recalcular de manera consistente, conservando este baseline histórico.

## Tests y validaciones

- Suite completa: **321 passed**. Tras añadir auditoría de artefactos y casos de dataset inválido, suite afectada: **16 passed**, con las dos DeprecationWarning conocidas de Starlette/AnyIO y google-genai. Sin llamadas a modelos en tests.
- Cálculos con rankings conocidos, positivo situado sexto para distinguir MRR de MRR@5, ranking vacío/corto, ausencia de positivos, macro con denominadores distintos y rechazo de duplicados/K inválido.
- Runner con encoder doble y PostgreSQL de pruebas: corpus aislado, top-5 y ranking completo, una codificación por query, preservación de tablas previas, limpieza, rechazo de sobrescritura y artefacto fallido sin agregado.
- Validación de hashes antes de inferir y de consistencia semántica del dataset. Auditoría determinista del baseline guardado: congelación anterior al run, cobertura de rankings, etiquetas, scores ordenados y métricas recalculadas.
- Resultado real completo: 50 artículos indexados y 10 queries; esquema de evaluación eliminado. Procedimiento reproducible en el [runbook](README.md#ejecutar-y-reproducir).

`git diff --check` sin incidencias; hashes del código fuente coincidentes con los registrados por el baseline; los tests del cálculo no son evidencia de calidad biomédica.
