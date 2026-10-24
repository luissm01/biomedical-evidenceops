# Evaluación RAG v1 — M8 / #47

Estado: **baseline RAG v1 revisado y promocionado**.
[Informe](REPORT-v1.md), [baseline](baseline-v1.json),
[revisión humana](baseline-v1.review.json), [agregado](baseline-v1.aggregate.json)
y [procedencia/código archivado](baseline-v1.provenance.json).
Run `a8b78e1c-02c4-4e8d-964d-9823f6d8b741`: diez éxitos técnicos,
58 pass, 0 fail y 2 N/A aprobados expresamente por el desarrollador tras revisión
humana asistida. No es consenso clínico experto ni certificación biomédica.
El desarrollador aprobó los diez casos el 2026-10-24, con la corrección de r09
para no asumir un régimen exclusivamente adulto: [casos](CASES-v1.md),
[dataset](cases-v1.json). La [auditoría del corpus completo](LABEL_AUDIT-v1.md)
confirma las clasificaciones, especialmente los escenarios parciales r05/r06.
El desarrollador autorizó excepcionalmente una única corrida con saldo recargado
de DeepSeek; esa autorización ya se consumió. No hubo reintentos ni fallback.
Cualquier nueva corrida requiere nueva autorización. Los diez outputs ya tienen
revisión humana aprobada, preservada separadamente del run y las etiquetas.

## Método y entradas

Se juzga la **respuesta completa**, incluyendo answer y limitations; no se
segmenta en afirmaciones ni se introduce un modelo juez. Se reutilizan las
revisiones, hashes de contenido y transiciones M4, el corpus congelado de 50
publicaciones M7 y sus mecanismos de indexación/aislamiento y métricas. No se
reutilizan automáticamente los juicios M7: aquellas queries medían relevancia
para otro objetivo; estos casos miden evidencia para una respuesta concreta.
No hay adquisición nueva, bibliografía externa, estrategias M9 ni dependencias
nuevas. Las preguntas están en español tal como se ejecutarán; el runner no las
traduce ni reescribe para MedCPT.

`cases-v1.json` separa cuatro escenarios suficientes, dos parciales, dos ausentes
y dos con distractores plausibles. La clasificación describe el **corpus**, no
el contexto que se espera que recupere el sistema. Puede haber evidencia en el
corpus y faltar en top-5. Cada caso contiene fuentes con PMID/URL, extractos del
abstract congelado, justificación, hechos, conducta esperada y errores a evitar.
Son anotaciones asistidas aprobadas para este ejercicio; no revisión experta acreditada. Ausencia significa
que esos abstracts no permiten responder, no ausencia de evidencia en PubMed.

`expected_pmids` son anclas documentales que apoyan la parte respondible;
`related_pmids` son fuentes complementarias o vecinas útiles para revisar el
escenario, y **no** negativos automáticos. Los anclajes no equivalen a juicios
exhaustivos de relevancia de 500 pares. Las métricas deterministas cuantifican
cobertura de estos anclajes, no toda la evidencia relevante ni suficiencia
semántica. Para casos sin anclajes, recall es indefinido; se excluyen de las
medias de cobertura. No se puntúa un caso ausente como fallo de retrieval.

`freeze-v1.json` fija hashes de dataset y corpus antes de las respuestas. Se
validan también los hashes M7 sin modificar sus artefactos. Para revisar las
etiquetas, leer los abstracts originales en
[corpus-v1.json](../retrieval/corpus-v1.json) y contrastar la tabla de casos.
Si la revisión previa cambia etiquetas, preguntas o rúbrica, actualizar dataset,
tabla y freeze **antes de inferir**, dejando explícita la revisión realizada.
Tras observar outputs, conservar v1 y crear una nueva versión; ambos runs de
cualquier comparación deben corresponder al mismo archivo exacto. No ajustar
etiquetas retrospectivamente para mejorar un resultado.

## Rúbrica humana

Los seis juicios se aplican a cada respuesta completa (60 pares caso/dimensión).
Leer primero pregunta, fuentes de referencia y conducta esperada; después
retrieved, context.sources, context.omitted, generated y output del run.
No confundir fuentes recuperadas con fuentes efectivamente vistas por el modelo.

