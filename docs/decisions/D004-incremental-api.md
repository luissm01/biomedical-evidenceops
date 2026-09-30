# D004 — Start with the smallest useful API

Estado: aplicada en M0; principio de evolución incremental vigente.

Comenzar con `/health` permitió trabajar HTTP, FastAPI y testing antes de añadir
capas sin un problema real. Se aceptó refactorizar después en lugar de diseñar
la arquitectura final anticipadamente. No limita la API actual a ese endpoint.
