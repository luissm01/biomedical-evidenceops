# Mapa del conocimiento

Entrada del agente: [AGENTS](../AGENTS.md) + encargo recibido → solo la
fuente pertinente según este mapa. Este índice sirve para descubrir contexto;
no es una lista de lectura obligatoria. Los enlaces tampoco implican cargar sus
destinos en cascada.

| Necesidad | Fuente de verdad | Cuándo leer |
| --- | --- | --- |
| Operar el repositorio | [README](../README.md) | Instalación, API y pruebas |
| Propósito permanente | [Visión](PROJECT_CONTEXT.md) | Producto, objetivos profesionales |
| Responsabilidades y límites | [Arquitectura](ARCHITECTURE.md) | Cambios que cruzan componentes |
| Presente y próximo paso | [Estado](CURRENT_STATE.md) | Cuando la tarea dependa del estado, milestone o trabajo en curso |
| Orden y alcance M0–M19 | [Roadmap](ROADMAP.md) | Sección del milestone afectado |
| Por qué una elección | [ADRs](decisions/README.md) | Índice y decisión del área |
| Trabajo en curso | [Plan M5](plans/active/m5-observability.md) | Continuar observabilidad |
| Trabajo histórico útil | [Planes completados](plans/completed/README.md) | Investigación histórica |
| Cómo enseñar / qué se ha trabajado | [Aprendizaje](learning/README.md) | Solo tareas pedagógicas |
| Dataset, runs y revisión | [Evaluation](../evaluation/README.md) | Evaluación del generador |
| Eventos y diagnóstico | [Observabilidad](subsystems/observability.md) | Cambiar/usar logs |
| Workflow de evaluación asistida | [Skill evaluation](../.codex/skills/evidenceops-evaluation/SKILL.md) | Ejecutar, revisar o comparar evaluaciones |

## Fuentes automáticas

Dependencias y Python: [pyproject.toml](../pyproject.toml), [lock](../uv.lock) y
[versión local](../.python-version). Configuración: [.env.example](../.env.example)
y [config.py](../src/evidenceops/config.py). Comportamiento: código y
[tests](../tests). CI: [workflow](../.github/workflows/ci.yml).
Historial: Git. Entrega: [issues](https://github.com/luissm01/biomedical-evidenceops/issues),
[PRs](https://github.com/luissm01/biomedical-evidenceops/pulls) y
[milestones](https://github.com/luissm01/biomedical-evidenceops/milestones).
No copies inventarios de versiones, tests, commits o estados remotos a los documentos.
No consultes GitHub solo para confirmar acciones que el desarrollador ya confirmó.

## Mantener

- **Estado:** actualiza capacidades presentes, trabajo local pendiente, limitación
  relevante o siguiente paso; reemplaza el estado anterior. No acumules verificaciones.
- **Arquitectura/subsistema/README:** actualiza cuando cambien límites, contrato
  operativo o procedimiento que el documento explica; enlaza al código para detalles.
- **ADR:** una elección duradera con alternativas y trade-offs merece documento
  individual e índice. Conserva ID, contexto, decisión, consecuencias y estado;
  una decisión sustituida enlaza a su reemplazo. No registres imports/refactors triviales.
- **Plan:** crea uno si el trabajo necesita varias sesiones, dependencias o un
  traspaso de contexto que la issue no cubre. Incluye alcance, próximos pasos,
  decisiones abiertas y evidencia. Una issue pequeña no necesita un plan.
- **Archivo:** al completar un plan, lleva reglas duraderas a su fuente, mueve
  el plan a `plans/completed/` y enlázalo desde su índice. No dupliques el historial
  de GitHub. El archivo no forma parte de la lectura normal.
- **Aprendizaje:** actualiza solo el milestone trabajado y con interacción real
  del desarrollador; implementación asistida no acredita comprensión. La guía
  contiene objetivos y pedagogía; los registros, evidencia y límites del aprendizaje.
- **Roadmap/visión:** solo cambian por alcance, secuencia o propósito acordados.
- **Skill:** crea una solo ante un workflow repetible con instrucciones propias
  que mejoren decisiones; descripción precisa y cuerpo breve, sin copiar runbooks.
- **Sin cambio relevante, sin actualización.** Antes de cerrar una tarea revisa
  estas fuentes por su responsabilidad, sin leer todos los documentos. Mantener
  contexto local no autoriza commit, push, PR, cierre de issue ni inferencia real.

## Descubrimiento de skills

Se conserva `.codex/skills/<nombre>/SKILL.md` como ubicación de autoría pedida.
Cada carpeta se enlaza desde `.agents/skills/`, ruta de descubrimiento actual
según [OpenAI](https://learn.chatgpt.com/docs/build-skills), que admite symlinks.
Hay una sola copia del contenido. Si el cliente no muestra la skill, abre el
archivo enlazado arriba; no presupongas que el selector la cargó.
