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
Pydantic (dependencia directa desde su uso en modelos propios);
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

D005 — Registro temporal de preguntas en memoria

Status

Accepted para la primera versión de Fase 1.

Problem

Necesitamos registrar y consultar preguntas para trabajar el contrato de la API.
El desarrollador considera que conservarlas tras un reinicio no es necesario
en esta primera versión, aunque sí será útil en un producto más completo.

Options and decision

Un diccionario en memoria permite trabajar este flujo sin gestionar todavía
una base de datos. El almacenamiento persistente conservaría los registros,
pero introduciría configuración, esquema y gestión de datos en este incremento.
Se elige un diccionario por proceso; la tecnología de persistencia queda pendiente.

Contract and trade-offs

`POST /questions` crea un registro con UUID generado por el servidor; devuelve
`201`, su `id` y `text`, y una cabecera `Location`. `GET /questions/{question_id}`
permite recuperarlo, con `404` para un UUID ausente y `422` para uno inválido.
El texto se recorta en sus extremos, admite de 1 a 2.000 caracteres y no se
aceptan campos extra. Repetir un POST crea otro registro.

Los datos se pierden al reiniciar o recargar el servidor, no se comparten entre
workers y no se limita aún el número de registros. El alcance es desarrollo
local temporal con un único proceso. Cuando se incorpore persistencia se podrá
conservar el contrato HTTP y reemplazar el acceso al diccionario; no se introduce
una abstracción Repository por anticipación.

D006 — Seguimiento de trabajo y revisión en GitHub

Status

Accepted.

Problem and decision

Los cambios locales de preguntas y CI se habían acumulado sin seguimiento en
GitHub. Se acuerda usar un milestone para Fase 1 e issues con criterios de cierre
para las tareas actuales, ramas de trabajo y PRs antes de integrar en main.
La documentación del repositorio conserva el contexto técnico y de aprendizaje;
las issues conservan el estado de entrega. No se crean tareas de fases futuras.

Trade-offs

El seguimiento requiere mantener ambos contextos coherentes, pero permite revisar
el alcance y la validación de cada cambio. Para separar el trabajo ya acumulado,
la PR inicial de CI parte de la rama de preguntas; tras integrar preguntas debe
cambiarse su base a main y comprobar de nuevo CI. Esta dependencia es puntual.

D007 — PostgreSQL local para la primera persistencia duradera

Status

Accepted.

Problem

El diccionario por proceso pierde las preguntas al reiniciar y no representa
una dependencia de datos compartida por varias instancias de la aplicación.
Necesitamos persistencia duradera sin depender de servicios de pago.

Options and decision

SQLite ofrece persistencia transaccional con una puesta en marcha mínima, pero
su ejecución embebida no permite trabajar varios aspectos relevantes de una
base de datos de producción. PostgreSQL introduce un servicio independiente,
conexiones, configuración y una estrategia de testing más exigente.

Se elige PostgreSQL ejecutado localmente. No se utilizará una base de datos
gestionada, una tarjeta de crédito ni un free tier temporal. El desarrollador
prefiere asumir la complejidad local para aprender una arquitectura más
representativa de producción.

Trade-offs

La aplicación necesitará una instancia local de PostgreSQL y más configuración
que con SQLite. A cambio, trabajaremos límites reales entre procesos,
concurrencia, conexiones y transacciones. Esta decisión también evita una
migración inmediata desde una base embebida, sin autorizar todavía `pgvector`
ni componentes de retrieval de milestones futuros.

D008 — SQLAlchemy ORM síncrono, Psycopg y Alembic

Status

Accepted.

Problem

Necesitamos integrar PostgreSQL con Python, definir los límites transaccionales
y evolucionar el esquema sin mezclar estas responsabilidades con los modelos
del contrato HTTP.

Options and decision

Se consideraron SQL directo mediante Psycopg, SQLAlchemy Core y SQLAlchemy ORM.
El acceso directo ofrece máxima visibilidad sobre SQL y transacciones, mientras
que el ORM introduce el patrón habitual de mapeo y sesiones en aplicaciones
Python. El desarrollador elige SQLAlchemy ORM para aprender este patrón; Psycopg
será el driver y Alembic gestionará las migraciones.

La integración inicial será síncrona. Cada petición que acceda a datos recibirá
su propia `Session`; las escrituras harán `commit` explícito y los errores
provocarán `rollback`. No se compartirá una sesión entre peticiones.

Trade-offs

El ORM añade conceptos y puede ocultar el SQL emitido si no se inspecciona.
La ejecución síncrona bloquea el thread que atiende esa operación mientras
espera a PostgreSQL, pero mantiene separado el aprendizaje de persistencia del
modelo async. Este se trabajará cuando exista una necesidad concreta en M13.
No se introduce todavía un Repository Pattern: los handlers usan la sesión
directamente mientras no exista lógica de aplicación que justifique otra capa.

D009 — Fallar al arrancar si PostgreSQL no está disponible

Status

Accepted para M2.

Problem and decision

`GET /health` comprueba que el proceso responde, pero no tenemos todavía
readiness para expresar una dependencia de datos inaccesible. Si la API
arrancase con PostgreSQL caído, parecería sana mientras sus endpoints
principales fallan. El desarrollador considera razonable arrancar en modo
degradado cuando exista readiness; para M2 acuerda fallar temprano.

Durante startup se ejecuta `SELECT 1` sobre una conexión real. Si falla,
Uvicorn no acepta tráfico y el Engine se cierra. Las migraciones siguen siendo
una operación explícita separada del arranque.

Trade-offs

Una caída temporal de PostgreSQL durante startup impide levantar la API.
Más adelante, M14 puede introducir readiness, recuperación y una política
de disponibilidad parcial. Esta decisión no obliga a tratar igual una caída
que ocurra después del arranque.

Future decisions

Todavía NO se han tomado decisiones sobre:

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
