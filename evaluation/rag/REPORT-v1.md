# Baseline RAG v1 — informe de M8 / #47

Run `a8b78e1c-02c4-4e8d-964d-9823f6d8b741`, proveedor/modelo
`deepseek / deepseek-flash`, dataset `rag-m8-v1`, corpus `pubmed-m7-v1`.
Diez casos ejecutados una vez, sin retries ni fallback: estado `complete`,
10 éxitos técnicos, 0 errores técnicos y 2 abstenciones (r07/r08).

El desarrollador aprobó expresamente los 60 juicios tras la revisión humana
asistida: **58 pass, 0 fail y 2 not_applicable**. Se registran esos juicios;
este informe no introduce un evaluador automático ni una segunda revisión experta.
El baseline se promocionó localmente antes de su entrega en Git/GitHub.

## Artefactos e integridad

- [Baseline](baseline-v1.json): copia byte por byte del run histórico original,
  incluidas respuestas, fuentes, ranking, contexto efectivo y diagnósticos.
- [Revisión humana](baseline-v1.review.json): identifica revisor, dataset y hash
  canónico del run; 60 pares caso/dimensión únicos, completos y con N/A motivados.
- [Agregado reproducible](baseline-v1.aggregate.json): salida del comando existente.
- [Observaciones aprobadas](baseline-v1.observations.json): las diez observaciones
  suministradas por el desarrollador, separadas de etiquetas y respuestas.
- [Procedencia](baseline-v1.provenance.json): hashes del run, revisión, agregado,
  entradas y archivo de código. [Snapshot de entradas/código](baseline-v1.inputs-and-code.tar.gz):
  conserva todos los módulos del run y uv.lock con sus hashes, incluso con árbol
  dirty, además de corpus/dataset/freeze. No contiene .env ni credenciales.

SHA-256 del run original/promocionado:
`19de1fd5fea10409e026538b492598191c540b369de5c0cf2ac7d409e6375329`.
Las comprobaciones de completitud, identidades, texto/fingerprint de fuentes,
partición de contexto, citas y respuesta final pasan. El replay de validación
usa exclusivamente datos guardados; no llama a un modelo ni repite retrieval real.
Los hashes de las fuentes archivadas coinciden con `source_sha256` del run.
Ni el run original ni las etiquetas, evidencia o respuestas se han modificado.

## Calidad de generación: revisión humana aprobada

La unidad es la respuesta completa, incluyendo answer y limitations. N/A no es
pass ni fail y se mantiene fuera del denominador de juicios aplicables. Los diez
casos no presentan dimensiones fallidas; dos contienen una dimensión no aplicable.
No se transforma ese resultado en una puntuación clínica o un score compuesto.

| Dimensión | Pass | Fail | N/A |
| --- | ---: | ---: | ---: |
| Groundedness | 10 | 0 | 0 |
| Corrección semántica de citas | 8 | 0 | 2 |
| Relevancia | 10 | 0 | 0 |
| Afirmaciones sin apoyo | 10 | 0 | 0 |
| Abstención apropiada | 10 | 0 | 0 |
| Limitaciones | 10 | 0 | 0 |
| Total | 58 | 0 | 2 |

| Caso | Escenario previo | Pass | Fail | N/A | Primer anclaje en top-5 |
| --- | --- | ---: | ---: | ---: | ---: |
| r01 | Suficiente | 6 | 0 | 0 | 2 |
| r02 | Suficiente | 6 | 0 | 0 | 1 |
| r03 | Suficiente | 6 | 0 | 0 | 1 |
| r04 | Suficiente | 6 | 0 | 0 | 3 |
| r05 | Parcial | 6 | 0 | 0 | 2 |
| r06 | Parcial | 6 | 0 | 0 | 1 |
| r07 | Ausente | 5 | 0 | 1 | Sin positivos esperados |
| r08 | Ausente | 5 | 0 | 1 | Sin positivos esperados |
| r09 | Distractores plausibles | 6 | 0 | 0 | 2 |
| r10 | Distractores plausibles | 6 | 0 | 0 | Sin positivos esperados |

