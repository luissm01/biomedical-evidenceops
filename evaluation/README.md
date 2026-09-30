# Evaluación offline de Generator

Fuente del procedimiento de dataset, ejecución, promoción y revisión. El dataset
[cases.json](cases.json) contiene la rúbrica; no es una respuesta ideal ni un
benchmark completo. No incluye fuentes de referencia en su versión inicial.
El contrato HTTP y la estructura de salida se prueban en la suite de software;
los juicios de contenido se realizan aquí. No hay retrieval ni evaluación de citas.

Desde la raíz del repositorio, con `EVIDENCEOPS_LLM_PROVIDER` y las variables del proveedor elegido en el entorno o `.env`:

```bash
uv run --locked python -m evidenceops.evaluation run --live
```

`--live` es obligatorio y consume cuota del proveedor elegido. «Offline» significa fuera
del servicio HTTP: el proveedor necesita red; FastAPI y PostgreSQL no intervienen y
no se requiere `DATABASE_URL`. Se reutiliza `GenerationSettings`, también base
de la configuración de la API. No hay inferencia al importar el módulo.

El runner llama secuencialmente a `Generator.generate(case.question)` con
el adapter configurado. Nunca envía la rúbrica del dataset. Conserva un JSON por run
en `evaluation/runs/` (ignorado por Git) e imprime su ruta. `--dataset` y
`--output-dir` permiten seleccionar otras rutas; si se cambia la salida, quien
ejecuta debe mantener sus runs fuera de Git.

El archivo contiene UUID, fecha UTC de inicio, versión y SHA-256 de los bytes
exactos del dataset, commit y estado dirty/clean al inicio, modelo, tokens y
timeout efectivos. Cada caso contiene ID, pregunta y output o causa segura.
No contiene scores ni evaluadores. No se serializan mensajes de excepciones,
credenciales ni respuestas brutas del proveedor. El modelo registrado es el
seleccionado; el esquema histórico del run no incluye todavía un campo `provider`.

Se guarda un checkpoint tras cada caso, sustituyendo atómicamente el archivo.
Los errores ordinarios no detienen los casos restantes; el comando devuelve 1
si hay casos fallidos y 0 si todos tienen éxito. Una interrupción conserva los
casos ya terminados; no hay reanudación automática ni retries propios. Se
mantiene la política del adaptador: el timeout es de transporte, no un deadline
total, Gemini puede reintentar determinados fallos una vez; DeepSeek no reintenta.

## Seleccionar y usar un baseline

Revisar el run y sustituir `<run_id>` por el UUID impreso:

```bash
uv run --locked python -m evidenceops.evaluation promote \
  evaluation/runs/<run_id>.json evaluation/baselines/m4-initial.json
```

La promoción copia el run completo sin cambiar su metadata, comprueba versión,
hash, IDs, preguntas y éxito de todos los casos contra `evaluation/cases.json`.
Rechaza casos ausentes, duplicados, errores, outputs inválidos y un destino que
ya exista. Para un dataset histórico se debe proporcionar su archivo exacto
mediante `--dataset`. El baseline queda en una ruta versionable; el comando no
hace commit ni publica nada.

Un baseline es una referencia de outputs, no una respuesta ideal ni una
certificación de calidad biomédica. Para usarlo, ejecutar otro run y comparar
manualmente los outputs por `case_id`, consultando los criterios en `cases.json`:

```bash
git diff --no-index evaluation/baselines/m4-initial.json evaluation/runs/<nuevo_run_id>.json
```

El diff también muestra metadata distinta y devuelve 1 cuando hay diferencias;
no representa una regresión automáticamente. Usa la revisión estructurada
descrita abajo para detectar cambios de calidad. Las respuestas del proveedor pueden variar con el mismo código y dataset.
El hash identifica el artefacto de entrada; el commit identifica el código y
`SYSTEM_INSTRUCTION` cuando el árbol está limpio. `working_tree_dirty=true`
advierte de cambios locales: el commit por sí solo no permite reconstruirlos.

Tests sin inferencias reales, credenciales ni PostgreSQL:

```bash
uv run --locked pytest tests/test_evaluation.py tests/test_evaluation_dataset.py
```

## Disponibilidad de un baseline

Consulta el [estado operativo](../docs/CURRENT_STATE.md) antes de asumir que
existe un baseline real. Los nombres de archivos de esta guía son ejemplos;
reemplázalos por artefactos existentes y compatibles. Las decisiones del método
están en [D013–D015](../docs/decisions/README.md).

## Revisión humana estructurada

Estos comandos son locales, sin proveedor LLM ni PostgreSQL. `prepare` exige un run
completo y exitoso contra el dataset exacto. Los casos ausentes o con error de
generación invalidan la evaluación de calidad: no se convierten en juicios fail.

```bash
uv run --locked python -m evidenceops.evaluation_review prepare \
  evaluation/baselines/m4-initial.json evaluation/runs/baseline-review.json
```

1. Abre el run, `evaluation/cases.json` y la revisión en el editor. No modifiques
   el run ni el dataset durante la revisión.