| Dimensión | Pass | Fail |
| --- | --- | --- |
| `groundedness` | La síntesis se sostiene en el contexto efectivo y respeta resultados, población, comparador, endpoint y grado de evidencia. | Distorsiona evidencia o presenta conclusiones que el contexto no sostiene, aunque sean plausibles fuera de él. |
| `citation_semantics` | Las fuentes citadas respaldan el sentido de la respuesta y sus limitaciones; ninguna cita clave apunta a otra población, intervención o resultado. | Una cita existente y bien formada no apoya lo que se le atribuye. |
| `relevance` | Responde a lo preguntado con la parte apoyada disponible y distingue lo que falta. | Evasión, contenido irrelevante, omisión central o abstención global teniendo evidencia suficiente para responder. |
| `unsupported_claims` | No introduce cifras, causalidad, eficacia, seguridad ni recomendaciones que excedan el contexto. | Añade al menos una afirmación sustantiva sin apoyo, incluida extrapolación de distractores. |
| `abstention` | Responde cuando puede; en evidencia parcial responde lo apoyado y reconoce lo ausente; se abstiene cuando el contexto no permite responder. | Inventa una respuesta con evidencia ausente o se abstiene injustificadamente. |
| `limitations` | Expresa los límites relevantes (abstracts, seguimiento, subgrupo ausente, incertidumbre y aplicabilidad) sin falsa seguridad ni consejo individual. | Omite un límite que cambia la interpretación o añade seguridad/recomendación injustificada. |

`pass` y `fail` son juicios semánticos, nunca matching textual. Todo fail requiere
`notes` con el problema y la evidencia que lo contradice o falta. Pueden fallar
varias dimensiones por el mismo problema: no se suman como errores independientes.
`not_applicable` requiere motivo y solo se admite en `citation_semantics` para la
abstención exacta D026, sin afirmaciones sustantivas citadas. El resto sigue siendo
aplicable: una abstención prudente puede pasar groundedness/unsupported_claims y
fallar relevancia si evita una pregunta respondible. Una abstención justificada
ante evidencia ausente puede aprobar también relevancia, abstention y limitations.
Una respuesta negativa fundamentada (r10: ENHANCE estudió EPOC y no demuestra
eficacia en asma) puede aprobar las seis dimensiones; no se exige una conclusión
positiva ni se debe convertir ausencia de prueba en prueba de ineficacia. La limitación operacional añadida por la aplicación se valora
como tal, sin exigirle una cita. Null significa pendiente, nunca pass ni N/A.

Juzgar fidelidad al contexto separadamente de cobertura end-to-end: una abstención
puede ser adecuada al contexto recibido, pero no satisfacer una pregunta respondible
con el corpus. Usar `expected_not_retrieved` y `expected_lost_from_context` para
localizar el problema y anotarlo en notes con origen retrieval/context/generation
o indeterminado. Un anclaje ausente es una señal de diagnóstico; no prueba por sí
solo el origen de un fallo semántico. Un revisor debe valorar fuentes alternativas.

## Ejecutar una corrida real pequeña (requiere autorización nueva)

Requisitos: dependencias del [README principal](../../README.md), extra `medcpt`,
PostgreSQL con pgvector y permisos de creación de esquema, configuración del
proveedor ya elegido y **cuota gratuita disponible**. No cambiar proveedor para
sortear cuotas. Las inferencias de pago requieren autorización explícita: la
excepción ya ejecutada no autoriza consumo adicional. `--live` consume cuota LLM y ejecuta MedCPT
local (puede descargar pesos fijados); no ejecutarlo solo para probar el mecanismo.

```bash
uv sync --locked --dev --extra medcpt
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  uv run --locked --offline --extra medcpt \
  python -m evidenceops.rag_evaluation run --live \
  --dataset evaluation/rag/cases-v1.json --output-dir evaluation/runs/rag
```

Preparación comprobada el 2026-10-24, sin inferencia:

- El contenedor existente `evidenceops-postgres-1` estaba detenido. Se arrancó con
  `docker.exe start evidenceops-postgres-1` desde WSL, conservando volumen y datos;
  el comando Linux `docker` sigue sin integración WSL. PostgreSQL 18.6, pgvector
  0.8.7 y permiso CREATE confirmados. Las dos integraciones antes fallidas pasan.
- `uv sync --locked --dev --extra medcpt --offline` completado. Ambos snapshots
  fijados de MedCPT contienen tokenizers/configuración y pesos safetensors legibles,
  con dimensión 768. Se comprobaron offline sin cargar encoders ni ejecutar forward.
  Por eso el comando preparado usa las cachés locales y evita descargas.
- Configuración efectiva: `deepseek / deepseek-flash`, 2.048 tokens máximos de
  salida por caso y timeout de transporte de 60 segundos. Clave presente, sin
  mostrarla. No se han comprobado autenticación remota ni disponibilidad del modelo
  con la cuenta durante la preparación. La única corrida posterior autorizada
  terminó con diez resultados estructuralmente válidos.
