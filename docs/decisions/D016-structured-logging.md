# D016 — Logging estructurado y correlación HTTP mínima (#21)

## Status

Aceptada por diseño explícito del desarrollador. Entrega en el plan activo M5.

## Decision and trade-offs

Logging estándar, JSON a stdout y UUID generado por EvidenceOps por petición,
propagado con ContextVar y devuelto en X-Request-ID. No se confía en el ID enviado
por el cliente. No se amplían contratos de negocio para transportar metadata.
La API registra la operación; Gemini aporta el modelo desde el adaptador.
Duración monotónica de la generación, causas seguras y campos seleccionados;
sin contenido biomédico, secretos ni cadenas de excepción.

Es suficiente para investigar operaciones individuales sin nuevas dependencias.
No ofrece agregación ni tracing y no representa los intentos internos del SDK.
Se preservan errores, timeouts y retries de D011/D012. El middleware envuelve
la capa de errores HTTP para correlacionar también sus respuestas 500, sin
cambiar cuerpos/códigos. OpenTelemetry y Langfuse siguen sin adoptarse.
