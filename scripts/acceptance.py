"""Original acceptance projections and observations; semantic equivalence needs review."""
from pathlib import Path

import evidence as ev


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Acceptance needs nonempty ' + field)
    return value


def conditions(source, parent):
    values = source.get('conditions')
    if not isinstance(values, list) or not values:
        raise ValueError('Original acceptance conditions are required; reference existing project assets')
    result = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError('Acceptance condition must be an object')
        item = {key: text(value.get(key), key) for key in ('id', 'locator', 'requirement', 'target')}
        path = ev.resolve_file(parent, text(value.get('source'), 'source'))
        item['source'] = ev.artifact(path)
        ev.verify_artifact(parent, item['source'])
        result.append(item)
    if len({v['id'] for v in result}) != len(result):
        raise ValueError('Duplicate acceptance condition id')
    return result


def verify_conditions(task):
    if not task.get('conditions'):
        raise ValueError('Original acceptance conditions missing; explicitly replan with project conditions')
    for condition in task['conditions']:
        ev.verify_artifact(Path(task['record_path']).parent, condition['source'])


def capture(task, report_path):
    import json
    verify_conditions(task)
    path = Path(report_path).resolve()
    rows = json.loads(path.read_text())
    if not isinstance(rows, list):
        raise ValueError('Acceptance report must be a list of observations')
    expected = {v['id']: v for v in task['conditions']}
    captured = []
    seen = set()
    for value in rows:
        if not isinstance(value, dict):
            raise ValueError('Acceptance observation must be an object')
        key = value.get('id')
        if key not in expected or key in seen:
            raise ValueError('Unknown or duplicate acceptance condition: ' + str(key))
        seen.add(key)
        status = value.get('status')
        if status not in ('pass', 'fail', 'unknown'):
            raise ValueError('Acceptance status must be pass, fail or unknown: ' + key)
        row = {'id': key, 'status': status, 'target': expected[key]['target']}
        for field in ('behavior', 'target', 'observation'):
            if status in ('pass', 'fail') or field in value:
                row[field] = text(value.get(field), field)
        if row['target'] != expected[key]['target']:
            raise ValueError('Acceptance target differs from original condition: ' + key)
        if status in ('pass', 'fail') or 'evidence' in value:
            evidence = value.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                raise ValueError('Observed acceptance needs raw evidence: ' + key)
            row['evidence'] = [ev.artifact(ev.resolve_file(path.parent, text(p, 'evidence path'))) for p in evidence]
            for item in row['evidence']:
                ev.verify_artifact(path.parent, item)
        if status != 'pass':
            row['next_action'] = text(value.get('next_action'), 'next_action')
        captured.append(row)
    return {'report': ev.artifact(path), 'tree': ev.code_tree(task['repo']),
            'conditions': task['conditions'], 'observations': captured,
            'attestation': 'caller-declared observations; semantic sufficiency requires actual acceptance and review'}


def problems(task):
    try:
        verify_conditions(task)
        value = task.get('acceptance')
        if not value:
            raise ValueError('Original acceptance observations missing: ' + ', '.join(v['id'] for v in task['conditions']))
        parent = Path(task['record_path']).parent
        ev.verify_artifact(parent, value['report'])
        if value['conditions'] != task['conditions'] or value['tree'] != ev.code_tree(task['repo']):
            raise ValueError('Stale acceptance conditions or code tree')
        observed = {r['id']: r for r in value['observations']}
        missing = []
        for condition in task['conditions']:
            row = observed.get(condition['id'])
            for item in (row or {}).get('evidence', []):
                ev.verify_artifact(parent, item)
            if not row or row['status'] != 'pass':
                missing.append(condition['id'] + ': ' + (row['status'] + '; ' + row['next_action'] if row else 'unverified'))
        return missing
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ['acceptance: ' + str(exc)]


def summary(task):
    rows = {r['id']: r for r in (task.get('acceptance') or {}).get('observations', [])}
    lines = []
    for condition in task.get('conditions', []):
        row = rows.get(condition['id'], {'status': 'unverified'})
        lines.append(condition['id'] + ' · ' + condition['requirement'] + ' [' + condition['target'] + ']: ' + row['status']
                     + ('; ' + row['next_action'] if row.get('next_action') else ''))
        lines.append('  source: ' + condition['source']['path'] + ' · ' + condition['locator'])
        for key in ('behavior', 'observation'):
            if key in row:
                lines.append('  ' + key + ': ' + row[key])
        if row.get('evidence'):
            lines.append('  evidence: ' + ', '.join(v['path'] for v in row['evidence']))
    if task.get('acceptance'):
        lines.append('  code tree: ' + task['acceptance']['tree'])
    return '\n'.join(lines)
