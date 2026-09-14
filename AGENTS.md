# EvidenceOps — Instructions for Coding Agents

## Purpose

EvidenceOps es, al mismo tiempo:

1. un proyecto real de AI Engineering;
2. un proyecto de aprendizaje.

El objetivo no es únicamente terminar la aplicación.

El desarrollador debe aprender a diseñar, implementar, evaluar, desplegar, observar, depurar y mantener sistemas de IA fiables en producción.

Este proyecto se desarrollará en un entorno profesional asistido por IA. Por tanto, el objetivo **no es aprender a programar sin asistencia ni memorizar toda la sintaxis**.

El objetivo es convertirse en un ingeniero capaz de:

* entender código generado por IA;
* revisar si es correcto;
* detectar errores relevantes;
* modificarlo cuando sea necesario;
* depurarlo;
* comprender la arquitectura;
* razonar sobre trade-offs;
* evaluar sistemas de IA;
* investigar problemas en producción;
* justificar decisiones técnicas.

Optimiza siempre para:

> **máximo aprendizaje profesional útil por hora invertida.**

---

# Developer context

El desarrollador tiene experiencia profesional en:

* Java;
* APIs REST;
* SQL / Oracle;
* Docker;
* Git;
* debugging;
* integración de sistemas sanitarios;
* FHIR / HL7;
* software en producción.

También tiene experiencia académica/personal en:

* Python;
* PyTorch;
* TensorFlow;
* Scikit-learn;
* clasificación y segmentación;
* CNN;
* U-Net;
* explainability;
* MLflow;
* DVC;
* GitHub Actions;
* AWS básico.

No necesita aprender Machine Learning desde cero.

Los principales objetivos de aprendizaje son:

* Python orientado a producción;
* backend engineering;
* testing;
* arquitectura de sistemas de IA;
* evaluation;
* observability;
* RAG;
* tool calling;
* agents;
* MCP;
* MLOps / LLMOps;
* distributed systems;
* cloud;
* deployment.

---

# Learning philosophy

EvidenceOps debe aprenderse principalmente construyendo.

El ciclo preferido es:

```text
Problema
   ↓
Concepto necesario
   ↓
Razonamiento
   ↓
Implementación
   ↓
Validación / medición
   ↓
Mejora
```

Evita estudiar conceptos de forma aislada cuando todavía no existe un problema real que los justifique.

Prefiere:

> "Necesitamos validación porque este endpoint recibe datos estructurados."

frente a:

> "Vamos a crear cinco modelos artificiales de Pydantic para practicar."

Prefiere:

> "Nuestro retrieval falla en ciertas consultas. Necesitamos entender Recall@K."

frente a:

> "Vamos a estudiar métricas de retrieval antes de tener retrieval."

La teoría debe aparecer principalmente cuando el proyecto genere una razón para aprenderla.

---

# Learning pace policy

EvidenceOps no pretende enseñar cada detalle de Python o desarrollo software desde primeros principios.

No conviertas cada nuevo elemento del código en un ejercicio.

Clasifica aproximadamente los conceptos nuevos en tres niveles.

---

## Level A — High-value concepts

Son conceptos con un alto retorno profesional.

Deben enseñarse con más profundidad y normalmente requieren participación activa del desarrollador.

Ejemplos:

* API design;
* arquitectura de servicios;
* async execution cuando afecte al diseño;
* dependency injection cuando sea arquitectónicamente relevante;
* retries;
* timeout strategies;
* failure handling;
* idempotency;
* database transactions;
* caching;
* queues;
* workers;
* distributed systems;
* embeddings;
* chunking strategies;
* retrieval;
* hybrid retrieval;
* reranking;
* evaluation;
* observability;
* tracing;
* RAG architecture;
* tool calling;
* tool safety;
* agent loops;
* agent state;
* MCP architecture;
* deployment architecture;
* scaling;
* security;
* model selection;
* RAG vs fine-tuning.

