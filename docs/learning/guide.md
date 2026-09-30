# Colaboración y objetivos de aprendizaje

Consultar al enseñar, graduar una explicación o introducir un concepto importante;
no forma parte de la lectura normal de una corrección mecánica.

## Perfil y objetivos

Ingeniero de la Salud/Biomédico, completando un Máster en IA, con investigación en
Deep Learning para imagen médica. Experiencia profesional en Java, jBPM, REST,
SQL/Oracle, FHIR/HL7, Docker, Git, debugging e integración sanitaria en producción.
Experiencia previa en Python, PyTorch, TensorFlow, Scikit-learn, CNN/U-Net,
clasificación/segmentación, transfer learning, explainability, MLflow, DVC,
GitHub Actions y AWS básico. No necesita empezar ML desde cero.

Objetivos: Python de producción y backend; arquitectura, evaluation y observability
de IA; RAG, tools, agentes y MCP; MLOps/LLMOps, sistemas distribuidos y despliegue.
La secuencia y los temas futuros viven únicamente en el [roadmap](../ROADMAP.md).

## Cómo colaborar

Aprender construyendo: problema → concepto necesario → razonamiento → implementación
→ validación/medición → mejora. No anticipar teoría sin un problema que la justifique.

| Nivel | Tratamiento |
| --- | --- |
| A: arquitectura, AI Engineering, evaluación, observabilidad, fallos y sistemas distribuidos | Explicar problema y alternativas, recomendar con trade-offs, dejar razonar al desarrollador y revisar las partes críticas. Profundizar sin prisa. |
| B: conceptos ordinarios de implementación (Pydantic, typing, parámetros, pytest básico) | Explicación breve aplicada a EvidenceOps, comportamiento importante y comprobación razonable de comprensión; un ejemplo suele bastar. |
| C: boilerplate, YAML, repetición, refactors mecánicos | Implementar directamente y explicar solo lo no obvio. |

No convertir cada línea en ejercicio ni preguntar después de cada explicación.
Repetir solo a petición, ante confusión o errores. Cuando un patrón se comprende,
automatizar nuevas instancias. La sintaxis puede consultarse: importa explicar
qué hace, por qué se usa, qué puede fallar y dónde investigarlo.

Ante bloqueo pedagógico: pista conceptual → pista concreta → pseudocódigo →
fragmento parcial → solución completa si sigue haciendo falta. No aplicar esta
escalera a errores triviales o trabajo mecánico.

Al generar código significativo, explicar el diseño, implementarlo, destacar
decisiones/comportamientos importantes y facilitar su revisión. El desarrollador
debe comprender el sistema sin escribir todas sus líneas. Los registros de
[aprendizaje](README.md) distinguen interacción confirmada de código generado;
no acreditar dominio por haber usado automáticamente una tecnología.
