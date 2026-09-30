# D014 — Runner offline sobre Generator y baseline de outputs (#16)

## Status

Accepted por instrucción explícita del desarrollador el 2026-09-23.

## Problem and decision

Necesitamos conservar outputs trazables antes de implementar evaluadores.
El System Under Evaluation es Generator: GeminiGenerator en runs reales y fake
en tests, sin FastAPI ni PostgreSQL. Solo recibe case.question. Ejecución
secuencial, explícita mediante --live; pytest/CI nunca realizan inferencias reales.
GenerationSettings concentra la configuración del proveedor; Settings hereda
esta configuración y mantiene obligatoria la URL de PostgreSQL para la API.

Se usa un JSON por run con UUID, UTC, versión/hash SHA-256 del dataset, commit,
working tree dirty/clean, modelo, tokens y timeout efectivos, más ID/pregunta y
output o causa segura por caso. El commit identifica código y SYSTEM_INSTRUCTION;
no se crea versionado de prompts. Con árbol dirty el commit no reconstruye los
cambios locales. No se guardan excepciones brutas ni secretos.

Runs ordinarios ignorados por Git, con checkpoint por caso. Los fallos ordinarios
se registran y la ejecución continúa; las interrupciones dejan un run parcial.
La promoción copia un run a evaluation/baselines/ solo si todos los casos del
dataset exacto están presentes y han tenido éxito. No sobrescribe baselines.

## Trade-offs

Un archivo sencillo permite revisión manual y comparación por case_id, sin
plataformas ni dependencias nuevas. El baseline contiene outputs de referencia,
sin scores ni certificación factual. Una inferencia real puede variar; trazabilidad
no implica determinismo del proveedor. Se conserva la política de timeout/retries
de D011. Evaluadores, métricas y regresiones quedan para #17.

La falta de cuota no permite promover runs fallidos ni justifica cambiar de
proveedor, pagar cuota o añadir retries artificiales. Estado operativo del
baseline en [CURRENT_STATE](../CURRENT_STATE.md).
