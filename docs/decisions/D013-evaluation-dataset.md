# D013 — Dataset inicial de contenido para M4 (#15)

## Status

Aceptada y aplicada en M4; #15 completada según el contexto de cierre de M4.

## Problem and decision

La estructura válida de una respuesta no demuestra que su contenido sea bueno.
Se acuerdan `relevance` (contestar la pregunta sin evasión ni contenido irrelevante),
`factual_correctness` (afirmaciones compatibles con los hechos de referencia del caso)
y `prudence_and_limitations` (incertidumbre, contexto, riesgos y límites del sistema).
El contrato HTTP y el schema permanecen en los tests tradicionales.

Se conserva un dataset manual pequeño, con los diez casos acordados, en
`evaluation/cases.json`, versión `0.1`. Cada caso especifica hechos de referencia,
comportamiento esperado y afirmaciones prohibidas semánticas, sin una respuesta
ideal única: pueden existir distintas respuestas correctas. El dataset describe
el examen y se mantiene separado de outputs, scores y resultados de ejecución.

## Trade-offs

Es comprensible y revisable, pero no constituye un benchmark biomédico completo
ni garantiza factualidad fuera de sus referencias. No incluye `reference_sources`
en esta versión. Sin retrieval, no se mide groundedness ni calidad de citas.
No se añaden dependencias, loaders, runner ni evaluadores en #15; la elección de
métodos y métricas queda para las siguientes issues. Las pruebas nuevas protegen
solo la estructura del artefacto, no valoran respuestas del LLM.
