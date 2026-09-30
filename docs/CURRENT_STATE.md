# Estado actual

Actualizado: 2026-09-30. Distingue código versionado de trabajo local pendiente.

## Presente

- Milestone activo: **M5 — Observability**. M0–M4 completados según las
  confirmaciones conservadas; el [plan activo](plans/active/m5-observability.md)
  concentra orden de issues, revisión pendiente y criterios de continuación.
- API para registrar/consultar preguntas persistidas en PostgreSQL y generar
  respuestas efímeras mediante Gemini. [Límites y flujo](ARCHITECTURE.md).
- Evaluación offline con runs trazables, promoción de baseline y revisión humana
  por caso/dimensión, con agregación y comparación de regresiones.
  [Procedimiento](../evaluation/README.md).
- #21 está implementada localmente: logs JSON y correlación HTTP.
  Su código y tests no se incluyen en la PR de refactorización documental;
  siguen pendientes de revisión y publicación/cierre. Un checkout de esa PR
  no incorpora logging ni correlación. Métricas y tracing no implementados.

## Limitaciones relevantes

- No existe todavía un baseline real completo y revisado: la cuota impidió
  completar el run. Obtenerlo es una operación futura, no desarrollo pendiente
  de M4 ni prueba de calidad del modelo. No cambiar proveedor, pagar cuota o
  añadir retries artificiales para conseguirlo.
- Sin retrieval, fuentes consultadas ni citas verificadas. La revisión humana
  aplica una rúbrica limitada; no hay validación factual automática.
- Timeout de transporte sin deadline total; un retry puede duplicar consumo.
  [Política y motivos](decisions/D011-gemini.md).
- Una caída de PostgreSQL tras startup aún produce errores no controlados en
  endpoints de datos. Readiness y recuperación quedan para M14.
- Dos DeprecationWarning conocidos de dependencias: Starlette usa
  `anyio.abc.BlockingPortal`; google-genai usa `typing._UnionGenericAlias`
  (previsto para eliminación en Python 3.17). No se ocultan.
- En el entorno WSL usado previamente no estaba disponible la integración del
  CLI Docker; Docker Desktop y el contenedor existente se arrancaron desde
  Windows. Es una limitación de ese entorno, no un requisito del proyecto.

## Siguiente trabajo

Revisar la implementación local de #21 y su comprobación práctica según el plan
activo antes de publicarla/cerrarla. Después corresponde #22, seguida de #23.
Cuando exista cuota y se solicite, obtener/promover/revisar el baseline real.
Los comandos y requisitos de pruebas viven en el [README](../README.md);
los resultados de la validación previa de #21, en el plan activo.
