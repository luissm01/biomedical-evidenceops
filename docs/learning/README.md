# Aprendizaje del desarrollador

Consultar solo al enseñar o revisar comprensión; no cargar para cada issue.
La [guía](guide.md) contiene perfil, objetivos y pedagogía. Estos registros
conservan conceptos realmente trabajados y límites de comprensión, no manuales.

| Milestone | Registro |
| --- | --- |
| M0 | [Entorno, HTTP y tests](m0.md) |
| M1 | [Pydantic, contratos y recorrido de ejecución](m1.md) |
| M3 | [Inferencia, Protocol, DI, ownership y fallos](m3.md) |
| M4 | [Dataset, rúbrica y revisión humana](m4.md) |
| M5 | [Logging y correlación conceptual](m5.md) |

No había registro suficiente de aprendizaje de M2 para crearlo por inferencia.
Las decisiones técnicas de persistencia siguen documentadas en las ADRs.

## Comprensión pendiente de confirmar

Validadores Pydantic en profundidad, async Python, unit/integration testing en
profundidad, mocking, configuración/variables de entorno en profundidad,
dockerización y CI/CD. Haber explicado o generado código no acredita dominio.
Los matices concretos de lifecycle, SDK y concurrencia están en el registro
del milestone pertinente. No considerar context engineering aprendido solo
porque este refactor lo haya implementado un agente.