- El endpoint oficial de saldo se consultó antes y después de la corrida
  excepcional autorizada: disponible, 0,00 USD concedidos y 1,99 USD recargados
  en ambas consultas. La diferencia visible es 0,00 USD; dos decimales o un
  cargo diferido pueden ocultar consumo. No significa inferencia gratuita.
  Recibos y resumen en `evaluation/runs/rag/authorization-2026-10-24/`.
  El comando no impone límite monetario ni verifica saldo por sí mismo.
  Para ejecuciones futuras, confirmar gratuidad o autorización expresa de pago;
  no cambiar de proveedor ni recargar para eludir ese límite.
- Una sola ejecución de diez casos: como máximo diez llamadas DeepSeek, una por
  caso con contexto; ninguna si se abstiene localmente sin fuentes. No hay retry
  del adapter DeepSeek ni del runner. El máximo de salida solicitado suma 20.480
  tokens, además de los tokens de entrada; no es una estimación de consumo real.
  El timeout no garantiza una duración total máxima de diez minutos.

Se ejecutan los diez casos secuencialmente mediante **RagService real**, fuera del
transporte HTTP. Se indexa solo el snapshot M7 en un esquema aleatorio aislado con
el mismo context manager de M7; se elimina al salir. Las tablas de desarrollo no
se usan. Una terminación abrupta puede dejar `retrieval_eval_*`; inspeccionarlo
antes de limpiar. Las pruebas HTTP existentes cubren el contrato de transporte.

El runner no envía etiquetas ni rúbrica al generador. Observa el contexto que el
servicio construye y las salidas tipadas del generador antes de validar citas;
no repite retrieval ni generación para diagnosticarlos. Sin fuentes incluidas,
la abstención local no invoca al proveedor. No hay retries ni reanudación del
runner. Se conserva la política del adapter: Gemini puede reintentar determinados
fallos una vez; DeepSeek no reintenta. El timeout es de transporte, no un deadline
total, y un retry del adapter podría consumir cuota adicional.

Cada run nuevo se guarda en `evaluation/runs/rag/<UUID>.json` (ignorado por Git),
con checkpoint atómico después de cada caso. `--output-dir` cambia el directorio.
Conserva UUID, tiempos UTC, proveedor/modelo y límites efectivos, commit/dirty,
hashes de fuentes y lock, versiones de Python/paquetes/DB/pgvector, configuración
MedCPT y revisiones, top-k, filtro por caso, instrucciones completas y presupuesto.
Un árbol dirty requiere conservar el código local: hashes identifican, pero no
reconstruyen los archivos. Un baseline reproducible debe acompañarse del código
revisado/versionado, sin que el comando haga commits automáticamente.

Por caso: pregunta, ranking top-5 con unidades/identidad/fingerprint/score,
contexto exacto serializado, fuentes incluidas/omitidas y correspondencia S1…Sn,
respuesta tipada original si existe, respuesta final de aplicación, abstención,
errores seguros y diagnóstico de cobertura. No se guardan claves, URLs de DB,
mensajes arbitrarios de excepción ni cuerpos brutos de errores del proveedor.
La información biomédica pública y las respuestas se guardan en el artefacto,
no en logs de aplicación.

Errores de DB/indexación/limpieza quedan como error de infraestructura; los de
cada caso distinguen retrieval, context, generation y citations, con causa segura.
Un error de citas conserva el output tipado rechazado y el diagnóstico D027;
un fallo de esquema del adapter puede no disponer de output tipado. Los errores
ordinarios de casos no impiden registrar los restantes. Una interrupción deja
`running` con checkpoints: no es un run completo. Errores técnicos no se convierten
en juicios fail de calidad. No repetir llamadas solo para obtener un baseline
exitoso: diagnosticar el artefacto y acordar el siguiente intento.

## Inspección, revisión y baseline

Sustituir `<run>` por el archivo existente impreso. Los siguientes comandos no
usan DB, modelos ni red:

```bash
uv run --locked python -m evidenceops.rag_evaluation inspect <run>
uv run --locked python -m evidenceops.rag_evaluation prepare \
  <run> evaluation/runs/rag/review.json
```

`inspect` admite runs fallidos o interrumpidos y expone errores y diagnósticos por
caso. La cobertura agregada excluye errores de retrieval y casos sin anclajes;
reciprocal rank queda limitado al top-5, no es el MRR a profundidad 50 de M7.
Un caso puede tener a la vez anclajes no recuperados y otros perdidos por presupuesto.