2. Completa `reviewer` con un identificador del revisor. Para cada caso, lee la
   pregunta, el output completo (`answer` y `limitations`) y toda la rúbrica:
   `reference_facts`, `expected_behavior` y `forbidden_claims`.
3. Cambia cada `verdict: null` por `"pass"` o `"fail"`, solo en las dimensiones
   preparadas: `relevance` evalúa si responde sin evasión ni contenido irrelevante;
   `factual_correctness`, si las afirmaciones son compatibles con los hechos;
   `prudence_and_limitations`, si expresa incertidumbre, riesgos y límites
   pertinentes sin falsa seguridad ni recomendaciones injustificadas.
4. Interpreta la rúbrica semánticamente: negar una afirmación prohibida no es
   fallar por contener las mismas palabras. No hay matching textual. Los puntos
   formulados como «puede» son opcionales. Una respuesta prudente pero evasiva
   puede fallar relevancia; juzga cada dimensión por separado.
5. Cada `fail` requiere `notes` explicando la afirmación u omisión y su conflicto
   con la rúbrica; en `pass` son opcionales. Si no puedes decidir, conserva null
   y resuelve la duda antes de agregar. Si la rúbrica necesita cambiar, ambos
   runs deberán corresponder al nuevo dataset y revisarse de nuevo.
6. Conserva hashes, identificadores y pares. No añadas dimensiones ni elimines
   resultados. Puedes guardar borradores, pero no agregarlos ni compararlos.
   `prepare` nunca sobrescribe una revisión existente.

Ejemplo de entrada completada (juicio artificial):

```json
{
  "case_id": "antibiotics_flu_001",
  "dimension": "factual_correctness",
  "verdict": "fail",
  "notes": "Afirma que los antibióticos curan la gripe; contradice los hechos de referencia."
}
```

El JSON incluye `review_version: "1"`, `evaluator: "human"`, `reviewer`, `run_id`,
`run_sha256`, `dataset_version`, `dataset_sha256` y `results`. Null solo es un
estado de borrador; los resultados finales son binarios. El hash canónico del
run permite reformatear JSON, pero cualquier cambio de contenido invalida la
revisión. Es trazabilidad local, no una firma ni una prueba de autoría.

## Agregar y comparar

```bash
uv run --locked python -m evidenceops.evaluation_review aggregate \
  evaluation/baselines/m4-initial.json evaluation/runs/baseline-review.json

uv run --locked python -m evidenceops.evaluation_review prepare \
  evaluation/runs/<candidate_id>.json evaluation/runs/candidate-review.json
# Completar candidate-review.json manualmente antes de comparar.
uv run --locked python -m evidenceops.evaluation_review compare \
  evaluation/baselines/m4-initial.json evaluation/runs/baseline-review.json \
  evaluation/runs/<candidate_id>.json evaluation/runs/candidate-review.json
```

Todos aceptan `--dataset <archivo>`; ambos runs deben corresponder al mismo
archivo exacto, incluida su rúbrica. Modelo, commit y configuración pueden variar.
Las revisiones cubren exactamente los pares declarados, sin duplicados y con
juicios completos. El dataset actual tiene 28 pares en 10 casos.

`aggregate` imprime conteos pass/fail globales y por dimensión, lista y número
de casos completamente aprobados, todos los fallos con notas y todos los
resultados individuales. Un caso aprueba solo si pasan todas sus dimensiones.
No hay scores, pesos, umbrales ni nota global.

`compare` imprime conteos y listas de `unchanged_pass`, `unchanged_fail`,
`improvements` (fail → pass) y `regressions` (pass → fail) por el mismo
`case_id + dimension`, con notas de ambas revisiones y orden estable. Una mejora
nunca compensa una regresión. Comparar revisiones del mismo run mide cambios de
juicio humano; para medir cambios del sistema usa runs distintos y criterios
consistentes.

Códigos de salida: prepare/aggregate devuelven 0 para datos válidos, incluso
con juicios fail; compare devuelve 0 sin regresiones y 1 con regresiones;
2 indica datos inválidos, revisión incompleta o problemas de acceso a archivos.
La salida JSON puede redirigirse a un archivo nuevo. Guarda artefactos ordinarios
en `evaluation/runs/`, ignorado por Git. Su publicación no es automática.

Demostración determinista sin proveedor:

```bash
uv run --locked pytest tests/test_evaluation_review.py -k controlled_regression -v
```

Cambia artificialmente `a + factual_correctness` de pass a fail y `b + relevance`
de fail a pass. Los totales siguen siendo 2 pass y 2 fail, pero se detectan y
listan una regresión y una mejora, además de unchanged pass y unchanged fail.
Prueba la detección sobre juicios introducidos, no un evaluador biomédico
automático ni calidad del proveedor.

La revisión humana es manejable para diez casos y permite valorar semántica y
contexto, pero tiene coste manual y variabilidad entre revisores. Mantén criterios
consistentes y resuelve desacuerdos con las notas y la rúbrica. Los cálculos son
reproducibles para los mismos juicios; los juicios humanos no necesariamente.
Los resultados no son certificación clínica ni generalizan fuera del dataset.
LLM-as-a-judge queda fuera: coste, variabilidad, sesgos y dependencia de un modelo
no se justifican frente a esta revisión pequeña.
