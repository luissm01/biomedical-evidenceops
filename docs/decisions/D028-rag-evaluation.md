# D028 — Evaluación RAG end-to-end y baseline (#47)

## Estado

Método aceptado por las decisiones explícitas del encargo de #47.
Implementación local; diez casos asistidos aprobados por el desarrollador con
corrección de r09 y auditoría contra el corpus completo. Una corrida real
completa, revisión humana asistida aprobada (58 pass, 0 fail, 2 N/A) y baseline
promocionado. El estado de integración y cierre de #47/M8 vive en Git/GitHub.
[Informe y límites](../../evaluation/rag/REPORT-v1.md); sin consenso clínico experto.

## Problema y alternativas

El baseline M7 mide recuperación; M4 evalúa generación sin fuentes. Ninguno
permite atribuir una respuesta RAG deficiente a evidencia no recuperada, pérdida
por presupuesto o interpretación del generador. Citas bien formadas no prueban
apoyo semántico. Se podría puntuar cada afirmación o añadir un juez LLM/framework,
pero introduciría segmentación, coste y variabilidad que no justifican diez casos.
Duplicar corpus, runner de indexación y revisión produciría contratos divergentes.

## Decisión

Evaluar la respuesta completa con diez casos previos a outputs: cuatro con
evidencia suficiente, dos parcial, dos ausente y dos con distractores plausibles.
Reutilizar el snapshot público M7 y su aislamiento/indexador/buscador, y los
mecanismos M4 de identidad de run, revisión vinculada a hash, agregación y
transiciones. Las etiquetas RAG se justifican desde los abstracts; no se infieren
de rankings ni de juicios M7 que respondían otras preguntas.

Ejecutar el servicio RagService real, fuera del transporte HTTP, con un observador
opcional del contexto y un wrapper del generador que conserva la salida tipada
antes de validar citas. No se reconstruye un pipeline alternativo ni se repiten
llamadas para obtener trazas. El transporte mantiene sus pruebas deterministas.
El recurso PostgreSQL aislado se extrae del runner M7 sin cambiar su política.

Se guardan configuración/versiones, entradas con hashes congelados, top-5,
contexto efectivo, fuentes omitidas/incluidas, output tipado/final y errores
seguros. Checkpoint por caso, sin retry ni reanudación propios. Las unidades se
reconstruyen desde el corpus para validar identidad, fingerprint y texto; se
reproduce localmente la orquestación con datos guardados y se reutiliza D026
para formato/pertenencia/cobertura. Esto verifica trazabilidad, no semántica.
La validación adicional del run se incorpora a la validación común de M4 mediante
un método de extensión; también protege prepare/aggregate usados como funciones.

Revisión humana separada en seis dimensiones: groundedness, citas semánticas,
relevancia, afirmaciones no respaldadas, abstención y limitaciones. Pass/fail por
respuesta/dimensión; fail exige motivo. N/A exige motivo y solo corresponde a
citas semánticas en abstención exacta, que no contiene afirmaciones citadas.
Las otras dimensiones siguen siendo aplicables. M4 conserva sus juicios binarios y versión de revisión 1; RAG usa `rag-1`.
N/A no cuenta como pass/fail ni compensa regresiones; sus transiciones se muestran
como cambios de aplicabilidad que requieren inspección.

Distinguir fallos técnicos de errores semánticos. Un fallo técnico/validación de
citas deja run fallido; no se transforma en fail de contenido ni se promociona.
Los anclajes documentales ausentes de top-5 o descartados del contexto generan
diagnósticos separados, no juicios automáticos sobre toda la evidencia. Las
métricas M7 se reutilizan con denominadores explícitos sobre anclajes; no se
presentan como relevancia exhaustiva. La revisión humana localiza y explica
fallos semánticos consultando esos diagnósticos.

La promoción requiere run completo y revisión humana completa vinculada a sus
hashes. Conserva run y revisión; no exige todos los juicios pass: el baseline es
referencia del sistema, no certificación de calidad. Se compara solo el mismo
dataset/corpus exacto y se conservan regresiones y mejoras por separado.

## Consecuencias y límites

La muestra es pequeña y asistida; no demuestra revisión experta, generalización,
factualidad automática ni acuerdo entre revisores. Las fuentes son abstracts,
no texto completo. Capturar salidas públicas facilita revisar errores de citas,
pero no se conservan cuerpos de error arbitrarios del proveedor ni secretos.
Los hashes no autentican ejecuciones/revisores ni reconstruyen código dirty;
conservar el código con un baseline real es responsabilidad de quien lo establece.

No hay cambios de proveedor para sortear cuota, LLM-as-a-judge,
nueva infraestructura ni optimizaciones M9. La revisión de los diez casos precede
a cualquier corrida real. Procedimiento, rúbrica y comandos viven únicamente en
[evaluation/rag/README.md](../../evaluation/rag/README.md).

El desarrollador autorizó excepcionalmente una única corrida con el saldo
recargado existente de DeepSeek el 2026-10-24, sin retries/fallback y con los
límites ya preparados. La excepción no cambia el criterio general de gratuidad
ni autoriza repeticiones; quedó consumida por esa corrida.
