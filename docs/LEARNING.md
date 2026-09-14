EvidenceOps — Learning Log

Este documento contiene únicamente conceptos que se han trabajado realmente durante el desarrollo.

No es una lista de tecnologías utilizadas.

Un concepto debe añadirse aquí cuando el desarrollador haya tenido contacto suficiente con él como para poder explicar, al menos de forma básica:

qué es;
qué problema resuelve;
cómo lo utilizamos en EvidenceOps.
Milestone 0
uv

uv es la herramienta utilizada para gestionar el proyecto Python.

Actualmente se ha trabajado su papel en:

creación del proyecto;
gestión de dependencias;
creación/uso del entorno virtual;
ejecución de comandos dentro del entorno;
generación de uv.lock.

Concepto importante:

uv no sustituye a Python.

Gestiona el entorno y las dependencias alrededor del proyecto Python.

pyproject.toml

Es el archivo principal de configuración del proyecto Python.

Actualmente se utiliza para definir, entre otras cosas:

metadata del proyecto;
versión de Python;
dependencias de ejecución;
dependencias de desarrollo.
uv.lock

Representa las versiones concretas resueltas de las dependencias.

Diferencia conceptual:

pyproject.toml

expresa qué dependencias queremos.

uv.lock

registra la resolución exacta de dependencias utilizada.

Runtime vs development dependencies

Se ha trabajado la diferencia entre:

Runtime dependencies

Necesarias para ejecutar la aplicación.

Actualmente:

FastAPI;
Uvicorn.
Development dependencies

Necesarias para desarrollar, probar o analizar el proyecto, pero no necesariamente para ejecutarlo en producción.

Actualmente:

pytest;
httpx2.
FastAPI vs Uvicorn
FastAPI

Define la aplicación web:

rutas;
lógica;
request handling;
response handling.
Uvicorn

Es el servidor ASGI encargado de ejecutar la aplicación y aceptar conexiones HTTP.

Conceptualmente:

Cliente HTTP
     ↓
   Uvicorn
     ↓
   FastAPI
     ↓
   Endpoint
HTTP GET

GET es un método HTTP utilizado normalmente para recuperar información sin modificar el recurso consultado.

El primer endpoint del proyecto utiliza:

GET /health
Endpoint

Un endpoint combina principalmente:

un método HTTP;
una ruta;
un handler.

Ejemplo:

GET + /health + health()
Decorators

Se ha introducido el concepto de decorador mediante FastAPI.

Ejemplo conceptual:

@app.get("/health")
def health():
    ...

El decorador registra la función como handler de una determinada ruta HTTP.

No es simplemente una llamada ordinaria a una función.

Type annotations

Se ha trabajado la diferencia entre:

indicar qué tipo esperamos;
crear realmente un valor.

Una anotación de tipos describe una expectativa o contrato para herramientas, desarrolladores y librerías.

No crea por sí misma una instancia del tipo.

HTTP status code

Se ha trabajado:

200 OK

como respuesta que indica que una petición HTTP se ha procesado correctamente.

JSON response

FastAPI puede transformar estructuras Python compatibles en una respuesta JSON.

Ejemplo actual:

{"status": "ok"}

se serializa como:

{
  "status": "ok"
}
assert

En los tests utilizamos assert para expresar una condición que esperamos que sea cierta.

Ejemplo conceptual:

assert actual == expected

Si la condición no se cumple, el test falla.

Tests as contracts

El test de /health expresa parte del contrato observable de la API:

debe responder con un determinado status code;
debe responder con un determinado cuerpo.

Esto significa que una modificación accidental de ese comportamiento debería ser detectada por el test.

Function test vs application test vs real server

Se ha trabajado la diferencia entre:

Probar una función directamente

Ejecutar Python sin pasar por la capa HTTP.

Probar la aplicación con TestClient

Ejercitar el comportamiento HTTP de FastAPI sin levantar manualmente un servidor externo.

Consultar un servidor real

Levantar Uvicorn y realizar una petición real, por ejemplo mediante curl.

Cada nivel prueba cosas diferentes.

Test failure vs warning
Test failure

Una expectativa del test no se cumple.

Implica que el comportamiento probado no coincide con el esperado.

