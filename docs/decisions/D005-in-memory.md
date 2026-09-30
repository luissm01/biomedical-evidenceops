# D005 — Registro temporal de preguntas en memoria

Estado: sustituida por [D007](D007-postgresql.md) y [D008](D008-persistence.md).

En M1 se eligió un diccionario por proceso para registrar/consultar preguntas y
aprender el contrato HTTP sin introducir aún una DB. Se aceptó perder datos al
reiniciar, no compartirlos entre workers y no limitar registros en desarrollo.
Persistencia era útil más adelante, no necesaria para ese incremento.

Se mantuvo el contrato al migrar a PostgreSQL; no se introdujo Repository por
anticipación. El contrato actual está en schemas, rutas y tests de preguntas.
