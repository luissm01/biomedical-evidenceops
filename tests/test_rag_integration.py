"""Use actual PostgreSQL/pgvector and M7 search with a deterministic encoder."""

import json

import pytest
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import delete

from evidenceops.database import create_database
from evidenceops.generation import GeneratedContent
from evidenceops.main import create_app
from evidenceops.models import Publication, Question
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.retrieval import index_publication
from test_retrieval import ControlledMedCPT, document, persist


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_api_database_retrieval_context_generation_and_filter(test_settings, migrated_database, mode):
    engine, sessions = create_database(test_settings)
    encoder = ControlledMedCPT()
    generator = Mock()
    generator.generate.return_value = GeneratedContent(answer="Síntesis [S1].", limitations=[])
    # Own only these test publications; preserve any other fixtures' data.
    publication_ids = []
    try:
        for number in range(6):
            doc = document(source_id=f"rag-http-{number}", year=2024)
            publication_id = persist(sessions, doc)
            publication_ids.append(publication_id)
            index_publication(sessions, publication_id, encoder)
        with sessions() as session:
            before_questions = list(session.query(Question.id))
        with TestClient(create_app(test_settings.model_copy(update={"retrieval_mode": mode}), generator=generator, encoder=encoder)) as client:
            response = client.post("/rag", json={"query": " diabetes ", "published_from": 2024})
            assert response.status_code == 200
            body = response.json()
            assert body["answer"] == "Síntesis [S1]."
            assert len(body["sources"]) == 5
            assert [s["citation_id"] for s in body["sources"]] == [f"S{i}" for i in range(1, 6)]
            assert {s["unit"]["publication_id"] for s in body["sources"]} <= {
                str(value) for value in publication_ids
            }
            if mode == "semantic":
                assert all(s["score"] == 1.0 for s in body["sources"])
            else:
                assert [s["score"] for s in body["sources"]] == [2 / (60 + i) for i in range(1, 6)]
            evidence = json.loads(generator.generate.call_args.args[0])["evidence"]
            assert [e["text"] for e in evidence] == [s["unit"]["text"] for s in body["sources"]]
            assert encoder.query_calls == ["diabetes"]
            # Filtering happens in the actual SQL retrieval before context/LLM.
            abstention = client.post("/rag", json={"query": "diabetes", "published_from": 9999})
            assert abstention.status_code == 200
            assert abstention.json()["answer"] == ABSTENTION_ANSWER
            assert abstention.json()["sources"] == []
            generator.generate.assert_called_once()
            metrics = client.get("/metrics").text
            assert 'evidenceops_rag_operations_total{outcome="success",stage="operation"} 1.0' in metrics
            assert 'evidenceops_rag_operations_total{outcome="abstention",stage="operation"} 1.0' in metrics
        with sessions() as session:
            assert list(session.query(Question.id)) == before_questions
    finally:
        with sessions.begin() as session:
            session.execute(delete(Publication).where(Publication.id.in_(publication_ids)))
        engine.dispose()


def test_frozen_rag_evaluation_database_isolation_and_full_trace(tmp_path, test_settings, migrated_database):
    """Actual 50-document SQL pipeline with fakes; no model or provider inference."""
    from contextlib import contextmanager
    from functools import partial
    from sqlalchemy import select, text
    from evidenceops import rag_evaluation as evaluation
    from evidenceops.retrieval import search
    from evidenceops.retrieval_evaluation import frozen_sessions
    from test_retrieval_evaluation import FakeEncoder

    _, corpus = evaluation.inputs(evaluation.DEFAULT_DATASET)
    engine, sessions = create_database(test_settings)
    encoder = FakeEncoder()
    generator = Mock()
    generator.generate.return_value = GeneratedContent(answer='Síntesis artificial [S1].', limitations=[])
    environment = {}
    with sessions() as session:
        before = session.scalars(select(Publication.id)).all()
        schemas = session.scalars(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'retrieval_eval_%' ORDER BY nspname")).all()

    @contextmanager
    def retrieval_context():
        with frozen_sessions(corpus, str(test_settings.database_url), encoder, environment) as isolated:
            yield partial(search, isolated, encoder)

    try:
        path = evaluation.run_evaluation(generator, None, dataset_path=evaluation.DEFAULT_DATASET,
            settings=test_settings, encoder_configuration=encoder.config.metadata(),
            output_dir=tmp_path, environment=environment, retrieval_context=retrieval_context)
        run = evaluation.RagRun.model_validate_json(path.read_bytes())
        evaluation.validate_run(run, evaluation.DEFAULT_DATASET)
        assert run.status == 'complete'
        assert encoder.article_calls == 50 and encoder.query_calls == 10
        assert generator.generate.call_count == 10
        assert all(len(c.retrieved) == 5 for c in run.cases)
        assert run.environment['pgvector_extension']
        with sessions() as session:
            assert session.scalars(select(Publication.id)).all() == before
            assert session.scalars(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'retrieval_eval_%' ORDER BY nspname")).all() == schemas
    finally:
        engine.dispose()
