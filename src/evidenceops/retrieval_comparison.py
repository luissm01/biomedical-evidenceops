"""Compare complete frozen-corpus retrieval runs without inference."""

import argparse
import json
from pathlib import Path

from evidenceops.retrieval_evaluation import aggregate_metrics, publication_metrics, aggregate_latency


def compare(reference: dict, candidate: dict) -> dict:
    for run in (reference, candidate):
        if run['status'] != 'complete':
            raise ValueError('Only complete runs can be compared')
    for key in ('input_sha256', 'corpus_version', 'dataset_version'):
        if reference[key] != candidate[key]:
            raise ValueError(f'Incompatible runs: {key}')
    for key in ('top_k', 'published_from', 'mrr_depth'):
        if reference['configuration'][key] != candidate['configuration'][key]:
            raise ValueError(f'Incompatible runs: {key}')
    rows = []
    indexed = []
    for run in (reference, candidate):
        mapping = {row['query_id']: row for row in run['results']}
        if not mapping or len(mapping) != len(run['results']):
            raise ValueError('Query IDs must be unique and nonempty')
        k = run['configuration']['top_k']
        for row in mapping.values():
            ranking = row['ranking']
            pmids = [item['pmid'] for item in ranking]
            positives = {item['pmid'] for item in ranking if item['relevant']}
            if (len(ranking) != run['configuration']['mrr_depth']
                    or row['top_5'] != pmids[:k]
                    or row['metrics'] != publication_metrics(pmids, positives, k=k)):
                raise ValueError('Inconsistent ranking or metrics')
        measured = ['latency' in row for row in mapping.values()]
        if any(measured) and not all(measured):
            raise ValueError('Incomplete latency measurements')
        if all(measured) and run.get('latency') != aggregate_latency(run['results']):
            raise ValueError('Inconsistent latency aggregate')
        if run['aggregate'] != aggregate_metrics(run['results'], k=k):
            raise ValueError('Inconsistent aggregate')
        indexed.append(mapping)
    before, after = indexed
    if before.keys() != after.keys():
        raise ValueError('Runs must contain the same queries')
    for identity, old in before.items():
        new = after[identity]
        if old['query'] != new['query'] or {
            r['pmid']: (r['content_fingerprint'], r['relevant']) for r in old['ranking']
        } != {r['pmid']: (r['content_fingerprint'], r['relevant']) for r in new['ranking']}:
            raise ValueError('Query, corpus text or judgments differ')
        rows.append({
            'query_id': identity,
            'metric_delta': {key: new['metrics'][key] - value if value is not None else None
                             for key, value in old['metrics'].items()},
            'entered_top_5': [p for p in new['top_5'] if p not in old['top_5']],
            'left_top_5': [p for p in old['top_5'] if p not in new['top_5']],
        })
        if 'latency' in old and 'latency' in new:
            rows[-1]['latency_delta_seconds'] = {
                key: new['latency'][key] - value for key, value in old['latency'].items()
            }
    latency = None
    if 'latency' in reference and 'latency' in candidate:
        latency = {
            'reference': reference['latency'], 'candidate': candidate['latency'],
            'delta_seconds': {stage: {stat: candidate['latency'][stage][stat] - value
                                      for stat, value in stats.items()}
                              for stage, stats in reference['latency'].items()},
            'same_protocol': reference['configuration'].get('latency') == candidate['configuration'].get('latency'),
            'same_environment': reference.get('environment') == candidate.get('environment'),
        }
    return {
        'latency': latency,
        'reference_configuration': reference['configuration'],
        'candidate_configuration': candidate['configuration'],
        'aggregate_delta': {key: candidate['aggregate'][key] - value if value is not None else None
                            for key, value in reference['aggregate'].items()},
        'queries': rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.reference.read_text()),
                             json.loads(args.candidate.read_text())), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
