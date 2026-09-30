# D008 — SQLAlchemy ORM síncrono, Psycopg y Alembic

## Status

Accepted.

## Problem

Necesitamos integrar PostgreSQL con Python, definir los límites transaccionales
y evolucionar el esquema sin mezclar estas responsabilidades con los modelos
del contrato HTTP.

## Options and decision

Se consideraron SQL directo mediante Psycopg, SQLAlchemy Core y SQLAlchemy ORM.
El acceso directo ofrece máxima visibilidad sobre SQL y transacciones, mientras
que el ORM introduce el patrón habitual de mapeo y sesiones en aplicaciones
Python. El desarrollador elige SQLAlchemy ORM para aprender este patrón; Psycopg
será el driver y Alembic gestionará las migraciones.

La integración inicial será síncrona. Cada petición que acceda a datos recibirá
su propia `Session`; las escrituras harán `commit` explícito y los errores
provocarán `rollback`. No se compartirá una sesión entre peticiones.

## Trade-offs

El ORM añade conceptos y puede ocultar el SQL emitido si no se inspecciona.
La ejecución síncrona bloquea el thread que atiende esa operación mientras
espera a PostgreSQL, pero mantiene separado el aprendizaje de persistencia del
modelo async. Este se trabajará cuando exista una necesidad concreta en M13.
No se introduce todavía un Repository Pattern: los handlers usan la sesión
directamente mientras no exista lógica de aplicación que justifique otra capa.
