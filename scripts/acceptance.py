"""Original acceptance projections and observations; semantic equivalence needs review."""
from pathlib import Path
import re

import evidence as ev

COMPUTES = ('count', 'sum', 'mean', 'median', 'min', 'max', 'ratio')


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


def claim_decimals(value):
    text = str(value)
    if not re.fullmatch(r'-?\d+(\.\d+)?', text):
        raise ValueError('Number claim must be a plain decimal, not ' + text)
    return len(text.partition('.')[2])


def extract(data, pattern):
    try:
        found = re.findall(pattern, data)
    except re.error as exc:
        raise ValueError('Invalid number claim pattern: ' + str(exc))
    # findall yields tuples for patterns with groups; the first group is the extracted value.
    return [match[0] if isinstance(match, tuple) else match for match in found]


def recompute(data, claim):
    """Derive a number from sealed raw bytes; None means the claim is not recomputable."""
    if claim['compute'] == 'ratio':
        denominator = len(extract(data, claim['denominator']))
        if not denominator:
            return None
        return len(extract(data, claim['numerator'])) / denominator * claim['scale']
    values = extract(data, claim['pattern'])
    if claim['compute'] == 'count':
        return float(len(values))
    try:
        numbers = [float(value) for value in values]
    except ValueError:
        return None
    if not numbers:
        return None
    if claim['compute'] == 'sum':
        return sum(numbers)
    if claim['compute'] == 'mean':
        return sum(numbers) / len(numbers)
    if claim['compute'] == 'median':
        ordered = sorted(numbers)
        middle = len(ordered) // 2
        return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return min(numbers) if claim['compute'] == 'min' else max(numbers)


def normalize_claim(value):
    if not isinstance(value, dict):
        raise ValueError('Number claim must be an object')
    claim = value.get('claim')
    if isinstance(claim, bool) or not isinstance(claim, (int, float)):
        raise ValueError('Number claim needs a numeric claim value')
    claim_decimals(claim)
    kind = value.get('kind', 'exact')
    if kind not in ('exact', 'approx'):
        raise ValueError('Number claim kind must be exact or approx')
    item = {'claim': claim, 'kind': kind, 'compute': value.get('compute', 'count')}
    if item['compute'] not in COMPUTES:
        raise ValueError('Number claim compute must be one of: ' + ', '.join(COMPUTES))
    tolerance = value.get('tolerance')
    if kind == 'approx':
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise ValueError('Approximate number claims need a nonnegative tolerance')
        item['tolerance'] = tolerance
    elif tolerance is not None:
        raise ValueError('Exact number claims cannot carry a tolerance')
    if item['compute'] == 'ratio':
        for key in ('numerator', 'denominator'):
            if not isinstance(value.get(key), str) or not value[key]:
                raise ValueError('Ratio claims need numerator and denominator patterns')
            item[key] = value[key]
        scale = value.get('scale', 1)
        if isinstance(scale, bool) or not isinstance(scale, (int, float)):
            raise ValueError('Ratio scale must be numeric')
        item['scale'] = scale
    else:
        if not isinstance(value.get('pattern'), str) or not value['pattern']:
            raise ValueError('Number claims need an extraction pattern')
        item['pattern'] = value['pattern']
        if value.get('scale') is not None:
            raise ValueError('Scale applies to ratio claims only')
    return item


def evaluate_claim(item):
    try:
        data = Path(item['source']['path']).read_text()
    except UnicodeDecodeError:
        data = None
    recomputed = recompute(data, item) if data is not None else None
    if recomputed is None:
        return {'recomputed': None, 'verdict': False,
                'mismatch': 'Not recomputable from sealed source: ' + item['source']['path']}
    if item['kind'] == 'approx':
        verdict = abs(recomputed - item['claim']) <= item['tolerance']
    else:
        verdict = round(recomputed, claim_decimals(item['claim'])) == item['claim']
    result = {'recomputed': recomputed, 'verdict': verdict}
    if not verdict:
        result['mismatch'] = 'Claimed {} but recomputed {} from {}'.format(
            item['claim'], recomputed, item['source']['path'])
    return result


def number_claim(value, parent):
    item = normalize_claim(value)
    item['source'] = ev.artifact(ev.resolve_file(parent, text(value.get('source'), 'source')))
    ev.verify_artifact(parent, item['source'])
    item.update(evaluate_claim(item))
    return item


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
        numbers = value.get('numbers')
        if numbers is not None:
            if not isinstance(numbers, list) or not numbers:
                raise ValueError('Number claims must be a nonempty list: ' + key)
            checked = [number_claim(item, path.parent) for item in numbers]
            row['numbers'] = checked
            failed = [item for item in checked if not item['verdict']]
            # A cited number that does not recompute makes the observation unverified,
            # not a new hard stage and not proof of product failure.
            if failed and status != 'unknown':
                status = row['status'] = 'unknown'
                row['next_action'] = ('Number claims do not recompute: '
                                      + '; '.join(item['mismatch'] for item in failed))
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
            for item in (row or {}).get('numbers', []):
                ev.verify_artifact(parent, item['source'])
                # Unknown rows already acknowledge the gap; strict re-evaluation guards declared pass/fail rows.
                if row and row['status'] != 'unknown' and not evaluate_claim(item)['verdict']:
                    raise ValueError('Number claim does not recompute: ' + str(item.get('mismatch', item['claim'])))
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
