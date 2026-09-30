# EvidenceOps

Proyecto de AI Engineering aplicado a evidencia biomédica pública.
[Visión](docs/PROJECT_CONTEXT.md) · [Estado y próximo paso](docs/CURRENT_STATE.md) ·
[Mapa documental](docs/README.md) · [Instrucciones para agentes](AGENTS.md).

## Requisitos e instalación

- Python compatible con [pyproject.toml](pyproject.toml); versión local en [.python-version](.python-version).
- uv instalado.
- Docker con Docker Compose para ejecutar PostgreSQL localmente.

Desde la raíz del proyecto:

```bash
uv sync --locked --dev
```

Este comando prepara `.venv/` con las dependencias de ejecución y desarrollo
registradas en `uv.lock`. No es necesario activar el entorno para usar `uv run`.

Si aún no tienes `.env`, créalo a partir del ejemplo (no sobrescribas uno existente):

```bash
cp .env.example .env
```

Configura personalmente `EVIDENCEOPS_GEMINI_API_KEY` antes de arrancar la API.
Los nombres y valores iniciales están en [.env.example](.env.example); las
variables de entorno prevalecen sobre `.env`. Después:

```bash
docker compose up -d --wait postgres
uv run alembic upgrade head
```

El contenedor crea dos bases: `evidenceops` para desarrollo y
`evidenceops_test` para las pruebas. Las credenciales del ejemplo son únicamente
locales. Los archivos `.env` reales no se versionan.

## Ejecutar la API

```bash
uv run uvicorn evidenceops.main:app --reload
```

La API escucha en `http://127.0.0.1:8000`. `--reload` permite recargar los cambios
durante el desarrollo. Detén el servidor con `Ctrl+C`.

Desde otra terminal:

```bash
curl -i http://127.0.0.1:8000/health
```

Respuesta esperada: `200 OK`, contenido JSON y cuerpo `{"status":"ok"}`.
Este endpoint comprueba que la aplicación responde; no verifica servicios externos.

## Registrar y consultar preguntas

```bash
curl -i http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"text": "¿Qué evidencia existe sobre la intervención X?"}'
```

Devuelve `201 Created`, un JSON con `id` (UUID generado por el servidor) y `text`,
y una cabecera `Location` con la ruta de consulta. Copia el identificador recibido:

```bash
curl -i http://127.0.0.1:8000/questions/ID_DEVUELTO
```

- `200 OK`: devuelve la pregunta registrada.
- `404 Not Found`: el UUID es válido, pero no existe una pregunta con ese ID.
- `422 Unprocessable Entity`: el cuerpo o el identificador no cumplen el contrato.

`text` debe ser una cadena de entre 1 y 2.000 caracteres después de quitar los
espacios de los extremos. Se rechazan campos adicionales, incluido un `id`
enviado por el cliente. Cada POST válido crea un registro nuevo, aunque repita
el texto. El endpoint registra preguntas; todavía no busca evidencia ni genera
respuestas. El contrato interactivo está disponible en `http://127.0.0.1:8000/docs`.

Las preguntas se almacenan en PostgreSQL y sobreviven al reinicio de la
aplicación. Alembic mantiene el esquema de la base de datos; una aplicación nueva
debe ejecutar `uv run alembic upgrade head` antes de atender peticiones.

## Generar una respuesta

Con el UUID de una pregunta registrada, sin body:

```http
POST /questions/{question_id}/generate
```

Devuelve `200 OK`:

```json
{
  "answer": "Generated biomedical answer.",
  "limitations": ["Relevant limitation."],
  "external_sources_consulted": false
}
```

Una pregunta inexistente devuelve `404`; un UUID inválido, `422`. Ninguno
invoca al generador. La respuesta no se persiste y repetir la operación puede
producir otra respuesta. No se han consultado fuentes biomédicas externas.


## Operar Gemini

La API requiere clave configurada salvo que se inyecte un generador, como hacen
los tests. No hay inferencia al importar ni al arrancar; startup comprueba
PostgreSQL, pero no la validez remota de la clave. No publiques `.env` ni claves.

Para una inferencia manual explícita que consume cuota:

```bash
uv run --locked python test_gemini.py
```

Ese script usa `Settings`: exige la URL de PostgreSQL aunque no conecte a la DB.
El runner de [evaluation](evaluation/README.md) usa `GenerationSettings` y no la exige.
La respuesta tiene validación estructural, no garantía de veracidad biomédica.

Errores HTTP: timeout → 504; cuota → 429; autenticación/indisponibilidad del
proveedor → 503; salida inválida u otro fallo de generación → 502. Los mensajes
públicos son fijos y seguros; contrato exacto en OpenAPI y tests de generación.
Política de retries y ausencia de deadline total en [D011](docs/decisions/D011-gemini.md).
Flujo y recursos en [arquitectura](docs/ARCHITECTURE.md).

## Diagnóstico y evaluación

- [Observabilidad](docs/subsystems/observability.md): eventos JSON, X-Request-ID,
  diagnóstico y límites; estado de entrega en el plan M5.
- [Evaluación](evaluation/README.md): dataset, runs, promoción, revisión humana
  y comparación. Un baseline de outputs no certifica calidad biomédica.

## Pruebas y CI

La suite completa usa PostgreSQL local; las fixtures exigen `evidenceops_test`,
aplican migraciones y limpian preguntas antes/después de cada test de datos.
Configura `EVIDENCEOPS_TEST_DATABASE_URL` según el ejemplo.

```bash
docker compose up -d --wait postgres
uv run --locked pytest
```

Las pruebas usan fakes y transporte simulado: no requieren API key ni hacen
inferencias reales. Para trabajar solo en evaluación, sin PostgreSQL:

```bash
uv run --locked pytest tests/test_evaluation.py tests/test_evaluation_dataset.py tests/test_evaluation_review.py
```

[CI](.github/workflows/ci.yml) define comandos y servicios exactos para pushes/PRs;
no despliega. `--locked` exige coherencia del lock sin modificarlo. Distingue errores
de preparación del entorno, assertions fallidas y warnings. Limitaciones vigentes
en [estado](docs/CURRENT_STATE.md); no se mantiene aquí un contador de tests.

## Navegación del código

[src/evidenceops](src/evidenceops): aplicación; [tests](tests): comportamiento
verificado; [migrations](migrations): esquema; [compose.yaml](compose.yaml):
servicios locales; [evaluation](evaluation): dataset y runbook.
El mapa de responsabilidades está en [arquitectura](docs/ARCHITECTURE.md),
los motivos en [ADRs](docs/decisions/README.md) y la dirección en el
[roadmap](docs/ROADMAP.md).
