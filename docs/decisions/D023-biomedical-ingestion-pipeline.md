# D023 — Pipeline local y resultados de ingestión (#31)

## Estado

Aceptada: decisiones cerradas por el desarrollador en el encargo de #31.

## Contexto

D021 define fuente y contrato; D022 protege identidad y upsert atómico. Falta
componer adquisición y persistencia con un resultado interpretable cuando solo
parte de las publicaciones puede procesarse.

## Decisión

Una CLI fina sobre un servicio reutilizable admite PMIDs explícitos o query con
límite obligatorio (1–100), de forma excluyente. El servicio deduplica PMIDs y
coordina lotes EFetch de hasta 200. La transacción es por documento; no se abre
antes de adquirir el lote. Un registro inválido no bloquea registros válidos;
un fallo externo de lote marca sus PMIDs como fallidos y continúa otros lotes.
Un fallo SQL o del commit revierte solo ese documento.

Cada escritura genera un UUID candidato y lo pasa al upsert. Si el UUID devuelto
coincide, es `created`; si devuelve el UUID preservado de la fila existente, es
`updated`. Se cuenta éxito después del commit. No hay SELECT previo, ni cambio
al conflicto atómico o al UUID estable de D022. Se asume la unicidad práctica de
UUID4; reutilizar candidatos no pertenece a este protocolo.

`omitted` cuenta ocurrencias duplicadas dentro de la ejecución, no publicaciones
existentes. `failed` incluye registros inválidos, PMIDs ausentes, fallos externos
y errores de persistencia. Registros no identificables se cuentan aparte de los
PMIDs ausentes: no es seguro atribuirlos. Un fallo ESearch se cuenta como una
operación fallida sin PMID; no se inventa un número de documentos desconocidos.
El resumen expone cantidades y causas seguras, con exit code 0 sin fallos y 1
con fallos; argumentos inválidos producen 2.

Se reutiliza logging JSON de M5 para inicio/fin, duración, fuente, correlación
por ejecución y cantidades. No se registran contenidos, queries, credenciales
ni excepciones crudas. No se añaden métricas ni tracing.

## Alternativas y trade-offs

- Transacción global: facilita rollback total, pero pierde trabajo válido ante
  un documento fallido. Por documento implica más commits y permite partial success.
- Endpoint HTTP: no hay consumidor que lo requiera; CLI y servicio bastan.
- SELECT antes de escribir: añade una carrera y una sentencia. Comparar UUIDs
  aprovecha la identidad estable y RETURNING del upsert existente.
- Omitir filas existentes: impide actualizar metadata. Una escritura existente
  se clasifica siempre como actualización, aunque el contenido no cambie.
- Atribuir un registro sin PMID a una entrada ausente: daría un recuento más
  simple pero inventaría una correspondencia. Se exponen ambos hechos.

## Consecuencias

Reejecutar PMIDs es seguro y actualiza metadata; los resultados de una query y
la metadata externa pueden cambiar, por lo que no son snapshots. Los commits
correctos permanecen aunque otros fallen. No hay retries automáticos, histórico,
raw XML ni recuperación distribuida. El usuario puede revisar las causas y
repetir la entrada. El alcance se mantiene en M6, sin conectar publicaciones
con retrieval o generación. Tests usan transporte simulado y PostgreSQL local;
una demo real requiere autorización explícita.