En r07/r08 solo `citation_semantics` es N/A: son abstenciones exactas sin citas.
La abstención justificada aprueba las otras cinco dimensiones. r10 es una
respuesta negativa fundamentada, con citas evaluables y seis pass; no se exige
una respuesta positiva para aprobar.

## Retrieval y contexto: interpretación separada

Medias macro sobre **los siete casos con anclajes positivos previos**
(r01–r06 y r09). Se reutilizan las métricas M7 sobre esos anclajes, sin afirmar
que las etiquetas cubran toda relevancia documental posible.

| Métrica sobre anclajes | Valor | Denominador/alcance |
| --- | ---: | --- |
| Hit Rate@5 | 1,0000 | 7/7 casos con algún anclaje en top-5 |
| Recall@5 | 1,0000 | Todos los anclajes esperados de esos siete casos |
| Precision@5 | 0,2286 | Media de anclajes encontrados / 5; ocho anclajes en 35 puestos |
| MRR limitado a top-5 | 0,6905 | Media de reciprocal rank de esos siete casos, profundidad 5 |
| Casos con anclajes no recuperados | 0 | Solo casos con anclajes previos |
| Casos con pérdida de anclajes por presupuesto | 0 | Recuperados frente a contexto efectivo |
| Fuentes omitidas por presupuesto | 0 | Los 50 resultados (cinco por caso) cupieron |

El campo histórico `mrr` del agregado tiene aquí profundidad cinco; no es el MRR
sobre ranking completo de 50 publicaciones de M7. Las preguntas r07, r08 y r10
carecen de positivos esperados para la parte solicitada. Su recall individual es
null y sus ceros en otros campos del run son valores convencionales del cálculo;
no representan fallos convencionales de recuperación ni entran en estas medias.

Precision baja sobre anclajes **no** significa que el 77,14% de los documentos
sean biomédicamente irrelevantes: una revisión complementaria o un ensayo vecino
puede ayudar a matizar o rechazar una extrapolación. Tampoco el recall perfecto
prueba suficiencia factual, ausencia de distractores o calidad de generación.
En r09 el ensayo de rifapentina-moxifloxacino ayuda a distinguir regímenes aunque
no esté etiquetado como anclaje positivo; r10 usa ENHANCE para negar la extrapolación
a asma sin que eso cree un positivo nuevo después de observar la respuesta.
Las etiquetas originales se conservan para comparaciones futuras.

## Análisis de errores y observaciones acordadas

No hubo fallos operativos, pérdidas de contexto ni fallos de contenido según
los juicios aprobados. Las siguientes observaciones se conservan como límites
y puntos de inspección, sin convertirlos retrospectivamente en fail ni modificar
respuestas/etiquetas para mejorar el resultado.

| Caso | Observación y alcance |
| --- | --- |
| r01 | Se recuperan documentos irrelevantes para la pregunta: hipertensión infantil y TB, además de las dos revisiones pertinentes en puestos 2/3. La respuesta utiliza estas últimas. El resultado humano aprobado no implica que el ranking sea limpio. |
| r02 | El GWAS refiere 24 señales y la revisión 25 loci. La respuesta atribuye ambos recuentos a sus fuentes. No se resuelve la discrepancia ni se asume que «señal» y «locus» sean unidades idénticas. |
| r03 | Conviene expresar cambios de HbA1c en puntos porcentuales. La respuesta original utiliza %, como el abstract; se conserva el pass aprobado y se registra la ambigüedad potencial frente a reducción relativa. |
| r04 | El artículo correcto está en tercera posición y se cita como S3; dos ensayos de TB lo preceden. Cobertura de evidencia y calidad del orden son propiedades distintas. |
| r05 | Distingue correctamente PATHWAY fase 2b de NAVIGATOR fase 3 y reconoce que las fuentes no incluyen los resultados finales de NAVIGATOR. |
| r06 | Debe distinguirse claramente la eficacia neonatal general del subgrupo de prematuros menores de 32 semanas. La revisión aprobada acepta la respuesta que declara la ausencia de estimación específica; el 50% general no etiqueta ese subgrupo. |
| r07 | Abstención correcta pese al retrieval poco útil. No hay anclajes positivos para el ensayo CRISPR solicitado; no se penaliza como recuperación convencional fallida. |
| r08 | Abstención correcta al pedir una dosis individual, aunque con utilidad clínica limitada. El sistema no da una prescripción y no se modifica para añadirla. |
| r09 | Distingue correctamente los ensayos y sus condiciones. La utilidad del ensayo vecino pone de manifiesto límites de las etiquetas de relevancia/anclajes; no autoriza reetiquetar tras observar el output. |
| r10 | Distingue correctamente EPOC y asma grave. La respuesta negativa fundamentada no equivale a probar ineficacia de ensifentrina en asma. |

