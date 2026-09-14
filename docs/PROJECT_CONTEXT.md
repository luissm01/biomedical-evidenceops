EvidenceOps — Project Context
What is EvidenceOps?

EvidenceOps será una plataforma de inteligencia sobre evidencia biomédica pública.

Permitirá realizar preguntas biomédicas y utilizar sistemas de IA para recuperar, analizar y sintetizar evidencia científica.

Ejemplo conceptual:

¿Qué evidencia existe sobre una determinada intervención para una determinada población?

El sistema podrá evolucionar progresivamente para:

buscar literatura científica;
recuperar documentos relevantes;
localizar fragmentos relevantes;
rerankear resultados;
extraer información estructurada;
generar respuestas grounded en evidencia;
mostrar las fuentes utilizadas;
utilizar herramientas externas;
comparar estudios;
identificar incertidumbre o evidencia contradictoria;
ejecutar workflows mediante agentes.

No se utilizarán datos clínicos privados o sensibles.

El proyecto utilizará principalmente datos y literatura biomédica pública.

Why are we building it?

EvidenceOps no pretende ser simplemente otro chatbot.

El proyecto existe para aprender a construir:

sistemas de IA que alguien estaría dispuesto a desplegar en producción.

El resultado final debe permitir demostrar competencias propias de puestos como:

AI Engineer;
Applied AI Engineer;
Machine Learning Engineer;
Healthcare AI Engineer;
Medical AI Engineer.
Developer background

El desarrollador es Ingeniero de la Salud / Ingeniero Biomédico y está completando un Máster en Inteligencia Artificial.

Tiene experiencia profesional desarrollando software sanitario con:

Java;
jBPM;
REST APIs;
SQL / Oracle;
FHIR / HL7;
Docker;
Git;
debugging;
integración de sistemas;
software en producción.

Tiene experiencia previa en IA con:

Python;
PyTorch;
TensorFlow;
Scikit-learn;
CNN;
U-Net;
transfer learning;
clasificación;
segmentación;
explainability;
MLflow;
DVC;
GitHub Actions;
AWS básico.

También cuenta con experiencia investigadora en Deep Learning aplicado a imagen médica.

Main knowledge gaps

El objetivo no es volver a estudiar Machine Learning desde cero.

Las principales áreas a desarrollar son:

Software Engineering
Python orientado a producción
typing
backend
APIs
FastAPI
async Python
Pydantic
testing
configuration
packaging
error handling
Docker
CI/CD
AI Systems
arquitectura de sistemas de IA
evaluation
observability
tracing
RAG
tool calling
agents
MCP
Production
databases
queues
workers
caching
retries
idempotency
distributed systems
cloud
Kubernetes
Advanced LLM Engineering

Más adelante:

LLM fundamentals
inference
quantization
fine-tuning
LoRA / QLoRA
RLHF
DPO
PPO
GRPO
Learning philosophy

El aprendizaje será principalmente:

learning by building.

El ciclo habitual será:

Problema
   ↓
Concepto
   ↓
Razonamiento
   ↓
Implementación
   ↓
Medición
   ↓
Mejora

No se pretende estudiar meses de teoría antes de construir.

La teoría aparecerá cuando sea necesaria para resolver problemas reales del proyecto.

El trabajo será asistido por IA: el desarrollador debe comprender, revisar,
modificar y depurar el código, sin necesidad de escribir cada línea ni memorizar
sintaxis. Las decisiones de arquitectura y AI Engineering requieren participación
y profundidad; los conceptos ordinarios, una explicación breve aplicada al
proyecto; el trabajo mecánico puede automatizarse. Evitar preguntas constantes y
ejercicios repetitivos cuando el patrón ya se entiende. `AGENTS.md` concreta esta
política para la colaboración diaria.

Project philosophy

Prioridades:

conceptos transferibles;
comprensión de arquitectura;
evaluación;
observabilidad;
testing;
decisiones justificables;
simplicidad;
progresión incremental.

Evitar:

tutorial-driven development;
framework-driven development;
sobrearquitectura;
añadir tecnologías únicamente por moda;
implementar funcionalidades futuras antes de necesitarlas.
Definition of success

EvidenceOps será un proyecto exitoso si el desarrollador puede explicar con confianza:

cómo está construido;
por qué está construido así;
cómo se prueba;
cómo se evalúa;
cómo se observa;
cómo se despliega;
qué ocurre cuando falla;
cómo investigar problemas;
qué trade-offs arquitectónicos existen.

En una entrevista, el objetivo no es poder decir:

"He utilizado X framework."

El objetivo es poder explicar:

"Tenía este problema, consideré estas alternativas, elegí esta solución por estas razones y medí el resultado de esta forma."
