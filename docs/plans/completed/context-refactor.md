# Refactor de contexto — 2026-09-30

Refactor documental solicitado explícitamente. No cambia comportamiento,
producto, decisiones de aplicación ni orden M0–M19. Se completó primero en local;
el desarrollador autorizó después commit, push y PR de estos cambios estructurales.
Al publicar se conserva el ajuste del desarrollador: leer CURRENT_STATE solo
cuando la tarea dependa del presente, milestone o trabajo pendiente del proyecto.
La publicación excluye el código y tests locales de M5; su estado pendiente se
indica en CURRENT_STATE, el plan y el runbook.

## Diagnóstico

- AGENTS tenía 971 líneas: perfil, pedagogía, procedimientos y secuencia completa.
  Su lectura llevaba además a estado, roadmap y aprendizaje para trabajo ordinario.
- CURRENT_STATE mezclaba presente con verificaciones de #9–#17, intentos fallidos
  por entorno, contadores históricos de tests, commits y entregas ya confirmadas.
- README decía M4 activo y «no hay runner ni evaluadores»; código y estado ya
  reflejaban M5. D013 conservaba revisión pendiente de una issue ya completada.
- ROADMAP mantenía fases antiguas y M0–M19; AGENTS repetía la secuencia canónica.
- Propósito, perfil y pedagogía se repartían entre cuatro documentos; decisiones
  y aprendizaje eran monolitos. No había un mapa de arquitectura ni planes separados.
- Evaluation ya era un runbook útil, pero repetía el estado del baseline. La
  documentación local de observabilidad mezclaba instrucciones estables con entrega.

## Migración y conocimiento conservado

| Origen | Destino o criterio |
| --- | --- |
| AGENTS | Mapa global; pedagogía/perfil en learning/guide; secuencia en ROADMAP |
| README | Instalación, uso y pruebas; arquitectura y decisiones enlazadas |
| CURRENT_STATE | Presente/limitaciones; evidencia local de #21 en plan activo |
| DECISIONS (monolito retirado) | decisions/D001–D016 e índice; nueva D017 del refactor |
| LEARNING (monolito retirado) | learning/m0, m1, m3, m4, m5 e índice de comprensión pendiente |
| OBSERVABILITY (archivo raíz de docs retirado) | subsystems/observability y plan activo M5 |
| PROJECT_CONTEXT | Visión estable; perfil y método pedagógico en learning/guide |
| ROADMAP | Secuencia canónica existente y matices útiles de las antiguas fases |
| evaluation/README | Procedimiento conservado, enlace al estado del baseline |

Se conservaron IDs y trade-offs de las decisiones, contrato efímero, ownership,
sesiones cortas, política real de retries/deadline, gratuidad, privacidad y límites
del aprendizaje acreditado. D005 queda sustituida por D007/D008. D001–D006 se
condensan sin eliminar el motivo ni la consecuencia de las elecciones.

La ejecución real previa de #16 tuvo un éxito y nueve `rate_limit`; la promoción
se rechazó. Se conserva aquí como antecedente, mientras la limitación operativa
vive en CURRENT_STATE. Las inferencias manuales confirmadas se conservan como
aprendizaje de M3; no se repiten para validarlas. Las cifras y evidencia locales
de #21 permanecen en su plan porque todavía sirven para revisar trabajo no publicado.

Se eliminan listas duplicadas de dependencias/defaults, inventarios de tests,
verificaciones antiguas y narraciones de publicación. Código/config/tests y
Git/GitHub ya son su fuente. No se crea una copia archivada de todos los monolitos.
No se consultó GitHub para reconfirmar cierres/merges comunicados: el contexto
local bastaba y este refactor no requería alterar el estado remoto.

## Skill y mantenimiento

Una skill: `evidenceops-evaluation`. Hay un workflow repetible con entradas,
artefactos y decisiones propias: ejecución real frente a fake, promoción válida,
revisión humana y comparación compatible. Enlaza al runbook sin replicarlo.
Se mantiene en `.codex/skills` y se descubre mediante un symlink en `.agents/skills`.

No se crean skills genéricas de «implementar issue», «actualizar docs» o «cerrar
milestone»: aquí añadirían reglas repetidas sin procedimiento específico suficiente.
El mapa documental contiene reglas de mantenimiento y archivo; los planes nuevos
solo se justifican por trabajo de varias sesiones o dependencias relevantes.

