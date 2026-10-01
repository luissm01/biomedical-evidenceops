# D022 — Persistencia atómica de publicaciones biomédicas (#30)

## Estado

Aceptada.

## Contexto

[D021](D021-biomedical-ingestion-source-and-contract.md) fija el contrato
normalizado, la identidad `(source, source_id)` y la actualización al reingerir.
#30 debe concretar el esquema y hacer segura esa actualización frente a
inserciones concurrentes, sin introducir aún el pipeline de #31.

## Decisión

Cada fila tendrá un UUID interno como primary key y una restricción única sobre
`(source, source_id)`. El UUID permanece estable tras la reingestión; el DOI es
metadata. Se guardan todos los campos actuales de `BiomedicalDocument`, con
`authors` como JSONB. `first_ingested_at` y `last_ingested_at` son `TIMESTAMPTZ`:
ambos se establecen al crear; solo `last_ingested_at` cambia al reingerir. No
representan la fecha de publicación.

La escritura usa `INSERT ... ON CONFLICT (source, source_id) DO UPDATE` mediante
SQLAlchemy para actualizar metadata y `last_ingested_at` en una sentencia de
PostgreSQL. La función recibe una `Session` y no hace commit: el llamador posee
la transacción y puede revertir el conjunto ante un fallo. El reloj de
PostgreSQL establece el instante inicial y el de cada actualización.

## Alternativas y trade-offs

- Una primary key compuesta evitaría un UUID, pero acoplaría referencias
  internas futuras a identificadores externos; se mantiene la identidad externa
  protegida por `UNIQUE`.
- `SELECT` seguido de `INSERT/UPDATE` permitiría decidir la acción en Python,
  pero exigiría resolver la carrera entre lectores concurrentes. El upsert
  atómico delega ese conflicto a PostgreSQL.
- Una tabla de autores permitiría consultas por autor más elaboradas; JSONB
  conserva el orden y la lista del contrato sin una relación aún innecesaria.

## Consecuencias

Repetir una ingestión mantiene una sola fila por identidad externa, con UUID y
primer instante estables. Una reingestión correcta renueva metadata y último
instante aunque el contenido no cambie. La escritura depende de PostgreSQL;
no añade versiones, histórico ni deduplicación entre fuentes. La clasificación
`created`/`updated` y la coordinación de fallos parciales quedan para #31.
