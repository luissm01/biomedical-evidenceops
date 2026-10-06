# D024 — Unidad de retrieval, MedCPT y almacenamiento vectorial (#37)

## Estado

Aceptada por las decisiones explícitas del desarrollador en el encargo de cierre
documental de #37. Representación de #38 implementada; embeddings, almacenamiento
y retrieval siguen siendo diseño.

## Contexto

M6 persiste publicaciones de PubMed con título, abstract opcional y metadata
bibliográfica. [D021](D021-biomedical-ingestion-source-and-contract.md) limita
el contenido a esos registros; [D022](D022-biomedical-publication-persistence.md)
conserva la identidad al reingerir. M7 necesita una primera referencia medible
de retrieval antes de conectar evidencia con generación en M8.

## Decisión

**Unidad y texto.** Una publicación constituye una unidad recuperable: su título
y abstract, sin fragmentación interna ni overlap en el baseline inicial. No es
texto completo del artículo. La unidad conserva identidad estable vinculada al
UUID de publicación y a `(source, source_id)` —PMID para PubMed—, título, texto
representado y metadata/procedencia. Su posición es única dentro de la publicación;
no se necesita una jerarquía de chunks. En #38, `whole-publication-v1` une solo
campos con contenido: `title + "\n\n" + abstract` cuando existen ambos, solo
título o solo abstract cuando falta el otro. Un campo vacío o con solo whitespace
cuenta como ausente, al igual que un abstract `None`. No añade separadores por
campos ausentes; si ambos campos carecen de contenido devuelve `None`.
Los campos con contenido se conservan exactamente, sin normalización Unicode ni
recorte de espacios. No hay tamaño mínimo, límite, truncamiento, overlap ni
tokenización en esta transformación. No se resume ni reescribe el contenido.
El chunking interno podrá compararse con este baseline
si una necesidad o mejora medida lo justifica.

**Identidad y fingerprint de #38.** La identidad lógica `unit_id` es SHA-256
hexadecimal del JSON UTF-8 compacto `[source, source_id, strategy, chunk_index]`,
con `ensure_ascii=False`, separadores `(',', ':')` e índice cero. La serialización
evita ambigüedades entre campos; no usa `hash()` de Python ni UUID aleatorio.
Exige fuente e ID externo con contenido (`ValueError` si están en blanco).
El UUID de publicación se conserva como vínculo de procedencia, pero no forma
parte de la identidad: reconstruir el corpus no la cambia. Cambiar título o
abstract conserva identidad; cambiar fuente, ID externo o versión de estrategia
la cambia. Toda modificación de las reglas de representación exige incrementar
la versión de estrategia en código; no se ofrece un selector arbitrario de versiones.

`content_fingerprint` es SHA-256 hexadecimal del texto representado exacto en
UTF-8, sin metadata, UUID ni estrategia. Un cambio de metadata no obliga por sí
solo a recalcular contenido; cambiar estrategia puede mantener ese fingerprint
si el texto sigue idéntico, pero produce otra identidad. #39 deberá considerar
también estrategia y configuración/entrada efectiva del encoder, no solo este hash.
El contrato inmutable conserva título y abstract separados, autores como tupla,
revista, DOI, año y URL de origen. Implementación y contrato en
[chunking.py](../../src/evidenceops/chunking.py).

