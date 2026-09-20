"""Synthetic provenance only: private candidate content never enters tests."""
import hashlib
import json

import pytest
from adii.evaluation.exposure import collect, encoded, inventory, main


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value), encoding="utf-8")


@pytest.fixture
def inputs(tmp_path):
    corpus = b'{"custom_id":"Case-001"}\n{"custom_id":" case-001 "}\n{"custom_id":"third"}\n'
    digest = hashlib.sha256(corpus).hexdigest()
    research = tmp_path / 'research'
    for version in ('v1', 'v2'):
        write(research / f'exploratory_capabilities_{version}/selection.json', {
            'source_corpus_sha256': digest,
            'evidence_class': 'UNBLINDED_AI_ASSISTED_EXPLORATORY_ANALYSIS',
            'selected_ids': ['Case-001']})
    write(research / 'quota_cache_fixture_v1/receipt_v2.json', {
        'source': {'corpus_sha256': digest, 'proposal_id': 'Case-001'}})
    write(research / 'semantic_geometry_v1/custodian_sample_v1/selected_ids.json', ['third'])
    (research / 'semantic_geometry_v1/SAMPLE_FREEZE.md').write_text('Sample only')
    write(tmp_path / 'first_model_exposure.json', {'model': 'old', 'timestamp': 'earlier'})
    return corpus, research


def test_exposure_default_identity_coverage_and_determinism(inputs):
    corpus, research = inputs
    result = collect(corpus, research)
    rows = {r['custom_id']: r for r in result['candidates']}
    assert set(rows) == {'Case-001', ' case-001 ', 'third'}
    assert len(result['candidates']) == 3
    assert rows['Case-001']['classification'] == 'KNOWN_EXPOSED'
    assert len(rows['Case-001']['evidence']) == 3
    assert rows[' case-001 ']['classification'] == 'UNKNOWN_EXPOSURE'
    assert rows['third']['classification'] == 'UNKNOWN_EXPOSURE'
    assert rows['third']['evidence'] == []
    assert result['counts'] == {'KNOWN_EXPOSED': 1, 'KNOWN_UNEXPOSED': 0,
                                'UNKNOWN_EXPOSURE': 2}
    assert encoded(result) == encoded(collect(corpus, research))
    assert all(ref['sha256'] and ref['field'] for ref in rows['Case-001']['evidence'])


def test_recorded_model_exposure(inputs, tmp_path):
    corpus, research = inputs
    receipt = tmp_path / 'model.json'
    write(receipt, {'custom_id': 'third', 'model': 'test-model', 'timestamp': '2026-01-01',
                    'corpus_sha256': hashlib.sha256(corpus).hexdigest()})
    result = collect(corpus, research, (receipt,))
    row = next(r for r in result['candidates'] if r['custom_id'] == 'third')
    assert row['classification'] == 'KNOWN_EXPOSED'
    assert row['evidence'][0]['use'] == 'recorded_model_exposure'
    write(receipt, {'model': 'test-model', 'timestamp': '2026-01-01'})
    with pytest.raises(ValueError, match='explicit'):
        collect(corpus, research, (receipt,))


@pytest.mark.parametrize('corpus', [b'{"custom_id":""}', b'{"custom_id":42}',
                                   b'{"custom_id":"a"}\n{"custom_id":"a"}'])
def test_invalid_identity_refused(corpus):
    with pytest.raises(ValueError, match='unique nonempty'):
        inventory(corpus, [], [])


def test_unmapped_candidate_cannot_silently_disappear(inputs):
    corpus, _ = inputs
    with pytest.raises(ValueError, match='outside'):
        inventory(corpus, [{'custom_id': 'missing', 'provenance': {}}], [])


@pytest.mark.parametrize('field,value', [('source_corpus_sha256', 'wrong'),
                                         ('evidence_class', 'BLINDED')])
def test_selection_requires_binding_and_unblinded_statement(inputs, field, value):
    corpus, research = inputs
    path = research / 'exploratory_capabilities_v1/selection.json'
    doc = json.loads(path.read_text())
    doc[field] = value
    write(path, doc)
    with pytest.raises(ValueError, match='declare unblinded'):
        collect(corpus, research)


def test_fixture_requires_corpus_binding(inputs):
    corpus, research = inputs
    path = research / 'quota_cache_fixture_v1/receipt_v2.json'
    doc = json.loads(path.read_text())
    doc['source']['corpus_sha256'] = 'wrong'
    write(path, doc)
    with pytest.raises(ValueError, match='different corpus'):
        collect(corpus, research)


def test_cli_integrity_count_and_write_once(inputs, tmp_path):
    corpus, research = inputs
    path = tmp_path / 'corpus.jsonl'
    path.write_bytes(corpus)
    out = tmp_path / 'inventory.json'
    args = ['--corpus', str(path), '--research-root', str(research),
            '--expected-sha256', hashlib.sha256(corpus).hexdigest(),
            '--expected-count', '3', '--out', str(out)]
    with pytest.raises(ValueError, match='digest'):
        main([*args, '--expected-sha256', 'wrong'])
    with pytest.raises(ValueError, match='count'):
        main([*args, '--expected-count', '4'])
    assert not out.exists()
    assert main(args) == 0
    before = out.read_bytes()
    with pytest.raises(FileExistsError):
        main(args)
    assert out.read_bytes() == before
    other = tmp_path / 'again.json'
    assert main([*args, '--out', str(other)]) == 0
    assert before == other.read_bytes()