## Investigación de las abstenciones

`generated` es la salida tipada del modelo antes del procesamiento de aplicación;
`output` es la respuesta final del servicio. D026, sección «Abstención y salida»,
exige la frase fija de abstención con `limitations=[]` al modelo. Cualquier prosa
adicional en ese campo invalidaría esa forma sin citas, evitando esconder
contenido biomédico no citado. Tras validar, RagService añade la limitación
operacional `Las fuentes proporcionadas no permiten responder a la pregunta.`
y conserva las fuentes incluidas.

Eso ocurre exactamente en r07/r08: generated.limitations vacío y output.limitations
con una explicación. Es normalización intencionada y compatible con el contrato,
no una pérdida de respuesta ni una reparación de citas inválidas. No se modifica
el código, la salida del modelo ni el artefacto histórico. La validación por replay
y los tests existentes de abstención verifican esta transformación.

## Reproducir el informe sin inferencias

Desde la raíz, con las dependencias ya instaladas:

```bash
uv run --locked --offline --no-sync python -m evidenceops.rag_evaluation aggregate \
  evaluation/rag/baseline-v1.json evaluation/rag/baseline-v1.review.json \
  > /tmp/rag-v1-aggregate.json
cmp evaluation/rag/baseline-v1.aggregate.json /tmp/rag-v1-aggregate.json
uv run --locked --offline --no-sync pytest tests/test_rag_baseline.py
```

No se vuelve a ejecutar `run --live` ni se construye un nuevo juicio para
reproducir los números. El JSON agregado incluye resultados individuales y
fallos con motivos; este Markdown interpreta esos resultados y las observaciones
acordadas. La revisión corresponde al mismo dataset exacto y hash canónico del run.
Para comparaciones futuras, usar el comando `compare` del [runbook](README.md)
con una revisión completa de un candidato autorizado y el mismo dataset/corpus;
mostrar regresiones, mejoras y cambios de aplicabilidad separadamente.

## Límites y cierre

Diez preguntas preparadas, corpus cerrado de 50 publicaciones, títulos/abstracts
y revisión humana asistida sin consenso clínico experto. No hay estimación de
acuerdo entre revisores, muestra independiente, evaluación por afirmación ni
validación factual automática. Cero fail en esta muestra no demuestra fiabilidad
clínica, ausencia universal de alucinaciones ni generalización a otras preguntas.
El baseline referencia el sistema/juicios de esta corrida, no una respuesta ideal.

Las preguntas españolas se ejecutaron sin traducción ni reescritura para MedCPT.
El modelo remoto se identifica por el alias configurado y los hashes identifican
el código local; no se promete identidad de respuestas en futuras ejecuciones.
La excepción autorizada de uso de saldo recargado se consumió en esta única
corrida. La diferencia de saldo visible fue 0,00 USD a la precisión del endpoint,
lo que no demuestra coste facturado cero. No se han hecho nuevas consultas de
saldo ni inferencias para este cierre.

El trabajo de #47 queda terminado con baseline revisado/promocionado,
observaciones registradas y mecanismo reproducible. Git/GitHub es la fuente del
estado de entrega e integración posterior a esta promoción. M8 solo se considera
entregado al integrar los cambios y cerrar sus issues correspondientes.
M9 requiere su propio encargo y alcance según el roadmap; podrá comparar candidatos
contra esta referencia sin cambiar retrospectivamente los juicios previos. No se
ha implementado BM25, híbrido, reranking ni query rewriting en #47.