Warning

Indica un posible problema, deprecación o cambio futuro.

Un warning no significa necesariamente que la prueba haya fallado.

Regression experiment

Se ha cambiado deliberadamente la respuesta de /health a {"status": "error"},
manteniendo el test que espera {"status": "ok"}.
El desarrollador ha ejecutado pytest y observado el AssertionError en la
comparación del cuerpo, mientras la comprobación del estado 200 pasa.

Esto verifica que el test detecta ese cambio concreto del contrato.
El desarrollador ha restaurado el endpoint y confirmado que la prueba vuelve a
pasar. Se completa así el ciclo: comportamiento correcto, fallo deliberado y
restauración del comportamiento correcto.

Fase 1 — Primer modelo de respuesta

El desarrollador ha razonado que `dict[str, str]` permite distintas claves y
valores siempre que sean cadenas, y ha implementado `HealthCheckResponse`
heredando de `BaseModel`, con el campo `status: Literal["ok"]`.

Ha conectado el modelo a `/health` mediante `response_model` y la anotación
de retorno, y devuelve una instancia creada con `HealthCheckResponse(status="ok")`.
Primera práctica de campos declarados, restricción a un valor concreto y
construcción de una instancia como respuesta del endpoint.

Fase 1 — Modelos de entrada, validación y endpoints

Tras solicitar una explicación más detallada, el desarrollador ha confirmado
comprender el recorrido del código. Se han trabajado:

- Clases Pydantic como tipos propios de datos, herencia de `BaseModel` e instancias.
- Campos obligatorios, `Field`, límites de longitud y `ConfigDict` para recortar
  espacios exteriores y rechazar campos extra.
- Separación entre `QuestionCreate` (texto del cliente) y `QuestionResponse`
  (identificador generado por el servidor y texto).
- Validación de entrada de FastAPI anterior al handler: `422` automático y
  localización del error en `detail`. Se ha localizado el handler de la librería.
- Diferencia entre entrada inválida (`422`) y recurso no encontrado (`404`).
- Registro de rutas, parámetros del cuerpo y de la URL, creación de UUID,
  almacenamiento y consulta en un diccionario, `raise HTTPException`, cabecera
  `Location` y serialización de la respuesta.

Se ha aclarado que un error al construir una salida en nuestro código es un
error del servidor, distinto de una petición inválida del cliente. No se ha
profundizado todavía en validadores personalizados ni en gestión de excepciones.

Fase 1 — Almacenamiento temporal y persistencia

El desarrollador ha considerado suficiente perder las preguntas al reiniciar
esta primera versión, y ha identificado la necesidad de conservarlas en un
producto más completo. Se acuerda comenzar con memoria y abordar persistencia
cuando el proyecto la necesite. No se han trabajado todavía bases de datos ni
transacciones en EvidenceOps.

Fase 1 — Recorrido de ejecución y pruebas

Se ha revisado con el desarrollador la relación entre uv y el entorno, Uvicorn
y FastAPI, los modelos Pydantic, el diccionario en memoria y pytest. Tras pedir
una explicación estructural adicional, ha aceptado continuar hacia CI.
Se ha explicado el arranque por importación, el registro de rutas y el recorrido
de una petición: validación, handler, almacenamiento y respuesta. También el
recorrido de pruebas con TestClient, sin Uvicorn, y el papel de CI al automatizarlas.

Las fixtures, `monkeypatch`, `yield` y la parametrización se han explicado sobre
los tests existentes. Su comprensión práctica aún no se ha confirmado; no se
consideran dominados por haber leído la explicación. El agente ha verificado
la primera ejecución remota de GitHub Actions; queda pendiente que el desarrollador
revise el workflow y sus resultados. También se ha introducido el flujo milestone,
issue, rama y PR; su creación automática no implica dominio práctico.

Concepts pending

Todavía no deben considerarse aprendidos:

Pydantic: validadores personalizados y validación en mayor profundidad;
dependency injection;
async Python;
unit vs integration testing en profundidad;
mocking;
configuration management;
environment variables;
logging;
Dockerización del proyecto;
CI/CD.

Se introducirán cuando el proyecto los necesite.
