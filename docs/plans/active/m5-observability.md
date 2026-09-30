# M5 — Observability: plan activo

## Alcance y dependencias

Investigar generaciones mediante logging, métricas y tracing. Objetivos generales
en [roadmap](../../ROADMAP.md#m5--observability); arquitectura de aplicación intacta.

1. [#21: logging y correlación](https://github.com/luissm01/biomedical-evidenceops/issues/21):
   implementación local, pendiente de revisión y publicación/cierre.
2. [#22: métricas de generación, latencia y uso](https://github.com/luissm01/biomedical-evidenceops/issues/22):
   después de #21; sin implementar.
3. [#23: tracing y diagnóstico end-to-end](https://github.com/luissm01/biomedical-evidenceops/issues/23):
   después de #21 y #22; sin implementar.

## Retomar #21

- Revisar código y tests locales: `observability.py`, integración en `main.py`
  y `gemini.py`, `test_observability.py` y `test_gemini_adapter.py`.
- Diseño acordado en [D016](../../decisions/D016-structured-logging.md).
  Semántica de eventos, privacidad, comandos y límites en el
  [runbook](../../subsystems/observability.md). No duplicar aquí su especificación.
- La comprobación práctica con Gemini quedó propuesta, no ejecutada; requiere
  que la tarea incluya esa inferencia. Los tests utilizan fakes/transporte simulado.
- La PR documental publica este plan y el runbook, pero excluye el código y tests
  locales de #21. Recuperar ese trabajo local antes de ejecutar su comprobación.
- Revisar resultado antes de publicar/cerrar. La refactorización documental no
  autoriza publicación de #21 ni avance de #22/#23.

## Evidencia de validación recibida

La sesión anterior registró **156 passed y dos DeprecationWarning conocidos**
en la suite completa, con PostgreSQL accesible. No es una ejecución de este refactor.
Los tests cubren JSON, IDs/correlación, éxito y causas seguras, privacidad, duración,
404/422/500, concurrencia, limpieza tras error y configuración sin duplicados.
Hubo errores de setup por PostgreSQL apagado antes de esa ejecución correcta;
no quedan descritos como fallos funcionales pendientes.

## Decisiones abiertas y salida

Métricas y tracing aún requieren diseño con el desarrollador. No están elegidas
plataformas de observabilidad; OpenTelemetry/Langfuse no se han adoptado.
No instrumentar intentos internos del SDK ni cambiar retries/timeouts para #21.

Para cerrar M5, contrastar criterios de sus issues y aprendizaje realmente
trabajado, validar el comportamiento implementado y conservar límites operativos
en runbooks/ADRs. Mover este plan a completados cuando el trabajo se cierre,
actualizar el estado y evitar arrastrar su historial al milestone siguiente.
