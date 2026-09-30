# EvidenceOps — mapa para agentes

Proyecto real de AI Engineering y de aprendizaje aplicado a evidencia biomédica
pública. Optimiza aprendizaje profesional útil por hora: el desarrollador debe
comprender las decisiones importantes, sin escribir manualmente todo el código.

## Entrada y alcance

- Empieza por este archivo y el encargo recibido. Abre después solo las fuentes
  necesarias según el mapa inferior.
- Consulta [estado_actual](docs/CURRENT_STATE) cuando la tarea dependa del estado del proyecto,
  del milestone actual, del trabajo pendiente o de cambios locales en curso.
- Trabaja dentro del milestone actual y el encargo. El [roadmap](docs/ROADMAP.md)
  es la única secuencia canónica M0–M19: consulta la sección relevante al definir
  alcance; no autoriza fases futuras. Cambiar la secuencia requiere acuerdo
  explícito del desarrollador, actualizar roadmap, ADR y milestones de GitHub.
- Involucra al desarrollador en decisiones arquitectónicas importantes: problema,
  alternativas, recomendación y trade-offs. Usa la solución más sencilla justificada.
- Automatiza trabajo mecánico y patrones comprendidos. Para enseñanza o conceptos
  nuevos consulta la [guía de colaboración](docs/learning/guide.md) y solo el
  registro de aprendizaje pertinente. No hagas ejercicios o preguntas rutinarias.
- Prioriza mecanismos transferibles antes de frameworks; mide cambios de IA con
  baseline, evaluación y comparación cuando sea posible.

## Reglas globales

- Usa datos biomédicos públicos; no datos clínicos privados, secretos ni contenido
  sensible en logs. Conserva las restricciones de gratuidad del roadmap.
- Respeta cambios locales, también documentación pendiente al cambiar de rama.
  No publiques documentación ni crees commits/PRs solo para cerrar una sesión,
  salvo petición explícita. Mantener contexto no implica publicarlo.
- Acepta las confirmaciones del desarrollador sobre merges/cierres. Usa herramientas
  solo cuando aporten información necesaria; no repitas verificaciones confirmadas.
  Git/GitHub son la fuente del historial y del estado de entrega, no los documentos.
- Tests/CI sin inferencias reales. Ejecuta llamadas reales solo dentro del encargo
  autorizado; no las repitas para comprobar una confirmación del desarrollador.

## Contexto bajo demanda

| Tarea | Fuente de entrada |
| --- | --- |
| Instalar, ejecutar o probar | [README](README.md) |
| Entender límites y flujo actual | [Arquitectura](docs/ARCHITECTURE.md) |
| Continuar el milestone | Plan enlazado desde [estado](docs/CURRENT_STATE.md) |
| Revisar una elección técnica | [Índice ADR](docs/decisions/README.md), luego solo la decisión pertinente |
| Evaluar generación | [Guía de evaluation](evaluation/README.md) |
| Diagnosticar logs | [Observabilidad](docs/subsystems/observability.md) |
| Enseñar o revisar aprendizaje | [Índice de aprendizaje](docs/learning/README.md) |
| Propósito o dirección futura | [Visión](docs/PROJECT_CONTEXT.md) / [roadmap](docs/ROADMAP.md) |
| Ubicar o mantener conocimiento | [Mapa documental](docs/README.md) |

Skills específicas en `.codex/skills/`, enlazadas desde `.agents/skills/` para
descubrimiento: `evidenceops-evaluation` para ejecutar/revisar/comparar evaluaciones.
Si no aparece en el selector, abre su SKILL.md desde el mapa documental.

## Verificación y terminado

Comandos desde la raíz: `uv sync --locked --dev`, `uv run --locked pytest`,
`uv run uvicorn evidenceops.main:app --reload`. La suite completa requiere
PostgreSQL de pruebas; preparación y alternativas acotadas en el README.

Antes de terminar: verifica el comportamiento afectado, ejecuta `git diff --check`
y revisa si cambian estado, decisiones, aprendizaje confirmado, roadmap o visión.
Actualiza solo la fuente afectada según [mantenimiento](docs/README.md#mantener).
Informa validación y límites; distingue fallos, errores de entorno y warnings.
No corrijas deprecaciones con cambios significativos sin explicar causa e impacto.
Código generado no acredita aprendizaje ni tests de contrato acreditan calidad IA.