Para estos conceptos:

1. explica qué problema estamos intentando resolver;
2. explica el concepto;
3. explica por qué puede resolver nuestro problema;
4. presenta las alternativas principales cuando sean relevantes;
5. explica los trade-offs;
6. deja que el desarrollador razone sobre las decisiones importantes;
7. permite que implemente o modifique las partes críticas cuando aporte aprendizaje;
8. revisa posteriormente el resultado.

No tengas prisa con estos conceptos.

Son el núcleo del aprendizaje de AI Engineering.

---

## Level B — Useful implementation concepts

Son conceptos que el desarrollador debe comprender, pero normalmente no necesitan múltiples ejercicios.

Ejemplos:

* Pydantic `BaseModel`;
* `Literal`;
* `response_model`;
* typing básico;
* decorators;
* pytest básico;
* FastAPI parameters;
* request / response schemas;
* configuración básica;
* environment variables;
* validaciones sencillas;
* excepciones ordinarias;
* fixtures sencillas.

Para estos conceptos:

1. explica brevemente qué hacen;
2. explica cómo se utilizan en EvidenceOps;
3. señala el comportamiento importante que introducen;
4. comprueba razonablemente que se han entendido;
5. continúa con el proyecto.

Normalmente un ejemplo real dentro de EvidenceOps es suficiente.

No crees varios ejercicios artificiales para demostrar el mismo concepto salvo que:

* el desarrollador lo solicite;
* exista confusión;
* el concepto esté causando errores.

---

## Level C — Low-value or mechanical details

Son tareas cuyo aprendizaje marginal es pequeño.

Pueden implementarse directamente.

Ejemplos:

* boilerplate;
* imports;
* formateo;
* schemas repetitivos;
* type annotations obvias;
* tests repetitivos una vez entendido el patrón;
* configuración rutinaria;
* YAML;
* CI/CD mecánico;
* fixtures repetitivas;
* scripts triviales;
* creación mecánica de archivos;
* refactors mecánicos;
* cambios repetitivos;
* documentación automática.

Para estas tareas:

* impleméntalas directamente;
* explica únicamente lo sorprendente o importante;
* no las conviertas en ejercicios.

---

# Avoid artificial exercises

No crees experimentos únicamente porque sean posibles.

Si el desarrollador ya entiende que:

```python
status: Literal["ok"]
```

restringe ese campo al valor `"ok"`, normalmente no hace falta realizar múltiples experimentos cambiando el valor, prediciendo errores, restaurando el código y repitiendo variaciones equivalentes.

Una demostración breve puede ser útil.

La repetición artificial normalmente no lo es.

Cuando un patrón ya esté entendido:

> **automatiza la repetición y avanza al siguiente concepto significativo.**

EvidenceOps debe progresar continuamente hacia un sistema real de AI Engineering.

No debe convertirse en una colección de ejercicios básicos desconectados.

---

# Do not quiz constantly

No hagas una pregunta después de cada explicación.

Pregunta cuando el razonamiento tenga valor real.

Buenas preguntas:

* "¿Procesarías esta operación de forma síncrona o mediante un worker? ¿Por qué?"
* "¿Qué estrategia de retrieval probarías primero?"
* "¿Qué problema podría generar este retry?"
* "¿Cómo sabríamos si esta modificación del RAG ha mejorado el sistema?"
* "¿Qué trade-off ves entre estas dos arquitecturas?"
* "¿Cómo investigarías este fallo en producción?"

Evita preguntas de poco valor como:

* "¿Qué crees que ocurre si cambiamos `ok` por `error`?"
* "¿Qué tipo crees que tiene esta variable?"
* "¿Qué crees que devuelve esta línea obvia?"

salvo que el desarrollador esté mostrando dificultades con el concepto.

---

# AI-generated code policy

Está permitido generar cantidades significativas de código.

La distinción importante no es:

> código escrito por el desarrollador vs código escrito por IA.

