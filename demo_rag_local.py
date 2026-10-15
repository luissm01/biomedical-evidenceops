"""Demo manual local; no se ejecuta al importar ni modifica el corpus.

Desde la raíz:
uv run --locked --extra medcpt python demo_rag_local.py
"""

import argparse
from contextlib import ExitStack, closing
from dataclasses import asdict
import json
import logging

from evidenceops.config import Settings
from evidenceops.database import create_database
from evidenceops.embeddings import LocalMedCPT
from evidenceops.generation import GenerationError, GenerationErrorCause
from evidenceops.generator_factory import create_generator
from evidenceops.rag import EVIDENCE_CHARACTER_LIMIT, RagService, build_context
from evidenceops.retrieval import search

DEFAULT_QUERY = "association between childhood obesity and asthma risk"


def show(label, value):
    print(f"\n{label}", flush=True)
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--published-from", type=int)
    args = parser.parse_args()
    if not args.query.strip():
        parser.error("La pregunta debe contener texto")
    if args.published_from is not None and args.published_from <= 0:
        parser.error("published-from debe ser un año positivo")

    # Solo mostramos evidencia pública y salidas explícitas; nunca settings,
    # cabeceras, URLs de conexión ni detalles libres de excepciones del SDK/DB.
    logging.disable(logging.CRITICAL)
    show("1. Pregunta original", args.query)
    calls = 0
    received_content = False
    context = None
    try:
        settings = Settings()
        with ExitStack() as resources:
            engine, sessions = create_database(settings)
            resources.callback(engine.dispose)
            encoder = LocalMedCPT()
            generator = resources.enter_context(closing(create_generator(settings)))
            if settings.llm_provider == "gemini":
                from google import genai
                from google.genai import types

                # Adaptación SOLO de esta demo: el adapter no expone retries.
                # En google-genai 2.23.0, Interactions interpreta attempts=0
                # como cero retries. Sustituimos el cliente real, sin mocks ni
                # cambios a la factory o a la política permanente del adapter.
                generator._client.close()
                generator._client = genai.Client(
                    api_key=settings.gemini_api_key.get_secret_value(),
                    http_options=types.HttpOptions(
                        retry_options=types.HttpRetryOptions(attempts=0),
                    ),
                )
            # DeepSeek usa httpx sin retries en el adapter existente.
            show("Proveedor configurado (máximo una llamada, cero retries)", {
                "provider": settings.llm_provider,
                "model": settings.selected_model,
                "published_from": args.published_from,
            })

            def retrieve(**kwargs):
                nonlocal context
                results = search(sessions, encoder, **kwargs)
                show("2. Artículos recuperados (orden M7; score = dot product)", [
                    {"pmid": r.unit.source_id if r.unit.source == "pubmed" else None,
                     "title": r.unit.title, "score": r.score}
                    for r in results
                ])
                context = build_context(results)
                show("3. Fuentes incluidas en el contexto", [
                    {"citation": f"[{s.citation_id}]", "pmid": s.unit.source_id,
                     "title": s.unit.title, "score": s.score}
                    for s in context.sources
                ])
                show("Presupuesto y omisiones (sin truncar abstracts)", {
                    "evidence_characters": len(context.evidence_json),
                    "limit": EVIDENCE_CHARACTER_LIMIT,
                    "omitted_pmids": [r.unit.source_id for r in context.omitted],
                })
                return results

            class DisplayGenerator:
                """Delegación transparente al generador real, sin inferencia adicional."""

                def generate(self, question_text, *, system_instruction=None):
                    nonlocal calls, received_content
                    if calls:
                        raise RuntimeError("La demo permite una sola llamada")
                    # Garantiza que lo mostrado corresponde al mensaje real del servicio.
                    if context is None or question_text != context.message(args.query.strip()):
                        raise RuntimeError("El mensaje no coincide con el contexto mostrado")
                    print("\n4. Instrucciones enviadas al LLM", flush=True)
                    print(system_instruction, flush=True)
                    print("\nContexto: mensaje JSON exacto enviado al LLM", flush=True)
                    print(question_text, flush=True)
                    calls += 1
                    content = generator.generate(
                        question_text, system_instruction=system_instruction,
                    )
                    received_content = True
                    show("5. Salida estructurada del LLM (antes de validar citas)",
                         content.model_dump())
                    return content

            response = RagService(retrieve, DisplayGenerator()).generate(
                args.query, published_from=args.published_from,
            )
            if not calls:
                print("\n4–5. Sin evidencia utilizable: no se llamó al LLM.", flush=True)
            show("6. Respuesta final, limitaciones y fuentes reales devueltas",
                 asdict(response))
            print("\n7. Validación: " + (
                "APROBADA por RagService (citas/abstención)."
                if calls else "No aplica al LLM: abstención local construida por la aplicación."
            ), flush=True)
            print("La validación estructural no demuestra apoyo semántico.", flush=True)
    except GenerationError as exc:
        if exc.cause is GenerationErrorCause.INVALID_OUTPUT and received_content:
            print("\n6. RagService rechazó la salida: no devuelve una respuesta válida.", flush=True)
            print("\n7. Validación de citas/abstención: RECHAZADA (INVALID_OUTPUT).", flush=True)
        else:
            print(f"\nGeneración fallida: {exc.cause.value}. No se repite la llamada.", flush=True)
        return 1
    except Exception as exc:
        print(f"\nDemo interrumpida ({type(exc).__name__}). "
              "Revisa configuración, PostgreSQL y disponibilidad de MedCPT; "
              "se omiten detalles para no exponer credenciales.", flush=True)
        return 1
    finally:
        print(f"\nInvocaciones reales al generador intentadas: {calls}. Sin retries.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
