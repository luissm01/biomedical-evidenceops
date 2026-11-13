# D029 — Simplificación del roadmap pendiente a M9–M14

Estado: aceptada por el encargo explícito del desarrollador (2026-10-26).
Aplicación documental. Las milestones M9 y M10 de GitHub ya siguen esta numeración;
crear M11–M14 en GitHub queda pendiente de un encargo posterior.
El repaso breve en cada cierre queda sustituido por un repaso final consolidado
según [D035](D035-consolidated-final-learning-review.md).

## Contexto y problema

La secuencia pendiente M9–M19 separaba competencias relacionadas en once milestones.
Mantener cada bloque como una implementación independiente aumentaba tiempo,
redundancia y complejidad para un proyecto educativo y de portfolio. El objetivo
es conservar las competencias de AI Engineering y tiempo para comprenderlas y
explicarlas, profundizando especialmente en RAG, evaluación, agentes y herramientas.

## Alternativas

- Mantener once milestones: separación temática clara, pero mayor fragmentación
  y riesgo de implementar alternativas sin mejorar el aprendizaje.
- Eliminar competencias de infraestructura o adaptación: reduce trabajo, pero
  limita la experiencia práctica y la defensa técnica del sistema completo.
- Agrupar competencias relacionadas y acotar prácticas: conserva cobertura con
  menos entregas y exige distinguir experiencia práctica de estudio conceptual.

## Decisión

Adoptar la tercera alternativa. El [roadmap](../ROADMAP.md) es la única fuente
canónica del alcance vigente; la tabla explica la migración de la planificación,
no renumera trabajo histórico ni identifica milestones remotas ya modificadas.

| Planificación anterior | Planificación acordada |
| --- | --- |
| M9 — Advanced Retrieval & RAG Evaluation | M9 — Advanced RAG & Retrieval |
| M10 — Tool Calling; M11 — Agent Fundamentals; M12 — MCP Integration | M10 — Tool Calling, Agents & MCP |
| M13 — Async Processing & Distributed Systems; M14 — Production Hardening | M11 — Async Processing & Production Readiness |
| M15 — Cloud Deployment; M16 — Kubernetes Foundations | M12 — Cloud & Kubernetes Foundations |
| M17 — Advanced LLM Engineering; M18 — Fine-tuning & Model Adaptation | M13 — Advanced LLM Engineering & Model Adaptation |
| M19 — Final Production System & Portfolio | M14 — Final System, Portfolio & Technical Defense |

Una práctica representativa por competencia, unas trece issues en total y repaso
conceptual/práctico breve en cada cierre. LangGraph concentra la práctica de
agentes; reranking o reformulación se elige según evidencia; LoRA/PEFT concentra
el fine-tuning y las otras técnicas se estudian conceptualmente. Cloud queda
limitado a una práctica AWS temporal gratuita y Kubernetes local, sin operación
cloud permanente. No se eligen todavía proveedores de cola, modelos, esquemas
de fusión ni recursos cloud concretos.

## Consecuencias y límites

Se reduce el número de implementaciones y la profundidad de algunas tecnologías;
no se puede presentar el estudio conceptual como dominio práctico. Seguridad,
resiliencia y evaluación se aplican a flujos representativos, sin pretender una
plataforma comercial ni operación cloud permanente. La práctica AWS depende de
poder acotarla sin gasto; si no es viable, debe quedar documentado ese límite.

M0–M8 y sus decisiones, baselines, juicios y registros de aprendizaje se conservan.
Esta decisión actualiza únicamente la secuencia futura que D017 describía como
M0–M19; su arquitectura documental continúa vigente y no se reescribe su contexto.
No se autorizan código, inferencias, commits, push, PRs ni cambios de GitHub.
La discrepancia temporal con la planificación remota se resuelve en otro encargo.