## Coste aproximado de entrada

| Documento | Antes: líneas / bytes | Después: líneas / bytes |
| --- | --- | --- |
| AGENTS | 971 / 25.771 | 65 / 3.964 |
| CURRENT_STATE | 269 / 17.331 | 43 / 2.429 |
| README | 278 / 11.997 | 170 / 6.247 |

Entrada mínima AGENTS + estado: 43.102 → 6.393 bytes (−85,2%). Como heurística
bytes/4: unos 10.800 → 1.600 tokens; no es una medición del tokenizer ni del coste
completo de sesión. El prompt, herramientas, código y contexto ya inyectado también
consumen tokens; este refactor reduce principalmente lecturas de sesiones futuras.

Antes se exigían AGENTS + estado + roadmap al proponer/implementar y aprendizaje
al graduar explicaciones: 3–4 documentos extensos, más decisiones cuando aplicaba.
Tras el ajuste de publicación la entrada es AGENTS y el encargo; se añade estado
cuando la tarea lo requiere. La comparación anterior corresponde a leer ambos.
Hay más archivos en total porque decisiones e historial se pueden leer por separado;
reducir su número total no era el objetivo.

## Prueba conceptual de navegación

En todos los casos AGENTS y el encargo son la entrada. CURRENT_STATE se consulta
si hay dependencia del estado actual; código/tests según alcance. Los enlaces
no requieren cargar destinos en cascada.

| Escenario | Contexto adicional necesario |
| --- | --- |
| Issue pequeña de backend | Enunciado y criterios; sección del milestone si define alcance; código/tests afectados. Arquitectura/ADR solo si cambia un límite. Sin historial de aprendizaje. |
| Modificar evaluation | evaluation/README y código/tests pertinentes; D013, D014 o D015 solo si se revisa esa elección. Para ejecutar/comparar, cargar la skill y los artefactos necesarios. |
| Continuar M5 | Plan activo, sección M5 del roadmap; runbook de observabilidad para #21. D016 al revisar diseño; learning/m5 solo si se enseña o verifica comprensión. |
| Entender una decisión pasada | Índice ADR y una decisión, p. ej. D007 para PostgreSQL frente a SQLite. Sin leer las otras ADR ni todos los milestones. |

Prompts de ejemplo:

- «Implementa la issue #N según sus criterios; deja cambios locales y valida el comportamiento.»
- «Revisa #21 siguiendo el plan activo de M5. No hagas inferencias reales ni publiques.»
- «Usa $evidenceops-evaluation para comparar estos dos runs y sus revisiones: [rutas].»
- «Explícame por qué elegimos PostgreSQL frente a SQLite.»

## Validación y límites

Comprobados 38 archivos Markdown y 129 enlaces internos/anchors, sin destinos
rotos ni referencias a rutas retiradas. El validador de skill devuelve
`Skill is valid!`; el symlink resuelve a la única copia. Se preservan los nombres
y orden de los 20 milestones. `git diff --check` correcto.
No se ejecuta pytest por cambios exclusivamente documentales: los archivos de
aplicación, tests, dataset, configuración, lock y CI se contrastan por hash con
el árbol recibido: 35 archivos intactos, incluidos los cambios locales previos de M5.

Revisión de instrucciones conservadas: participación en decisiones y alcance
por milestone permanecen globales; pedagogía A/B/C, ayuda progresiva y umbral de
comprensión viven en learning/guide; confirmaciones del usuario, preservación
de cambios locales y publicación separada permanecen en AGENTS. Gratuidad y
secuencia están en ROADMAP; privacidad y evaluación medible siguen globales.
La obligación de revisar documentación al terminar permanece, con actualización
por responsabilidad y sin lecturas preventivas de todos los archivos.

La navegación anterior es una prueba conceptual, no un benchmark de sesiones
independientes. No se añade linter de Markdown, dependencia, plataforma de
documentación, índice vectorial ni harness de evaluación de agentes sin necesidad
demostrada. Queda por observar el uso real y, si aparecen roturas repetidas,
justificar entonces una comprobación de enlaces en CI. No se acredita al
desarrollador aprendizaje de context engineering por esta implementación automática.
