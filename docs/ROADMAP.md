# Roadmap canónico

Única fuente de la secuencia y alcance M0–M14. La simplificación acordada reduce
las once milestones pendientes M9–M19 a seis (M9–M14), con unas trece issues en
conjunto. M0–M8 conservan su alcance, historial y decisiones. La correspondencia
con la planificación anterior y los trade-offs quedan en
[D029](decisions/D029-roadmap-simplification.md).
El [estado](CURRENT_STATE.md) identifica el trabajo presente; los planes detallan
la ejecución. Las antiguas “Phase 1–10” no se usan.

El roadmap expresa dirección, no autorización para implementar fases futuras.
Cambiar orden o alcance requiere acuerdo explícito, ADR y posterior sincronización
de milestones de GitHub. Las milestones M9 y M10 de GitHub ya siguen esta
secuencia; crear M11–M14 requiere un encargo posterior.

## Principios de progresión

- Priorizar aprendizaje demostrable sobre acumulación de funcionalidades.
- Realizar una implementación práctica representativa por competencia; evitar
  alternativas redundantes y frameworks sin necesidad concreta.
- Profundizar especialmente en RAG, evaluación, agentes y herramientas.
- Acotar cloud, Kubernetes y sistemas distribuidos a prácticas útiles y medibles.
- Reservar tiempo para comprender y explicar decisiones, alternativas y trade-offs.
- Cerrar cada milestone con un breve repaso conceptual y práctico según la
  [guía de aprendizaje](learning/guide.md#cierre-de-milestone).
- Introducir arquitectura solo cuando el problema actual la necesite.
- Mantener EvidenceOps como proyecto educativo y de portfolio, no comercial.

Se mantiene la restricción de gratuidad: no depender de servicios gestionados de
pago ni de free tiers temporales para operar el proyecto. En M12 se contempla
una práctica temporal en AWS, condicionada a verificar previamente que pueda
realizarse sin gasto. Definir recursos, límites, monitorización y retirada antes
de desplegar; una alerta de presupuesto no garantiza por sí sola coste cero.
Si no se puede garantizar ese alcance gratuito, documentar el diseño y el límite
sin provisionar recursos. No mantener infraestructura cloud permanente.

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

## M9 — Advanced RAG & Retrieval

Búsqueda híbrida (BM25 + semántica), una mejora mediante reranking o reformulación
de consultas y evaluación comparativa frente a los baselines de retrieval M7 y
RAG M8. Elegir la mejora a partir de fallos observados; no implementar ambas por
completitud. Separar calidad de retrieval y de generación, con corpus, juicios y
casos reproducibles. Aproximadamente **2 issues**; [plan M9](plans/m9-advanced-rag-retrieval.md).

## M10 — Tool Calling, Agents & MCP

Herramientas estructuradas con esquemas, selección y validación; agente con
LangGraph, estado, routing y límites de ejecución. Comprender el loop y sus
fallos antes de abstraerlos, sin construir un segundo agente redundante.
Integrar MCP sobre capacidades útiles de EvidenceOps, comprendiendo clientes,
servidores, tools, resources y prompts. Acotar permisos, timeouts, errores y
reintentos. Aproximadamente **3 issues**: herramientas, agente e integración MCP.

## M11 — Async Processing & Production Readiness

Un flujo real con cola/worker, estado del trabajo, reintentos acotados e
idempotencia. Explicar async/await, entrega y consistencia eventual a partir de
ese flujo. Seguridad y resiliencia proporcionadas: secretos, validación,
autenticación/autorización y rate limiting donde se justifiquen; health/readiness,
caídas de dependencias y recuperación verificables. Evitar añadir caché o más
servicios sin necesidad medida. Aproximadamente **2 issues**: procesamiento
asíncrono y preparación operativa con escenarios de fallo.

## M12 — Cloud & Kubernetes Foundations

Despliegue temporal en AWS bajo las restricciones de coste anteriores: contenedores,
compute, almacenamiento, IAM, red, secretos y observabilidad del despliegue.
Estudiar servicios gestionados sin obligación de contratarlos. Practicar Kubernetes
local: Pods, Deployments, Services, ConfigMaps, Secrets, probes y recursos;
comprender escalado y sus límites sin exigir un clúster cloud ni alta disponibilidad.
Aproximadamente **2 issues**: práctica AWS temporal con retirada y Kubernetes local.

## M13 — Advanced LLM Engineering & Model Adaptation

Fundamentos de tokenización, transformers, self-attention, información posicional,
pretraining, decoding y KV cache para explicar inferencia. Experimentos acotados
de inferencia y cuantización; un fine-tuning controlado con LoRA/PEFT, dataset y
evaluación frente a una referencia sin adaptación. Justificar cuándo usar prompting,
RAG, tools o fine-tuning. Estudiar QLoRA, instruction tuning, reward models y
RLHF/DPO/PPO/GRPO conceptualmente, sin exigir implementaciones adicionales.
Usar recursos gratuitos disponibles y acordar el presupuesto experimental antes
de ejecutar. Aproximadamente **2 issues**: inferencia/cuantización y LoRA/PEFT.

## M14 — Final System, Portfolio & Technical Defense

Integrar y evaluar el sistema final frente a sus baselines, documentando fortalezas,
regresiones y límites. Demo reproducible, README y diagramas para portfolio,
documentación arquitectónica y defensa técnica completa: decisiones, alternativas,
fallos, evaluación, costes y trade-offs. Consolidar lo construido sin ampliar el
alcance hacia un producto comercial. Aproximadamente **2 issues**: integración,
evaluación y demo; portfolio y defensa técnica.

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
  Secuencia de trabajo conservada en el [plan completado](plans/completed/m5-observability.md).
- **M9:** usar las métricas de retrieval existentes y ampliar solo si aporta
  información (Recall@K, Precision@K, Hit Rate, MRR o NDCG según los juicios).
  Evaluar relevancia, groundedness, factualidad, citas y alucinaciones con la
  rúbrica RAG existente, respetando sus límites. Comparar candidatos con entradas
  congeladas; no cambiar etiquetas para favorecerlos ni confundir tests de
  contrato con calidad IA. No añadir una base vectorial dedicada sin necesidad.
- **M10:** reutilizar capacidades existentes como herramientas; memoria,
  planner/executor u otros patrones solo si el caso lo requiere. LangGraph es la
  práctica acordada, sin implementar además LangChain, AutoGen o CrewAI.
- **M11–M14:** integrar seguridad, operación y evaluación según el problema de
  cada milestone; el cierre final no exige rehacer cada competencia con otra tecnología.
- **Todas:** tests/CI sin inferencias reales. Las ejecuciones reales requieren
  encargo y recursos gratuitos disponibles; la excepción consumida en M8 no se
  extiende a futuros candidatos. El número de issues es orientativo, no un backlog
  creado ni una autorización de ejecución.
