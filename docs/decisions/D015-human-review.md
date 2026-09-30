# D015 — Revisión humana estructurada y regresiones por dimensión (#17)

## Status

Accepted por instrucciones explícitas del desarrollador el 2026-09-25.

## Problem and decision

La calidad de contenido exige interpretar la rúbrica y el contexto; estructura
válida y matching textual no demuestran factualidad. Revisión humana inicial
por `case_id + dimension`, solo dimensiones declaradas, con pass/fail sin scores,
pesos ni umbrales. Todo fail exige notas. Los borradores usan null y no admiten
agregación/comparación hasta completarse e identificar revisor.

Un JSON separado vincula los juicios al ID y hash canónico del run y al dataset
exacto. Se reutiliza la validación de runs completos de #16. La comparación
exige el mismo dataset y revisiones completas: pass → fail es regresión y
fail → pass es mejora. Conserva todas las transiciones y notas, conteos por
dimensión, casos completamente aprobados y resultados individuales. No se
compensan regresiones con mejoras. Modelo/código/configuración pueden variar.

## Trade-offs

La revisión manual es manejable para diez casos, pero exige consistencia humana.
Los cálculos son deterministas; los juicios no garantizan reproducibilidad ni
validez clínica. El hash detecta cambios del run, no autentica al revisor.
Se rechazan runs incompletos/con errores en vez de confundir fallos operativos
con calidad. Cambiar el dataset exige nuevos runs/revisiones compatibles.

No se implementa LLM-as-a-judge: coste, variabilidad, sesgos y dependencia de
modelo/proveedor no se justifican frente a esta muestra pequeña. Tampoco matching
automático de forbidden_claims, tracking genérico ni persistencia nueva.
Una demostración con outputs y juicios artificiales valida el mecanismo,
no la calidad biomédica. El cierre de M4 no exige un baseline real cuando
la cuota externa impide obtenerlo; su estado vive en CURRENT_STATE.
