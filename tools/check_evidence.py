"""Confere evidências históricas por hash, sem executar simulador, testes live ou IA."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / 'docs/evidencias/2026-11-16-preservacao-das-analises/manifesto.json'


def check_evidence(manifest: Path, root: Path, *, require_local=False) -> dict:
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or
            type(data.get('schema_version')) is not int or data['schema_version'] != 1 or
            not isinstance(data.get('experiments'), list) or not data['experiments'] or
            not all(isinstance(e, dict) for e in data['experiments'])):
        raise ValueError('Inventário de evidências inválido ou com versão não suportada.')
    root = root.resolve()
    seen_ids, seen_paths = set(), set()
    entries = []
    for experiment in data['experiments']:
        id = experiment.get('id')
        if not isinstance(id, str) or not id or id in seen_ids:
            raise ValueError('Identificador de experimento inválido ou duplicado.')
        seen_ids.add(id)
        entry = {'id': id, 'verified_versioned': 0, 'verified_local': 0, 'missing_local': [], 'errors': []}
        for group, prefix in (('versioned_artifacts', 'docs/evidencias/'), ('local_artifacts', 'logs/')):
            artifacts = experiment.get(group)
            if not isinstance(artifacts, list) or not all(isinstance(a, dict) for a in artifacts):
                raise ValueError(f'Lista de artefatos inválida: {id}/{group}.')
            for artifact in artifacts:
                name, digest, size = (artifact.get(k) for k in ('path', 'sha256', 'bytes'))
                if (not isinstance(name, str) or not name.startswith(prefix) or
                        '\\' in name or '..' in Path(name).parts or
                        not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest) or
                        type(size) is not int or size < 0 or name in seen_paths):
                    raise ValueError(f'Referência de artefato inválida ou duplicada: {id}.')
                seen_paths.add(name)
                path = (root / name).resolve()
                if not path.is_relative_to(root):
                    raise ValueError('O artefato precisa estar dentro da raiz informada.')
                if not path.exists():
                    if group == 'local_artifacts':
                        entry['missing_local'].append(name)
                    else:
                        entry['errors'].append({'path': name, 'reason': 'missing_versioned'})
                    continue
                if not path.is_file():
                    entry['errors'].append({'path': name, 'reason': 'not_a_file'})
                    continue
                with path.open('rb') as source:
                    actual = file_digest(source, 'sha256').hexdigest()
                if path.stat().st_size != size or actual != digest:
                    entry['errors'].append({'path': name, 'reason': 'content_changed', 'actual_sha256': actual})
                else:
                    entry['verified_local' if group == 'local_artifacts' else 'verified_versioned'] += 1
        entries.append(entry)
    errors = [error for entry in entries for error in entry['errors']]
    missing_local = [name for entry in entries for name in entry['missing_local']]
    return {
        'status': 'integrity_failed' if errors else 'local_artifacts_missing' if missing_local else 'verified',
        'integrity_ok': not errors and (not require_local or not missing_local),
        'local_complete': not missing_local,
        'require_local': require_local,
        'verified_versioned': sum(e['verified_versioned'] for e in entries),
        'verified_local': sum(e['verified_local'] for e in entries),
        'experiments': entries,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--root', type=Path, default=ROOT, help='Raiz à qual os caminhos do inventário se referem.')
    parser.add_argument('--require-local', action='store_true', help='Reprova também se faltarem logs brutos locais.')
    args = parser.parse_args(argv)
    try:
        result = check_evidence(args.manifest, args.root, require_local=args.require_local)
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'invalid_inventory', 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['integrity_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
