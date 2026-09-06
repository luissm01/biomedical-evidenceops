EvidenceOps — Engineering Decisions

Este documento registra únicamente decisiones técnicas que merezca la pena recordar.

No registrar decisiones triviales.

Para cada decisión importante intentar conservar:

problema;
opciones consideradas;
decisión;
motivos;
trade-offs.
D001 — Use uv for Python project management
Status

Accepted.

Problem

Necesitamos gestionar:

dependencias;
entorno virtual;
lock file;
ejecución consistente del proyecto.
Decision

Utilizar uv como herramienta principal para la gestión del proyecto Python.

Reasoning

Permite centralizar gran parte del workflow de desarrollo con una herramienta rápida y moderna.

Además proporciona:

dependency management;
virtual environment management;
lock file;
ejecución mediante uv run.
Trade-offs

El proyecto dependerá de una herramienta adicional que algunos desarrolladores pueden no conocer.

No obstante, los conceptos subyacentes siguen siendo los mismos:

Python environment;
dependencies;
dependency resolution.
D002 — Use a src/ project layout
Status

Accepted.

Problem

Necesitamos decidir dónde vive el paquete Python principal.

Decision

Utilizar:

src/evidenceops/

como ubicación del paquete.

Reasoning

Separa claramente:

código de la aplicación;
tests;
documentación;
configuración del repositorio.

También ayuda a evitar imports accidentales desde el directorio del repositorio durante desarrollo y testing.

Trade-offs

Introduce un nivel adicional de directorio frente a colocar directamente:

evidenceops/

en la raíz.

La ligera complejidad adicional se considera aceptable.

D003 — Separate runtime and development dependencies
Status

Accepted.

Problem

No todas las dependencias utilizadas durante el desarrollo son necesarias para ejecutar EvidenceOps.

Decision

Separar:

Runtime
FastAPI;
Uvicorn.
Development
pytest;
httpx2.
Reasoning

Permite distinguir claramente entre:

lo que necesita la aplicación;
lo que necesita el entorno de desarrollo/testing.
Trade-offs

Añade una pequeña cantidad de gestión adicional de dependencias, pero representa mejor cómo se estructuran proyectos reales.

D004 — Start with the smallest useful API
Status

Accepted.

Problem

EvidenceOps terminará siendo un sistema complejo, pero introducir toda la arquitectura desde el principio dificultaría el aprendizaje y produciría sobrearquitectura.

Decision

Comenzar con una aplicación mínima que expone:

GET /health

antes de introducir otras capas.

Reasoning

Permite aprender progresivamente:

FastAPI;
Uvicorn;
HTTP;
routing;
testing;
estructura del proyecto.

sin introducir componentes que todavía no resuelven ningún problema real.

Trade-offs

Parte de la arquitectura futura deberá añadirse o refactorizarse posteriormente.

Esto se considera intencional.

No diseñaremos hoy para problemas que todavía no tenemos.

Future decisions

Todavía NO se han tomado decisiones sobre:

database;
PostgreSQL;
vector store;
embeddings;
LLM provider;
RAG architecture;
observability platform;
queue system;
agent framework;
MCP architecture;
cloud deployment;
Kubernetes.

Estas decisiones deberán tomarse cuando exista suficiente contexto para evaluar sus trade-offs.