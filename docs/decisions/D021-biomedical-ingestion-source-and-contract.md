# D021 — Fuente y contrato de ingestión biomédica (#28)

## Estado

Accepted.

## Contexto

EvidenceOps aún no consulta fuentes externas ni persiste publicaciones. M6
necesita adquirir literatura biomédica pública, convertirla a un modelo interno
coherente y reingerirla con seguridad antes de abordar retrieval o RAG. La
primera integración debe poder ejecutarse localmente y sin costes obligatorios.

## Decisión

**Fuente y contenido.** La fuente inicial es PubMed mediante NCBI E-utilities.
PMID aporta un identificador estable; ESearch permite obtener PMIDs desde una
query y EFetch adquirir registros, también por PMIDs explícitos y en lotes. La
primitiva canónica de adquisición son los PMIDs explícitos; la búsqueda externa
solo los obtiene y no constituye retrieval propio de EvidenceOps. Las búsquedas
de desarrollo tendrán un límite pequeño y explícito. Se ingieren metadata
bibliográfica y abstract cuando exista; quedan fuera full text, PDFs, figuras,
tablas y contenido completo. Solo se usa información pública respetando las
condiciones de acceso y uso del proveedor y del contenido.

**Contrato interno.** `BiomedicalDocument` es una representación normalizada
propia, separada del XML de PubMed. Contiene `source`, `source_id`, título,
abstract opcional, autores como `list[str]` en orden razonable, revista y DOI
opcionales, año de publicación cuando se conozca y URL de origen o procedencia
equivalente si aporta valor. El año no implica mes ni día: no se inventará
precisión ausente. Los nombres y tipos concretos pueden adaptarse a las
convenciones del código sin alterar esta semántica. No se modela toda la riqueza
de PubMed: MeSH, grants, afiliaciones complejas, ORCID, chemicals y tipos de
publicación completos requieren una necesidad real.

**Identidad y persistencia.** La identidad de ingestión es
`(source, source_id)`; para PubMed, `source = "pubmed"` y
`source_id = PMID`. DOI es metadata, no clave primaria. La persistencia de
#30 protegerá la identidad con una restricción equivalente a
`UNIQUE(source, source_id)`. Un documento nuevo se inserta y uno existente se
actualiza mediante un upsert conceptual. Repetir una ingestión no crea
duplicados. No habrá histórico de versiones ni deduplicación heurística o
entre fuentes.

**Formato externo y ejecución.** El XML completo no se guarda en PostgreSQL.
El recorrido será formato externo → parser → modelo normalizado; pequeñas
fixtures XML servirán para tests. La interfaz inicial será una CLI fina sobre
un servicio de ingestión reutilizable, sin endpoint HTTP `/ingest`.

**Fallos.** El cliente tendrá timeout configurado, batching, respeto de los
límites de NCBI y API key opcional, sin exigirla para desarrollo pequeño. No
habrá retries automáticos propios al inicio: los fallos permanecen visibles y
una ejecución posterior es segura por idempotencia. Ante varios documentos,
los válidos pueden continuar aunque falle uno; un batch externo completo
puede fallar como unidad. El resultado final distinguirá `created`,
`updated` y `failed`. #29–#31 concretarán el manejo técnico sin introducir
workers, queues ni procesamiento distribuido.

## Alternativas consideradas

- **Europe PMC:** ofrece otras posibilidades de acceso, incluido texto completo
  disponible; queda como opción futura si surge esa necesidad. PubMed cubre el
  alcance actual con fuente oficial, PMIDs estables y un flujo útil para aprender
  APIs, XML, batching y fallos externos.
- **Copiar el modelo externo:** acoplaría dominio y almacenamiento al XML de
  PubMed. Un contrato propio conserva solo lo necesario.
- **Guardar raw XML:** facilitaría reprocesar sin refetch, pero añade
  almacenamiento y una capa raw innecesaria en M6. Se conservan fixtures de test.
- **DOI como identidad:** puede faltar; PMID identifica el registro de origen.
  Tampoco se deduplican publicaciones entre fuentes por semejanza.
- **Skip o versionado en reingestión:** skip dejaría metadata desactualizada;
  versionado añade complejidad sin necesidad actual. Se elige update.
- **Endpoint HTTP:** no hay consumidor que lo justifique. La CLI mantiene una
  entrada local explícita sobre lógica reutilizable.
- **Retries automáticos:** ocultan fallos y complican el comportamiento inicial.
  Se prefiere reejecución idempotente tras revisar el resultado.

## Consecuencias

El diseño es simple, gratuito en local, desacoplado del proveedor y permite
aprender mecanismos transferibles de ingestión. La identidad estable y el
upsert hacen segura la reejecución y dejan documentos normalizados para M7.
No habrá full text, deduplicación entre fuentes ni histórico de versiones.
Cambios en el parser pueden exigir volver a consultar PubMed al no conservar
raw XML; tampoco habrá retries automáticos propios.