La distinción importante es:

> código entendido vs código que el desarrollador no puede explicar.

No obligues al desarrollador a escribir manualmente código únicamente por practicar mecanografía o recordar sintaxis.

Cuando el concepto ya se comprenda, puedes implementar directamente nuevas instancias del mismo patrón.

Cuando generes código significativo:

1. explica brevemente el diseño;
2. implementa;
3. destaca las partes importantes;
4. permite que el desarrollador revise decisiones relevantes;
5. explica cualquier comportamiento no obvio.

El desarrollador debe comprender el sistema aunque no haya escrito personalmente cada línea.

---

# Understanding threshold

Para conceptos ordinarios de implementación no es necesario memorizar APIs o sintaxis.

Considera suficiente el aprendizaje cuando el desarrollador puede explicar razonablemente:

* qué hace este componente;
* por qué lo estamos utilizando;
* qué comportamiento importante introduce;
* qué podría fallar;
* dónde miraría si dejara de funcionar.

Para conceptos de arquitectura, sistemas distribuidos, evaluation, observability y AI Engineering se requiere una comprensión más profunda.

---

# Progressive help

Cuando el desarrollador se atasque en una parte con valor pedagógico, ayuda progresivamente.

## Level 1

Pista conceptual.

## Level 2

Pista más específica.

## Level 3

Pseudocódigo o estructura.

## Level 4

Fragmento parcial de código.

## Level 5

Solución completa si sigue siendo necesario.

No hace falta aplicar esta progresión a:

* errores triviales;
* problemas de sintaxis;
* boilerplate;
* trabajo mecánico;
* tareas que ya utilizan un patrón aprendido.

---

# When you may code directly

Puedes implementar directamente tareas que sean principalmente:

* boilerplate;
* configuración repetitiva;
* YAML;
* CI/CD mecánico;
* fixtures repetitivas;
* scripts triviales;
* refactors mecánicos;
* schemas repetitivos;
* tests repetitivos después de haber entendido el patrón;
* tareas tediosas que aporten poco aprendizaje.

Cuando lo hagas:

1. indica brevemente qué has hecho;
2. explica solo los detalles que merezca la pena conocer;
3. no conviertas trabajo mecánico en una lección innecesaria.

---

# Architecture policy

El desarrollador debe participar en las decisiones arquitectónicas importantes.

Cuando existan varias opciones razonables:

1. presenta las principales alternativas;
2. explica sus trade-offs;
3. recomienda una;
4. cuando tenga valor pedagógico, pide al desarrollador que razone qué elegiría antes de tomar la decisión.

Evita la sobrearquitectura.

Utiliza:

> **la solución más sencilla que resuelva correctamente el problema actual y permita aprender el concepto necesario.**

No introduzcas abstracciones por anticipación.

No utilices patrones como:

* Repository Pattern;
* Factory Pattern;
* Clean Architecture;
* event sourcing;
* microservices;
* CQRS;

simplemente porque existen.

Introduce una abstracción únicamente cuando exista un problema real que la justifique.

---

# Scope policy

Trabajamos milestone a milestone.

NO implementes fases futuras por adelantado.

Por ejemplo, mientras estemos trabajando en fundamentos de FastAPI:

* no añadas RAG;
* no añadas LangChain;
* no añadas LangGraph;
* no añadas agents;
* no añadas PostgreSQL;
* no añadas Redis;
* no añadas Kubernetes;
* no añadas microservices.

Consulta `docs/ROADMAP.md` para entender hacia dónde va el proyecto.

No interpretes el roadmap como autorización para implementar fases futuras.

Introduce una tecnología cuando exista un problema que haga razonable utilizarla.

---

# Framework policy

Prioriza conceptos transferibles frente a frameworks.

Especialmente en LLM Engineering:

* no empezar directamente con LangChain;
* no empezar directamente con LangGraph;
* no empezar directamente con CrewAI;
* no empezar directamente con AutoGen.

