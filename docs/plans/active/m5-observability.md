# M5 — Observability: plan activo

## Alcance y dependencias

Investigar generaciones mediante logging, métricas y tracing. Objetivos generales
en [roadmap](../../ROADMAP.md#m5--observability); arquitectura de aplicación intacta.

1. [#21: logging y correlación](https://github.com/luissm01/biomedical-evidenceops/issues/21):
   cerrada. Eventos LLM comunes para Gemini y DeepSeek.
2. [#22: métricas de generación, latencia y uso](https://github.com/luissm01/biomedical-evidenceops/issues/22):
   después de #21; sin implementar.
3. [#23: tracing y diagnóstico end-to-end](https://github.com/luissm01/biomedical-evidenceops/issues/23):
   después de #21 y #22; sin implementar.

## Decisiones abiertas y salida

Métricas y tracing aún requieren diseño con el desarrollador. No están elegidas
plataformas de observabilidad; OpenTelemetry/Langfuse no se han adoptado.
No instrumentar intentos internos ni cambiar retries/timeouts al abordar #22.

Para cerrar M5, contrastar criterios de sus issues y aprendizaje realmente
trabajado, validar el comportamiento implementado y conservar límites operativos
en runbooks/ADRs. Mover este plan a completados cuando el trabajo se cierre,
actualizar el estado y evitar arrastrar su historial al milestone siguiente.
