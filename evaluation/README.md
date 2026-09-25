# Evaluación offline de Generator

Desde la raíz del repositorio, con las variables `EVIDENCEOPS_GEMINI_*`
habituales en el entorno o `.env`:

```bash
uv run --locked python -m evidenceops.evaluation run --live
```

`--live` es obligatorio y consume cuota de Gemini. «Offline» significa fuera
del servicio HTTP: Gemini necesita red; FastAPI y PostgreSQL no intervienen y
no se requiere `DATABASE_URL`. Se reutiliza `GenerationSettings`, también base
de la configuración de la API. No hay inferencia al importar el módulo.

El runner llama secuencialmente a `Generator.generate(case.question)` con
`GeminiGenerator`. Nunca envía la rúbrica del dataset. Conserva un JSON por run
en `evaluation/runs/` (ignorado por Git) e imprime su ruta. `--dataset` y
`--output-dir` permiten seleccionar otras rutas; si se cambia la salida, quien
ejecuta debe mantener sus runs fuera de Git.

El archivo contiene UUID, fecha UTC de inicio, versión y SHA-256 de los bytes
exactos del dataset, commit y estado dirty/clean al inicio, modelo, tokens y
timeout efectivos. Cada caso contiene ID, pregunta y output o causa segura.
No contiene scores ni evaluadores. No se serializan mensajes de excepciones,
credenciales ni respuestas brutas del SDK.

Se guarda un checkpoint tras cada caso, sustituyendo atómicamente el archivo.
Los errores ordinarios no detienen los casos restantes; el comando devuelve 1
si hay casos fallidos y 0 si todos tienen éxito. Una interrupción conserva los
casos ya terminados; no hay reanudación automática ni retries propios. Se
mantiene la política del adaptador: el timeout es de transporte, no un deadline
total, y el SDK puede reintentar determinados fallos una vez.

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
no representa una regresión automáticamente. La evaluación y scoring quedan
para #17. Las respuestas de Gemini pueden variar con el mismo código y dataset.
El hash identifica el artefacto de entrada; el commit identifica el código y
`SYSTEM_INSTRUCTION` cuando el árbol está limpio. `working_tree_dirty=true`
advierte de cambios locales: el commit por sí solo no permite reconstruirlos.

Tests sin Gemini, credenciales ni PostgreSQL:

```bash
uv run --locked pytest tests/test_evaluation.py tests/test_evaluation_dataset.py
```

## Estado del baseline

#16 está completada y validada. En la ejecución real confirmada por el
desarrollador hubo un caso exitoso y nueve con `rate_limit`; la promoción fue
rechazada correctamente porque no todos los casos tuvieron éxito.

El baseline real queda pendiente de ejecución/promoción cuando Gemini disponga
de cuota suficiente, como operación futura y no como desarrollo pendiente.
Se usarán los comandos anteriores sin modificar el runner, cambiar de proveedor,
pagar cuota ni introducir retries artificiales. No hay baseline válido todavía.