**Embeddings.** Se elige MedCPT local como única opción inicial:
`ncbi/MedCPT-Query-Encoder` para consultas y `ncbi/MedCPT-Article-Encoder` para
publicaciones. Son dos encoders especializados y compatibles en un mismo espacio
de 768 dimensiones; no se exige usar el mismo encoder para ambos textos. Su
especialización en consultas y artículos biomédicos/PubMed motiva la elección,
sin demostrar todavía calidad sobre nuestro corpus. Véanse las fichas oficiales
del [Query Encoder](https://huggingface.co/ncbi/MedCPT-Query-Encoder) y
[Article Encoder](https://huggingface.co/ncbi/MedCPT-Article-Encoder).

La ejecución local evita coste por petición, API obligatoria y envío de abstracts
a terceros, pero requiere descargar los modelos y disponer de recursos locales.
Reproducibilidad exigirá identificar revisiones de ambos encoders, tokenizadores
y configuración efectiva, no solo el nombre MedCPT. No se añade soporte multimodelo.
`title + abstract` expresa el contenido conceptual; no prescribe concatenación
ingenua: la ficha oficial presenta título y abstract como un par de textos.
La unidad íntegra tampoco garantiza que todo su texto quepa en el encoder: sus
límites de tokens y el tratamiento de entradas largas deberán quedar explícitos
al implementar, sin introducir fragmentación silenciosa.

**Ranking.** Se elige inner product / dot product sobre las representaciones
compatibles de MedCPT, siguiendo su
[ejemplo oficial de búsqueda](https://github.com/ncbi/MedCPT#searching-pubmed-with-medcpt).
Un producto mayor ordena antes el resultado. No se sustituye por cosine ni se
normalizan vectores arbitrariamente: esas operaciones pueden alterar el ranking.
El score no es probabilidad, porcentaje de relevancia, factualidad ni calidad clínica.

**Almacenamiento.** Se elige PostgreSQL + pgvector para mantener vectores,
publicaciones y metadata en el servicio ya existente. Las 768 dimensiones
condicionarán el almacenamiento futuro. No se instala la extensión, se modifica
Docker ni se crea esquema en este cierre de diseño; tampoco se exige un índice
aproximado por anticipación.

**Filtro.** El único filtro semántico inicial es temporal, con la precisión
disponible: `publication_year`. No se inventan mes/día ni se usan timestamps de
ingestión como fecha de publicación. Conceptualmente, `published_from = 2020`
restringe candidatos a años conocidos desde 2020, inclusive, antes de obtener
el top-K por similitud. Sin filtro no se impone esa restricción; con filtro un
año desconocido no acredita cumplirla. PMID/DOI quedan como identificadores,
sin añadir filtros de autor, revista o fuente. Otros filtros requerirán necesidad.

**Contrato conceptual.** Entrada: query biomédica, `top_k` y filtro temporal
opcional. Cada resultado devuelve la publicación/unidad, identificadores,
título, texto representado, metadata/procedencia y similarity score; nunca un
vector sin origen. Por ejemplo, una consulta sobre tratamiento de diabetes con
`top_k = 3` y `published_from = 2020` devolverá hasta tres publicaciones elegibles,
ordenadas por producto interno, cada una con su PMID y contenido trazable.
Sin coincidencias devolverá una colección vacía. Se validarán query con contenido
y `top_k` positivo; los empates necesitarán un desempate estable al implementar.
No se define aquí un schema definitivo ni endpoint HTTP.

**Compatibilidad y reindexación.** La futura indexación deberá identificar la
estrategia de representación, contenido efectivo y configuración de embeddings.
Repetir la misma entrada/configuración no duplicará unidades ni vectores.
Cambiar contenido, estrategia o encoders exigirá regenerar las representaciones
afectadas y evitar devolver versiones obsoletas. Compartir dimensión no basta
para compatibilidad: consulta y corpus deben corresponder al par de encoders
y configuración registrados. #38/#39 concretarán identificadores, parámetros,
límites y mecanismo de sustitución, sin un histórico complejo por anticipación.

## Alternativas y trade-offs

- Chunks por longitud y overlap pueden afinar recuperación y resolver límites,
  pero añaden fragmentación, duplicación y decisiones de tamaño. La publicación
  como unidad ofrece una referencia sencilla; puede diluir detalles relevantes
  o exceder la entrada del modelo. La evaluación permitirá decidir si dividirla.
- Un modelo generalista local sería una alternativa sencilla; una API evita
  parte de los recursos locales, a cambio de cuotas, disponibilidad y envío de
  texto. MedCPT prioriza ajuste al dominio y autonomía local, sin asegurar que
  supere esas alternativas hasta medirlo.
- Cosine compara dirección y L2 mide distancia; dot product también depende
  de magnitud. Se elige coherencia con MedCPT, no la métrica más habitual.
- Vectores en memoria/archivos simplifican una demo, pero separan persistencia
  y metadata. Una DB dedicada añade otro servicio sin necesidad medida.
  pgvector aprovecha PostgreSQL, a cambio de preparar extensión e integración
  operativa cuando se implemente #39.

## Consecuencias

La dirección acordada es `publicación → título + abstract → Article Encoder →
vector de 768 dimensiones → PostgreSQL + pgvector`; la consulta seguirá
`query → Query Encoder → candidatos filtrados por año → dot product → top-K`.
La representación de una unidad por publicación está implementada en
#38, sin segmentación interna ni integración con ingestión. El resto de esos
componentes aún no existe. #39 integrará embeddings/almacenamiento y #40 medirá retrieval.

M7 acaba en evidencia recuperada y baseline, sin alimentar Gemini/DeepSeek.
RAG corresponde a M8; BM25, hybrid search, reranking y query rewriting a M9.
No se añaden agentes, LangChain/LangGraph, DB vectorial dedicada ni infraestructura
distribuida. CI seguirá sin inferencias reales ni descargas de modelos pesados.
