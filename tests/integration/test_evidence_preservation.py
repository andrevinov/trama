"""Integridade do arquivo histórico, sem rede e sem exigir logs locais no clone."""

from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools/check_evidence.py'
CHECK = runpy.run_path(str(TOOL))


@pytest.fixture
def archive(tmp_path):
    versioned = tmp_path / 'docs/evidencias/2026-11-16-example/relatorio.md'
    local = tmp_path / 'logs/example/trace.jsonl'
    versioned.parent.mkdir(parents=True)
    local.parent.mkdir(parents=True)
    versioned.write_text('Resultado histórico com ressalvas.\n')
    local.write_text('{"event":"ai.request_failed"}\n')

    def reference(path):
        content = path.read_bytes()
        return {'path': str(path.relative_to(tmp_path)), 'sha256': sha256(content).hexdigest(), 'bytes': len(content)}

    data = {'schema_version': 1, 'experiments': [{'id': 'example',
            'versioned_artifacts': [reference(versioned)], 'local_artifacts': [reference(local)]}]}
    manifest = tmp_path / 'inventory.json'
    manifest.write_text(json.dumps(data))
    return tmp_path, manifest, versioned, local


def verify(archive, **kwargs):
    root, manifest, *_ = archive
    return CHECK['check_evidence'](manifest, root, **kwargs)


def test_existing_failure_artifacts_are_preserved_without_reinterpreting_outcome(archive):
    result = verify(archive, require_local=True)
    assert result['status'] == 'verified' and result['integrity_ok'] and result['local_complete']
    assert result['verified_versioned'] == result['verified_local'] == 1
    assert archive[-1].read_text() == '{"event":"ai.request_failed"}\n'


@pytest.mark.parametrize('which', [2, 3])
def test_changed_document_or_present_raw_log_is_always_an_integrity_failure(archive, which):
    archive[which].write_text('Conteúdo modificado.\n')
    result = verify(archive)
    assert not result['integrity_ok'] and result['status'] == 'integrity_failed'
    assert result['experiments'][0]['errors'][0]['reason'] == 'content_changed'


def test_clone_without_local_logs_reports_absence_and_strict_mode_rejects_it(archive):
    archive[-1].unlink()
    result = verify(archive)
    assert result['integrity_ok'] and result['status'] == 'local_artifacts_missing'
    assert not result['local_complete'] and result['verified_local'] == 0
    assert result['experiments'][0]['missing_local'] == ['logs/example/trace.jsonl']
    strict = verify(archive, require_local=True)
    assert not strict['integrity_ok'] and strict['status'] == 'local_artifacts_missing'


def test_missing_versioned_report_fails_even_when_logs_are_optional(archive):
    archive[2].unlink()
    result = verify(archive)
    assert not result['integrity_ok']
    assert result['experiments'][0]['errors'][0]['reason'] == 'missing_versioned'


@pytest.mark.parametrize('defect', ['schema_version', 'path', 'digest', 'size', 'duplicate', 'experiment'])
def test_invalid_inventory_does_not_silently_skip_unverifiable_records(archive, defect):
    data = json.loads(archive[1].read_text())
    record = data['experiments'][0]['local_artifacts'][0]
    if defect == 'schema_version':
        data['schema_version'] = True
    elif defect == 'path':
        record['path'] = 'logs/../../outside.json'
    elif defect == 'digest':
        record['sha256'] = 'invalid'
    elif defect == 'size':
        record['bytes'] = -1
    elif defect == 'duplicate':
        data['experiments'][0]['local_artifacts'].append(record)
    else:
        data['experiments'] = [None]
    archive[1].write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(archive)


def test_current_sources_can_evolve_without_rewriting_historical_evidence(archive):
    root = archive[0]
    current = root / 'src/trama/scenarios/dungeon_escape.json'
    current.parent.mkdir(parents=True)
    current.write_text('{"new": "scenario"}')
    data = json.loads(archive[1].read_text())
    data['source_relocations'] = [{'current_path': str(current.relative_to(root)),
                                   'relation': 'identical_bytes_at_preservation', 'sha256': '0' * 64}]
    archive[1].write_text(json.dumps(data))
    assert verify(archive, require_local=True)['integrity_ok']


def test_cli_returns_nonzero_for_missing_logs_in_strict_mode_and_never_creates_files(archive):
    archive[-1].unlink()
    before = {str(p): p.read_bytes() for p in archive[0].rglob('*') if p.is_file()}
    result = subprocess.run([sys.executable, str(TOOL), '--manifest', str(archive[1]),
                            '--root', str(archive[0]), '--require-local'],
                            cwd=archive[0], capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'local_artifacts_missing'
    assert {str(p): p.read_bytes() for p in archive[0].rglob('*') if p.is_file()} == before


def test_registered_archive_matches_versioned_documents_and_original_per_case_hashes():
    inventory = CHECK['DEFAULT_MANIFEST']
    result = CHECK['check_evidence'](inventory, ROOT)
    assert result['integrity_ok'] and result['verified_versioned'] == 3
    data = json.loads(inventory.read_text())
    assert data['kind'] == 'historical_preservation_inventory' and data['new_ai_calls'] == 0
    references = {r['path']: r for e in data['experiments'] for r in e['local_artifacts']}
    assert len(references) == 40
    original = json.loads((ROOT / 'docs/evidencias/2026-11-16-movimento-contextual/manifesto.json').read_text())
    base = 'logs/live/contextual_movement/step12-20261116T205209Z'
    for case in original['measured_results']['cases']:
        for filename, field in [('result.json', 'artifact'), ('trace.jsonl', 'trace')]:
            record = references[f'{base}/{case[field]}']
            assert record['sha256'] == case['sha256'][filename]
            assert record['hash_origin'] == 'original_manifest'
