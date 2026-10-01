# M5 — Observability: plan completado

## Alcance y dependencias

Investigar generaciones mediante logging, métricas y tracing. Objetivos generales
en [roadmap](../../ROADMAP.md#m5--observability); arquitectura de aplicación intacta.

1. [#21: logging y correlación](https://github.com/luissm01/biomedical-evidenceops/issues/21):
   cerrada. Eventos LLM comunes para Gemini y DeepSeek.
2. [#22: métricas de generación, latencia y uso](https://github.com/luissm01/biomedical-evidenceops/issues/22):
   implementada sobre Gemini y DeepSeek; cerrada.
3. [#23: tracing y diagnóstico end-to-end](https://github.com/luissm01/biomedical-evidenceops/issues/23):
   implementada con OpenTelemetry y validada para entrega.

## Decisiones y salida

Métricas acordadas en [D019](../../decisions/D019-prometheus-metrics.md).
[D020](../../decisions/D020-opentelemetry-tracing.md) documenta el diseño de tracing.
No instrumentar intentos internos ni cambiar retries/timeouts al abordar #22.

Las verificaciones y los límites operativos permanecen en
[observabilidad](../../subsystems/observability.md) y [D020](../../decisions/D020-opentelemetry-tracing.md).
Este archivo conserva el orden de M5; GitHub refleja la entrega de issues y PRs.
