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

D010 — Generación efímera vinculada a preguntas en M3

Status

Accepted para M3; contrato y cliente Gemini implementados en #9 e integración
HTTP implementada en #10.

Problem and decision

Queremos aprender a integrar un LLM con las preguntas existentes sin introducir
almacenamiento de respuestas. El desarrollador elige generar y devolver:
recuperar una pregunta persistida, llamar a Gemini, validar el resultado y
devolverlo por HTTP. La respuesta no se guarda; repetir la operación puede
producir otra respuesta.

El contrato HTTP acordado es `POST /questions/{question_id}/generate`, sin
cuerpo de petición. Una operación correcta termina con `200 OK`; un UUID
inválido devuelve `422` y una pregunta inexistente, `404`, sin llamar al LLM.
No se crea una tabla `answers` ni una cabecera `Location` para la generación.

El cuerpo correcto incluye `answer: str`, `limitations: list[str]` (que puede
ser vacía) y `external_sources_consulted: false`. Gemini genera `answer` y
`limitations`; EvidenceOps establece el indicador de fuentes externas, ya que
esta operación no consulta ninguna. Pydantic validará el contrato estructural,
sin determinar la veracidad biomédica. El desarrollador acordó exigir que
`answer` contenga texto tras quitar espacios exteriores y que cada elemento
de `limitations` contenga texto; la lista puede estar vacía. Ambos campos son
obligatorios. No se añaden límites arbitrarios de longitud o número de
limitaciones en este primer contrato.

Ejemplo de la operación acordada, con una pregunta ya registrada:

```http
POST /questions/9f4d9b6b-2c4d-4f72-9d24-263412df46aa/generate
```

```json
{
  "answer": "Respuesta generada y validada para la pregunta almacenada.",
  "limitations": ["No se han consultado fuentes biomédicas externas."],
  "external_sources_consulted": false
}
```

El ejemplo muestra el formato, no una respuesta biomédica evaluada. No se
envía cuerpo HTTP: EvidenceOps recupera el texto de la pregunta por ID.

El desarrollador redactó la primera instrucción para el modelo: responder con
claridad y prudencia usando su conocimiento, producir `answer` y limitaciones
relevantes (incluida información clínica faltante cuando proceda), evitar
referencias inventadas y no afirmar que consultó fuentes externas. La pregunta
persistida se enviará separadamente como entrada del usuario. Se pedirá una
salida estructurada con un esquema real de los dos campos generados y se
validará de nuevo en EvidenceOps. El texto exacto del prompt aún puede
ajustarse al revisar el primer resultado real.

Se acordó concretar la precaución sobre referencias: no proporcionar estudios,
citas, cifras o resultados específicos si no se tiene suficiente certeza y
expresar incertidumbre cuando corresponda. Esta instrucción no permite al
modelo verificar hechos por sí mismo.

Trade-offs

La operación es pequeña y permite concentrarse en inferencia y validación.
No permite recuperar una respuesta anterior ni comparar automáticamente
generaciones repetidas; esto se decidirá cuando exista una necesidad real.
La dependencia que recupera `question.text` abre una Session corta y la cierra
antes de llamar al generador. Así no retiene conexión ni transacción durante
la espera externa; la generación utiliza el texto recuperado en ese momento.

D011 — Gemini como único proveedor de M3

Status

Accepted; actualizada por decisión explícita del desarrollador el 2026-09-15.
Sustituye el plan anterior de Gemini seguido de Ollama dentro de M3.

Problem and decision

Usar únicamente Gemini mediante `google-genai`, con `gemini-3.6-flash`,
2.048 tokens máximos de salida y 60 segundos de timeout por petición. El modelo
es el acordado por el desarrollador para esta integración; se elimina la
referencia anterior a `gemini-3.8-flash`. El desarrollador configuró la clave
local y confirmó una primera inferencia estructurada correcta. No se publica
la clave ni se repite automáticamente la inferencia. El objetivo sigue siendo
usar la opción gratuita; no se presupone una cuota fija para cada proyecto.

