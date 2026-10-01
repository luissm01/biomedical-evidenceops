# D019 — Métricas Prometheus de generación y tokens observados (#22)

## Estado

Aceptada por diseño explícito del desarrollador; implementada localmente.

## Problema y alternativas

Los logs de D016 permiten seguir una petición, pero no agregan tasas de error,
distribuciones de latencia ni uso de tokens. Se consideró instrumentación HTTP
general, un sistema de tracing y métricas centradas en la operación LLM. #22
requiere estas últimas, sin infraestructura adicional.

## Decisión y consecuencias

`prometheus-client` expone `GET /metrics`. Cada instancia de aplicación posee su
registro, lo que evita registros globales duplicados y permite tests aislados.
La API mide el mismo tramo que su log de duración: llamada a `Generator`,
incluida validación y posibles retries del SDK. Counter agrega generaciones y
errores por causas estables; Histogram registra duración por resultado. Los
adapters registran tokens solo si la respuesta del proveedor aporta los tres
campos. `provider` y `model` etiquetan únicamente tokens. No se etiquetan IDs,
contenido ni errores crudos.

El scrape ofrece agregados desde el arranque del proceso. No mide intentos
internos ni requests HTTP completos. La metadata de tokens es uso observado;
el coste facturado depende de pricing y tier externos, que no se conocen aquí
de forma fiable. No se calcula coste ni se incorporan Prometheus Server,
Grafana, tracing u otra infraestructura.
