# D017 — Arquitectura documental y carga progresiva

Estado: aceptada por el encargo explícito de refactorización (2026-09-30).

## Problema y alternativas

El mapa global acumulaba pedagogía y roadmap; estado y README repetían historia
e implementación con contradicciones. Acortar párrafos mantendría las mismas
dependencias de lectura. Dividir por responsabilidad permite cargar contexto
según la tarea, a costa de mantener rutas e índices.

## Decisión

AGENTS contiene restricciones globales, entrada, rutas y definición de terminado.
CURRENT_STATE contiene presente y siguiente paso. ROADMAP concentra la secuencia
M0–M19 existente, sin alterar orden o alcance. ADRs individuales conservan D001–D016;
aprendizaje se consulta por milestone. Planes distinguen trabajo activo de historia.
Runbooks de subsistemas conservan procedimientos; una skill de evaluación enruta
el workflow sin copiar sus comandos ni reemplazar la revisión humana.

La ubicación de autoría de skills solicitada, `.codex/skills`, tiene enlaces desde
`.agents/skills` para descubrimiento según la
[documentación oficial](https://learn.chatgpt.com/docs/build-skills).
No se añade configuración global ni se duplica contenido.

## Consecuencias

Más archivos pequeños, pero menos lectura obligatoria. Los índices necesitan
enlaces válidos; no se deben recorrer recursivamente. Código/config/tests y
Git/GitHub siguen siendo fuentes automáticas. Los planes completados no son un
changelog alternativo. La revisión documental usa responsabilidades y cambios,
sin exigir releer todo ni crear una skill para cada regla.

No cambian arquitectura de aplicación, secuencia de milestones ni alcance de M5.
El [informe del refactor](../plans/completed/context-refactor.md) conserva el
diagnóstico, trazabilidad de migración y pruebas de navegación.
