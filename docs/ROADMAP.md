# Roadmap canónico

Única fuente de la secuencia y alcance M0–M19. Se conserva la secuencia acordada;
las antiguas “Phase 1–10” eran agrupaciones superpuestas y dejan de usarse.
El [estado](CURRENT_STATE.md) identifica el milestone activo; los planes detallan
ejecución. Lee la sección necesaria, no todas las fases.

El roadmap expresa dirección, no autorización. Introduce tecnologías cuando
un problema real lo justifique; discute dependencias futuras antes de implementarlas.
Cambiar orden o alcance requiere acuerdo explícito, ADR y actualización de los
milestones de GitHub. No exige cambios remotos esta reorganización documental.

Los servicios elegidos deben poder usarse gratis: cloud y despliegue estudiarán
arquitectura sin depender de servicios gestionados de pago ni free tiers temporales.
AWS es la orientación inicial; conocer servicios gestionados no autoriza contratarlos.

## M0 — Project Foundation

Repository, uv, project structure, FastAPI basics, health endpoint,
testing fundamentals, Git and basic documentation.

## M1 — Production Python & API Foundations

Pydantic, request/response contracts, validation, error handling,
typing, API design and relevant Python production practices.

## M2 — Application Architecture & Persistence

Separation of responsibilities, service boundaries, persistence,
PostgreSQL, configuration, database access and migrations when the
project creates a real need for them.

## M3 — First LLM Integration

Introduce an LLM behind a clean application boundary.
Learn model APIs, structured outputs, configuration, failures,
timeouts and provider abstraction where justified.

## M4 — Evaluation Foundations

Golden datasets, baselines, deterministic evaluation,
regression testing, human evaluation and evaluation-driven
development.

## M5 — Observability

Structured logging, metrics, traces, spans, latency, errors,
token/cost tracking and OpenTelemetry / LLM observability concepts.

## M6 — Biomedical Data Ingestion

Public biomedical sources, document acquisition, parsing,
normalization, metadata and ingestion pipelines.

## M7 — Retrieval & Embeddings

Embeddings, similarity search, chunking, vector storage,
metadata filtering and retrieval metrics.

## M8 — RAG v1

Build the first complete retrieval-augmented generation pipeline
using previously learned retrieval and evaluation concepts.

## M9 — Advanced Retrieval & RAG Evaluation

BM25, hybrid search, reranking, query rewriting and systematic
comparison of retrieval/RAG strategies.

## M10 — Tool Calling

Structured tools, JSON schemas, validation, tool selection,
retries, permissions, timeouts and error handling.

## M11 — Agent Fundamentals

Agent loops, ReAct, state, routing, planner/executor patterns,
iteration limits and failure handling before introducing
high-level agent frameworks.

## M12 — MCP Integration

MCP architecture, clients, servers, tools, resources and prompts.
Expose useful EvidenceOps capabilities through MCP.

## M13 — Async Processing & Distributed Systems

Workers, queues, asynchronous jobs, retries, idempotency,
caching, eventual consistency and practical distributed-system
failure modes.

## M14 — Production Hardening

Security, authentication/authorization where justified,
secrets, rate limiting, resilience, health/readiness checks,
operational testing and production failure scenarios.

## M15 — Cloud Deployment

Containers, compute, storage, managed databases, IAM,
networking, secrets, monitoring and deployment in AWS.

## M16 — Kubernetes Foundations

Pods, Deployments, Services, ConfigMaps, Secrets, probes,
resources and autoscaling at the level relevant to an AI Engineer.

## M17 — Advanced LLM Engineering

Tokenization, transformers, inference, KV cache, quantization
and deeper understanding of foundation-model behavior.

## M18 — Fine-tuning & Model Adaptation

PEFT, LoRA, QLoRA, dataset preparation, evaluation and explicit
comparison between prompting, RAG, tool use and fine-tuning.
RLHF/DPO/PPO/GRPO are introduced according to their professional
relevance, primarily conceptually unless practical experimentation
is justified.

## M19 — Final Production System & Portfolio

Integrate and harden EvidenceOps as a coherent product.
Final evaluation, architecture documentation, deployment,
portfolio-quality README, diagrams and interview preparation.


## Detalles y límites de progresión

- **M3:** generar para una pregunta persistida, contrato validado, proveedor tras
  frontera mínima, errores y pruebas sin red. Gemini es el único proveedor acordado;
  Ollama aplazado hasta que una comparación lo justifique. No persistir respuestas
  ni introducir orquestación. La demostración de integración no demuestra factualidad.
  Se acepta timeout de transporte sin deadline global: [D011](decisions/D011-gemini.md).
- **M4:** dataset, outputs trazables y revisión humana/regresiones. Métodos
  deterministas y evaluación humana antes de añadir LLM-as-a-judge si se justifica.
  Los motivos del método inicial están en D013–D015; no se mide retrieval sin tenerlo.
- **M5:** logs, métricas y trazas para investigar latencia, errores, retries,
  uso de tokens y coste. OpenTelemetry/Langfuse son opciones, no elecciones impuestas.
  Secuencia de trabajo existente en el [plan activo](plans/active/m5-observability.md).
- **M7/M9:** Recall@K, Precision@K, Hit Rate, MRR y NDCG cuando exista retrieval;
  metadata, query rewriting y contextual retrieval según fallos medidos. PostgreSQL
  con pgvector es una posibilidad; DB vectorial dedicada solo con justificación.
- **M8/M9:** medir groundedness, relevancia, factualidad, citas y alucinaciones sobre
  el pipeline completo. Comparar estrategias con baseline y datasets reproducibles.
- **M10:** tools potenciales de búsqueda bibliográfica, metadata, artículos y
  comparación de estudios; fallback, validación y límites ante fallos reales.
- **M11:** memoria y orquestación después del loop básico. LangGraph, LangChain,
  AutoGen o CrewAI solo tras comprender mecanismos y justificar la abstracción.
- **M13:** async/await, event-driven architecture y tolerancia a fallos cuando el
  flujo necesite procesos distribuidos; no como ejercicios aislados.
- **M17:** profundizar también en self-attention, información posicional,
  pretraining y decoding para explicar comportamiento e inferencia.
- **M18:** instruction tuning, reward models y optimización de preferencias según
  relevancia; comparación medida con prompting, RAG y tools antes de adoptar tuning.