`prepare`, `aggregate`, `compare` y `promote` exigen todos los casos en orden,
preguntas/hashes exactos, éxito técnico, estado complete y trazas coherentes.
Se reconstruyen unidades desde el corpus para comprobar identidad y texto, el
contexto desde el ranking, las citas con el validador D026 y la respuesta final
mediante replay local de la orquestación guardada. No se infiere ni se evalúa
semántica automáticamente. Estas comprobaciones detectan inconsistencias de
artefactos; no son una firma ni prueban la ejecución de una llamada externa.

La revisión (`review_version: rag-1`) se prepara **vacía**. Abrirla junto al run y el dataset; completar
reviewer y los 60 veredictos, con motivos para fail/N/A. No cambiar hashes, pares,
run ni dataset. Un borrador incompleto no se agrega ni se promociona.

```bash
uv run --locked python -m evidenceops.rag_evaluation aggregate \
  <run> evaluation/runs/rag/review.json
uv run --locked python -m evidenceops.rag_evaluation promote \
  <run> evaluation/runs/rag/review.json evaluation/rag/baseline-v1.json
```

La promoción exige revisión humana completa vinculada al hash canónico del run.
Copia el run y `baseline-v1.review.json` sin modificar contenido ni sobrescribir.
Un baseline puede contener juicios fail: establece una referencia, no certifica
calidad biomédica. Un run incompleto/con errores nunca puede promocionarse.
El baseline actual es real, revisado y promocionado; no repetir la promoción
a ese destino ni sobrescribir sus artefactos. Los comandos con `<run>` son
procedimiento para futuros runs autorizados, no trabajo pendiente sobre v1.

Para una comparación posterior, ejecutar un candidato con el mismo dataset y
corpus congelados, preparar y completar su revisión y comparar:

```bash
uv run --locked python -m evidenceops.rag_evaluation compare \
  evaluation/rag/baseline-v1.json evaluation/rag/baseline-v1.review.json \
  <candidate-run> <candidate-review>
```

`aggregate` presenta pass/fail/N/A globales y por dimensión, casos sin fallos,
fallos con motivos y resultados individuales, junto a cobertura y pérdidas.
No hay score compuesto ni umbral clínico. `compare` muestra mejoras y regresiones
por par, sin compensarlas, cambios de aplicabilidad y N/A estables, diagnósticos
por caso y configuraciones de ambos runs. Cambiar pass/fail a N/A no es mejora.
Cambios de aplicabilidad requieren inspección humana. Totales iguales pueden
ocultar regresiones. Todos aceptan `--dataset <archivo>` y usan su freeze vecino.

Salidas: 0 para operación válida (aunque haya juicios fail), 1 para run con errores
o comparación con regresiones, 2 para entradas inválidas, revisión incompleta,
prerrequisitos o acceso a archivos. No se sobrescriben revisiones ni baselines.
Una copia de baseline que falle por IO puede dejar un destino parcial: conservar
el run original y revisar el destino antes de repetir la promoción.

## Tests y límites

```bash
uv run --locked pytest tests/test_rag_evaluation.py tests/test_evaluation_review.py \
  tests/test_evaluation.py tests/test_evaluation_dataset.py tests/test_rag.py
```

Tests deterministas sin red, DB, modelos ni credenciales. Cubren trazas, exclusión
de rúbrica, errores/citas, ausencia/presupuesto, checkpoints/interrupciones,
integridad, promoción, N/A y regresiones. Los tests de `tests/test_retrieval_evaluation.py` prueban además aislamiento/limpieza
con la DB de pruebas y encoder fake. `tests/test_rag_integration.py` comprueba
el runner sobre los 50 documentos con SQL/pgvector reales, diez búsquedas y
generador/encoder fake, validando trazas y limpieza. Una prueba de invariancia
cambia las anotaciones y exige argumentos de retrieval y mensajes LLM idénticos.
Otros juicios artificiales comprueban que negativas y abstenciones pueden aprobar. Las pruebas validan el mecanismo, no calidad IA.

Diez casos y una revisión humana pequeña no permiten generalizar ni acreditar
factualidad clínica, revisión experta, acuerdo entre revisores o ausencia universal
de alucinaciones. Los casos suficientes tampoco garantizan recuperación correcta.
La preparación e integración previas están validadas; los tests del artefacto
`tests/test_rag_baseline.py` auditan la promoción y reproducen el agregado sin
red, DB ni modelos. Persisten los warnings conocidos de dependencias. La revisión
y promoción v1 están terminadas; Git/GitHub conserva el estado de entrega y
cierre de M8. La autorización de una corrida está consumida. Diseño y
trade-offs en [D028](../../docs/decisions/D028-rag-evaluation.md).