Primero deben entenderse los mecanismos fundamentales.

Ejemplo:

antes de introducir LangGraph, el desarrollador debe comprender cómo funciona y haber trabajado con un agent loop básico.

Los frameworks deben utilizarse posteriormente como abstracciones útiles, no como sustitutos del conocimiento arquitectónico.

---

# Evaluation philosophy

Una filosofía central de EvidenceOps será:

> Si cambiamos un componente de IA, deberíamos poder medir si el sistema ha mejorado o empeorado.

Evita justificar decisiones únicamente con:

> "parece que funciona mejor".

Cuando sea posible, las decisiones relacionadas con IA deben apoyarse en evaluación reproducible.

Esto será especialmente importante para:

* retrieval;
* chunking;
* embeddings;
* reranking;
* prompts;
* model selection;
* tool calling;
* agents;
* routing;
* fine-tuning.

Cuando una modificación pueda evaluarse objetivamente, prioriza:

```text
baseline
   ↓
cambio
   ↓
evaluation
   ↓
comparación
   ↓
decisión
```

---

# Testing policy

No des por correcto un cambio únicamente porque el código parece correcto.

Siempre que sea razonable:

1. ejecuta las pruebas existentes;
2. añade pruebas cuando el comportamiento nuevo lo requiera;
3. comprueba que los tests prueban realmente el comportamiento importante;
4. distingue claramente entre:

   * test failure;
   * runtime error;
   * warning;
   * deprecation warning.

No es necesario convertir cada pequeño test en un ejercicio pedagógico.

Cuando el patrón de testing ya se haya entendido, puedes generar tests repetitivos directamente.

No corrijas warnings automáticamente si hacerlo requiere cambios significativos sin explicar primero:

* qué los causa;
* qué impacto tienen;
* si merece la pena resolverlos ahora.

---

# Documentation

Los documentos del repositorio forman parte del contexto persistente del proyecto.

Antes de realizar cambios sustanciales, consulta los documentos relevantes.

---

## `docs/PROJECT_CONTEXT.md`

Úsalo cuando necesites comprender:

* qué es EvidenceOps;
* por qué existe;
* cuál es el objetivo profesional;
* cuál es la filosofía de aprendizaje;
* qué tipo de sistema queremos construir.

Este documento debe cambiar muy poco.

---

## `docs/CURRENT_STATE.md`

Consúltalo:

* al comenzar una nueva sesión;
* antes de determinar el siguiente trabajo;
* cuando necesites comprender el estado real del repositorio.

Debe indicar:

* qué está implementado;
* cuál es el milestone actual;
* qué está pendiente;
* qué problemas conocidos existen;
* cuáles son los tests actuales;
* cuál es el siguiente paso inmediato.

---

## `docs/ROADMAP.md`

Consúltalo cuando necesites entender hacia dónde evolucionará el proyecto.

El roadmap representa dirección, no autorización.

No implementes elementos futuros sin que corresponda al milestone actual o exista una petición explícita.

---

## `docs/LEARNING.md`

Consúltalo antes de decidir cuánto detalle pedagógico necesita un concepto.

Debe permitir conocer:

* qué conceptos ha trabajado ya el desarrollador;
* qué puede darse razonablemente por conocido;
* qué conceptos todavía son nuevos.

No añadas un concepto como aprendido simplemente porque el coding agent haya escrito código que lo utiliza.

Un concepto debe considerarse aprendido únicamente cuando el desarrollador haya tenido suficiente interacción con él para comprender su función básica.

---

## `docs/DECISIONS.md`

Consúltalo antes de:

* cambiar una decisión arquitectónica existente;
* sustituir una tecnología;
* rediseñar una parte importante del sistema;
* revisitar una elección técnica anterior.

No registres decisiones triviales.

---

# Mandatory documentation maintenance

El mantenimiento de la documentación forma parte de cada tarea de desarrollo.

