---
name: evidenceops-evaluation
description: Ejecutar, promover, preparar revisión humana o comparar runs de evaluación de EvidenceOps. No se necesita para cambios ordinarios de backend.
---

# Evaluación de EvidenceOps

Trabaja desde la raíz del repositorio. Identifica la operación solicitada,
el dataset y los artefactos de entrada/salida; no ejecutes todo el pipeline
cuando solo se pide comparar runs existentes.

1. Consulta [evaluation/README.md](../../../evaluation/README.md) para comandos,
   validación y rúbrica. El [estado](../../../docs/CURRENT_STATE.md) únicamente si la operación depende del baseline actual, de una limitación vigente o del siguiente paso del proyecto.
   No presupongas que los archivos de ejemplo existen.
2. Distingue pruebas sin proveedor de `run --live`: este consume cuota y solo
   procede si el encargo incluye inferencias reales. Si no las incluye, realiza
   únicamente trabajo local con artefactos existentes o tests con fakes.
3. Mantén separados dataset, outputs y juicios. Si un run tiene errores o está
   incompleto, informa del fallo operativo; no lo conviertas en fail de contenido
   ni lo promociones. No cambies dataset, proveedor o retries para forzar un baseline.
4. `prepare` produce un borrador para revisión humana. No rellenes juicios ni
   atribuyas una revisión al desarrollador automáticamente. Una revisión incompleta
   queda pendiente; no puede agregarse/compararse. Si falta evidencia, detén solo
   esa operación e identifica el artefacto o juicio necesario.
5. Para comparar, usa revisiones completas sobre el mismo dataset exacto y
   conserva transiciones por caso/dimensión. Informa regresiones y mejoras por
   separado; totales iguales no demuestran ausencia de regresiones.
6. Entrega rutas de artefactos, comandos ejecutados, resultado/exit code y límites
   de la conclusión. Distingue cálculo determinista, juicio humano y calidad real
   del modelo. Con fakes solo se valida el mecanismo. No sobrescribas ni publiques
   artefactos por el hecho de haberlos generado.

El runbook es la fuente única del procedimiento técnico; no copies sus comandos
ni listas de campos a esta skill. Actualiza el estado solo si cambia una limitación
o el siguiente paso, sin añadir un historial de ejecuciones.
