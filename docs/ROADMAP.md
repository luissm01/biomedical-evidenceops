EvidenceOps — Roadmap

Este roadmap representa la dirección general del proyecto.

NO significa que todas las tecnologías aquí mencionadas deban implementarse.

Cada fase se introducirá únicamente cuando exista una necesidad real.

Milestone 0 — Project foundation

Objetivo:

Crear una base mínima, profesional y comprensible.

Temas:

uv;
estructura del proyecto;
dependencies;
FastAPI;
Uvicorn;
primer endpoint;
pytest;
TestClient;
Git;
README.

Resultado esperado:

Una aplicación FastAPI mínima con:

GET /health

y tests automáticos.

Phase 1 — Software Engineering Foundations

Objetivo:

Pasar de utilizar Python principalmente para IA/notebooks a utilizarlo para construir software de producción.

Aprender progresivamente:

Python typing;
project structure;
Pydantic;
request / response models;
FastAPI;
HTTP;
REST;
status codes;
exception handling;
configuration;
environment variables;
secrets;
logging;
pytest;
fixtures;
mocking;
unit tests;
integration tests;
async / await;
dependency injection;
Docker;
CI.

No introducir complejidad que no esté justificada.

Phase 2 — Evaluation & Observability

Objetivo:

Aprender a responder:

¿Cómo sabemos que nuestro sistema funciona?

Evaluation

Introducir progresivamente:

golden datasets;
offline evaluation;
regression evaluation;
deterministic evaluators;
human evaluation;
LLM-as-a-judge;
evaluation pipelines.

Más adelante, para retrieval:

Recall@K;
Precision@K;
Hit Rate;
MRR;
NDCG.

Para generación:

groundedness;
answer relevance;
factuality;
citation correctness;
hallucination analysis.
Observability

Aprender:

logs;
metrics;
traces;
spans;
distributed tracing;
latency;
errors;
retries;
token usage;
cost.

Herramientas posibles:

OpenTelemetry;
Langfuse.

Las herramientas concretas pueden cambiar.

Los conceptos son prioritarios.

Phase 3 — RAG

Objetivo:

Construir un sistema serio de recuperación de evidencia biomédica.

Aprender:

document ingestion;
parsing;
chunking;
embeddings;
similarity;
vector search;
metadata;
semantic retrieval;
BM25;
hybrid retrieval;
reranking;
query rewriting;
contextual retrieval;
retrieval evaluation.

Posible infraestructura:

PostgreSQL;
pgvector.

No introducir una vector database dedicada salvo que exista una razón.

Las decisiones de retrieval deberán medirse mediante evaluation.

Phase 4 — Tool Calling

Objetivo:

Permitir que el modelo interactúe de forma segura y estructurada con capacidades externas.

Aprender:

function calling;
tool calling;
structured outputs;
JSON Schema;
validation;
tool selection;
retries;
timeouts;
permissions;
error handling;
fallback.

Tools potenciales de EvidenceOps:

búsqueda bibliográfica;
recuperación de metadata;
acceso a artículos;
comparación estructurada de estudios.
Phase 5 — Agents

Objetivo:

Entender los agentes desde fundamentos antes de depender de frameworks.

Aprender:

agent loop;
ReAct;
state;
routing;
planner / executor;
iteration limits;
tool execution;
memory;
failure handling;
orchestration.

Solo después considerar frameworks como:

LangGraph;
LangChain;
AutoGen;
CrewAI.
Phase 6 — MCP

Objetivo:

Entender cómo integrar EvidenceOps dentro de arquitecturas basadas en Model Context Protocol.

Aprender:

MCP architecture;
MCP client;
MCP server;
tools;
resources;
prompts.

Construir un MCP server sencillo para EvidenceOps.

Phase 7 — Production Architecture

Objetivo:

Aprender los fundamentos prácticos necesarios para sistemas distribuidos.

Introducir cuando sea necesario:

asynchronous processing;
queues;
workers;
retries;
idempotency;
caching;
event-driven architecture;
eventual consistency;
fault tolerance.

No estudiar sistemas distribuidos únicamente de forma teórica.

Introducir conceptos a partir de problemas reales del proyecto.

Phase 8 — Cloud

Objetivo:

Ser capaz de desplegar y operar EvidenceOps.

Aprender únicamente lo relevante para AI Engineering:

compute;
containers;
object storage;
managed databases;
IAM;
secrets;
networking básico;
container registries;
monitoring;
deployment.

Cloud preferente inicialmente:

AWS.
Phase 9 — Kubernetes

Objetivo:

Comprender el nivel práctico necesario para desplegar servicios containerizados.

Aprender:

Pod;
Deployment;
Service;
ConfigMap;
Secret;
health probes;
resource requests / limits;
horizontal autoscaling.

No buscamos convertirnos en Kubernetes administrators.

Phase 10 — Advanced LLM Engineering

Objetivo:

Profundizar en los fundamentos una vez dominada la construcción de sistemas.

Aprender progresivamente:

tokenization;
embeddings;
self-attention;
transformers;
positional information;
pretraining;
decoding;
inference;
KV cache;
quantization.

Después experimentar con:

PEFT;
LoRA;
QLoRA;
instruction tuning;
fine-tuning.

Comparar cuándo utilizar:

prompting;
RAG;
tool calling;
fine-tuning.

Finalmente comprender a nivel conceptual/práctico:

RLHF;
preference optimization;
reward models;
DPO;
PPO;
GRPO.
End goal

Al finalizar el proyecto, el desarrollador debería poder explicar:

cómo diseñaría un sistema de IA;
cómo lo evaluaría;
cómo lo observaría;
cómo investigaría fallos;
cómo lo desplegaría;
cómo protegería sus dependencias;
cómo diseñaría RAG;
cómo diseñaría herramientas;
cómo diseñaría un agente;
cómo escalaría el servicio;
qué trade-offs existen.


Estas son las milestones que vamos a seguir en GitHub:
Los servicios elegidos deberán poder utilizarse gratis; los milestones de
cloud y despliegue estudiarán la arquitectura sin depender de servicios
gestionados de pago ni free tiers temporales.
M0  Project Foundation
M1  Production Python & API Foundations
M2  Application Architecture & Persistence
M3  First LLM Integration
M4  Evaluation Foundations
M5  Observability
M6  Biomedical Data Ingestion
M7  Retrieval & Embeddings
M8  RAG v1
M9  Advanced Retrieval & RAG Evaluation
M10 Tool Calling
M11 Agent Fundamentals
M12 MCP Integration
M13 Async Processing & Distributed Systems
M14 Production Hardening
M15 Cloud Deployment
M16 Kubernetes Foundations
M17 Advanced LLM Engineering
M18 Fine-tuning & Model Adaptation
M19 Final Production System & Portfolio