Ollama queda aplazado: podrá reconsiderarse cuando tenga sentido comparar
modelos en Evaluation, sin comprometer ahora su implementación en M4.

La clave sigue siendo opcional en Settings para permitir un Generator inyectado.
Desde #10, si no se inyecta uno, la API falla al arrancar sin clave configurada:
la generación es una dependencia esencial. No se valida la credencial contra
el proveedor ni se hace inferencia al arrancar. Modelo, tokens y timeout se
validan. El script manual detecta la ausencia de clave antes de crear el cliente
y lo cierra mediante `contextlib.closing`.

No se añaden retries propios. Se revisó el SDK 2.23.0: `attempts=0` se normaliza
a 1 y la ruta Interactions lo interpreta como un reintento. Un 503 simulado
produce dos intentos; el test registra ese comportamiento sin esperas reales.
Se conserva la opción pública, sin parches privados ni cambio de API. La
corrección de esta discrepancia y el presupuesto total se abordarán en #11.
El timeout actual no es una garantía de duración total de la operación.

Trade-offs

Un proveedor permite cerrar la primera integración con una frontera sencilla.
La API remota depende de disponibilidad y cuotas externas; la primera llamada
real demuestra conectividad y formato, no calidad factual. La generación es
efímera: no se persisten respuestas en PostgreSQL y se solicita `store=False`
a Interactions. Esto no sustituye las condiciones de tratamiento de datos del
proveedor. No se incorporan LangChain ni LangGraph.

D012 — Frontera LLM con un Protocol de una operación

Status

Accepted e implementada en #9.

Problem and decision

La generación debe poder sustituirse por un fake en tests y el resto de la
aplicación no debe depender del SDK Gemini. El desarrollador eligió un
`Protocol` con `generate(question_text: str) -> GeneratedContent`.

`GeneratedContent` contiene solo `answer` y `limitations`. Gemini recibe un
JSON Schema derivado de ese modelo y el adaptador vuelve a validar su salida
con Pydantic. La estructura válida no prueba veracidad. EvidenceOps añade
`external_sources_consulted: false` en `GenerationResponse`, separado del modelo
interno: es conocimiento de la aplicación sobre su ejecución, no del LLM.

Se adopta `GenerationError` con una causa identificable, sin jerarquía adicional.
En #9, la validación fallida se traduce a `INVALID_OUTPUT` y el resto de fallos
a `UNKNOWN`, con exception chaining. Las categorías de timeout, rate limit,
autenticación e indisponibilidad están declaradas; su clasificación completa
y el mapping HTTP quedan para #11. No se exponen tipos del SDK en el contrato.

Trade-offs

La frontera añade poco código y permite tests sin proveedor real. La clase
concreta gestiona el cierre del SDK; el Protocol conserva una sola operación.
No se añaden factories, registries, managers, repositorios ni frameworks de DI.

Integración HTTP y ownership (#10)

`create_app` recibe opcionalmente un Generator. El handler lo obtiene mediante
`Depends(get_generator)` desde `app.state`, sin construir GeminiGenerator. Esto
mantiene la frontera de #9 y permite utilizar FakeGenerator sin llamadas reales.

El lifespan crea y reutiliza GeminiGenerator cuando no hay uno inyectado y lo
cierra al apagar la aplicación. Un generador externo pertenece a quien lo
entrega: la aplicación no llama a su `close()`. El Engine se libera incluso
si falla el cierre del generador. Esta regla hace explícita la responsabilidad
sobre los recursos sin ampliar el Protocol ni introducir otra capa.

Future decisions

Todavía NO se han tomado decisiones sobre:

vector store;
embeddings;
RAG architecture;
observability platform;
queue system;
agent framework;
MCP architecture;
cloud deployment;
Kubernetes.

Estas decisiones deberán tomarse cuando exista suficiente contexto para evaluar sus trade-offs.