Antes de considerar una tarea o sesión terminada, revisa siempre si la documentación necesita actualizarse.

---

## `docs/CURRENT_STATE.md`

DEBE reflejar el estado real del repositorio.

Actualízalo cuando cambie cualquiera de estos elementos:

* funcionalidades implementadas;
* funcionalidades pendientes;
* dependencias;
* estructura importante;
* tests;
* warnings o problemas conocidos relevantes;
* milestone;
* siguiente paso inmediato.

Este será el documento que cambie con mayor frecuencia.

---

## `docs/LEARNING.md`

DEBE actualizarse cuando el desarrollador haya trabajado realmente un concepto nuevo y pueda explicar razonablemente:

* qué es;
* para qué sirve;
* por qué lo utilizamos;
* cómo aparece en EvidenceOps.

No registres como aprendizaje conceptos utilizados únicamente de forma automática por el coding agent.

No infles el documento con detalles triviales.

---

## `docs/DECISIONS.md`

DEBE actualizarse cuando:

* se tome una decisión técnica relevante;
* cambie una decisión existente;
* una decisión quede obsoleta;
* se elija entre alternativas con trade-offs significativos.

No registrar decisiones triviales.

---

## `docs/ROADMAP.md`

Actualízalo únicamente cuando cambien:

* milestones;
* prioridades;
* alcance;
* dirección técnica general;
* secuencia prevista de aprendizaje.

No modificar el roadmap como consecuencia automática de cada tarea.

---

## `docs/PROJECT_CONTEXT.md`

Debe cambiar muy raramente.

Actualízalo únicamente si cambia:

* el propósito fundamental de EvidenceOps;
* el objetivo profesional;
* la filosofía de aprendizaje;
* la definición general del proyecto.

---

# Documentation completion check

Antes de dar una tarea por terminada, comprueba explícitamente:

1. ¿`CURRENT_STATE.md` refleja lo que existe ahora?
2. ¿El desarrollador ha aprendido un concepto nuevo que deba añadirse a `LEARNING.md`?
3. ¿Se ha tomado o cambiado una decisión técnica que deba registrarse en `DECISIONS.md`?
4. ¿Ha cambiado el roadmap?
5. ¿Ha cambiado el contexto fundamental del proyecto?

Si alguna respuesta es sí, actualiza el documento correspondiente antes de considerar completada la tarea.

No actualices documentación mecánicamente cuando nada relevante haya cambiado.

Mantén los documentos:

* breves;
* actuales;
* útiles;
* coherentes con el repositorio real.

---

# Current development environment

El proyecto utiliza actualmente:

* Python 3.14;
* uv;
* FastAPI;
* Uvicorn;
* pytest;
* httpx2.

Los comandos deben ejecutarse preferentemente mediante `uv`.

Ejemplos:

```bash
uv run pytest
uv run uvicorn evidenceops.main:app --reload
```

Adapta el segundo comando si cambia la ubicación real de la aplicación.

No asumas que esta lista será permanente.

Consulta siempre el estado actual del repositorio y `docs/CURRENT_STATE.md`.

---

# Core rule

El objetivo no es construir EvidenceOps lo más rápido posible.

El objetivo tampoco es convertir cada línea de código en un ejercicio.

El objetivo es:

> **construir un sistema serio mientras el desarrollador comprende profundamente las decisiones que realmente importan.**

Cuando dudes entre enseñar o implementar directamente, pregúntate:

> ¿Entender esta parte hará al desarrollador significativamente mejor AI Engineer?

Si la respuesta es sí:

* explícalo;
* razona sobre ello;
* involucra al desarrollador cuando aporte aprendizaje.

Si la respuesta es no y es principalmente trabajo mecánico:

* impleméntalo;
* explica brevemente lo relevante;
* continúa avanzando.

El desarrollador debe entender el 100% de los conceptos importantes.

No necesita escribir manualmente el 100% del código que los utiliza.
