"""Task-scoped cooperative workflow guards; not an execution attestation system."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

import evidence as ev
import acceptance as ac

RULES = Path(__file__).with_name('workflow_rules.json')


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
        temporary = out.name
    os.replace(temporary, path)


@contextmanager
def locked(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield path


def selected(when, facts):
    terms = []
    if 'intents' in when:
        terms.append(facts['intent']['value'] in when['intents'])
    for key in ('any', 'all', 'none'):
        if key in when:
            values = [facts.get(f, {}).get('value', False) for f in when[key]]
            terms.append(any(values) if key == 'any' else all(values) if key == 'all' else not any(values))
    match = any(terms) if when.get('match') == 'or' else all(terms)
    if when.get('design_nontrivial') and facts['intent']['value'] == 'design' and facts.get('nontrivial', {}).get('value'):
        match = True
    return match


def compile_stages(facts, rules):
    if facts['intent']['value'] == 'question':
        return []
    stages = []
    for rule in rules['stages']:
        if rule['id'] == 'implement' and facts.get('implementation_complete', {}).get('value', False):
            continue
        if selected(rule['when'], facts):
            stage = {k: v for k, v in rule.items() if k not in ('when', 'after', 'optional_components')}
            if rule['id'] == 'preflight' and facts.get('implementation_complete', {}).get('value', False):
                stage['scope'] = 'tree'
            optional = [c for c in stage['components'] if c in rule.get('optional_components', [])]
            stage.update(status='pending', receipts=[], attempts=0, goal_refs=['user-goal'],
                         required_obligations=[c for c in stage['components'] if c not in optional],
                         optional_obligations=optional[:])
            stages.append(stage)
    set_dependencies(stages, rules)
    return stages


def set_dependencies(stages, rules):
    ids = {s['id'] for s in stages}
    for stage in stages:
        rule = next(r for r in rules['stages'] if r['id'] == stage['id'])
        candidates = ids - {stage['id']} if rule['after'] == ['*'] else rule['after']
        stage['depends_on'] = sorted(set(candidates) & ids)
        if stage['id'] != 'preflight' and 'preflight' not in stage['depends_on']:
            stage['depends_on'].append('preflight')


def plan(args):
    source = read(args.facts)
    rules = read(RULES)
    facts = source['facts']
    if set(facts) - set(rules['facts']) - {'intent'}:
        raise ValueError('Unknown facts; revise the rule source explicitly')
    if not source['task_id'].strip() or not source['goal'].strip():
        raise ValueError('Task identity and goal are required')
    for name, value in facts.items():
        if not isinstance(value['evidence'], str) or not value['evidence'].strip():
            raise ValueError('Every supplied fact needs an evidence reference: ' + name)
        if name == 'intent':
            if value['value'] not in rules['intents']:
                raise ValueError('Unknown intent')
        elif type(value['value']) is not bool:
            raise ValueError('Feature facts must be boolean')
    if facts.get('implementation_complete', {}).get('value', False) and not facts.get('existing_implementation', {}).get('value', False):
        raise ValueError('A complete implementation must be identified as existing')
    if 'intent' not in facts:
        raise ValueError('Intent is required')
    budget = source.get('max_attempts', 3)
    if type(budget) is not int or budget < 1:
        raise ValueError('Positive max_attempts required')
    root = ev.outside_repo(args.repo, args.record)
    if ev.volatile(args.record):
        raise ValueError('Record location is periodically purged; keep task records in a durable directory outside the repository (docs/EXECUTION.md)')
    stages = compile_stages(facts, rules)
    conditions = ac.conditions(source, Path(args.facts).resolve().parent) if stages else []
    with locked(args.record) as path:
        if path.exists():
            old = load(path, root)
            if old['task_id'] != source['task_id']:
                raise ValueError('Cannot replace another task')
            if not args.reason:
                raise ValueError('Plan revision needs a reason')
            previous = {s['id']: s for s in old['stages']}
            # Obligations accumulate. Changing labels never silently removes debt.
            for stage in stages:
                if stage['id'] in previous:
                    stage.update(previous.pop(stage['id']))
            stages.extend(previous.values())
            order = {r['id']: i for i, r in enumerate(rules['stages'])}
            stages.sort(key=lambda s: order[s['id']])
            set_dependencies(stages, rules)
            changed_plan_facts = old['facts'] != facts or old['goal'] != source['goal'] or old.get('conditions') != conditions
            if changed_plan_facts:
                preflight = stage_by_id({'stages': stages}, 'preflight')
                preflight['status'] = 'needs_verification'
                # A revision demands explicit re-verification; mechanical revalidation must not satisfy it.
                preflight['recheck_required'] = True
            revisions = old['revisions'] + [{'reason': args.reason, 'goal': source['goal'], 'facts': facts, 'conditions': conditions, 'at': time.time()}]
            task = old
            task.update(stages=stages, revisions=revisions, facts=facts, goal=source['goal'], status='IN_PROGRESS')
        else:
            task = {'schema': 1, 'task_id': source['task_id'], 'repo': str(root), 'goal': source['goal'],
                    'facts': facts, 'stages': stages, 'status': 'IN_PROGRESS',
                    'revisions': [{'reason': 'initial', 'goal': source['goal'], 'facts': facts, 'conditions': conditions, 'at': time.time()}],
                    'max_attempts': budget, 'events': [], 'external_actions': {},
                    'component_sources': source.get('component_sources', {}),
                    'rules_hash': ev.sha(RULES), 'host': {'status': 'not_observed'}}
        task['component_sources'] = {**task.get('component_sources', {}), **source.get('component_sources', {})}
        task['conditions'] = conditions
        task['rules_hash'] = ev.sha(RULES)
        refresh(task)
        save(path, task)
    print(view(task))
    return 0


def load(path, repo=None):
    task = read(path)
    if task['schema'] != 1 or task['rules_hash'] != ev.sha(RULES):
        raise ValueError('Unsupported or changed rules; explicitly revise plan')
    if repo is not None and Path(task['repo']).resolve() != Path(repo).resolve():
        raise ValueError('Task repository identity mismatch')
    task['record_path'] = str(Path(path).resolve())
    return task


def stage_by_id(task, name):
    return next(s for s in task['stages'] if s['id'] == name)


def declared_obligations(stage):
    """Required plus optional component obligations; 'output' is tracked separately."""
    return stage['required_obligations'] + stage.get('optional_obligations', [])


def obligation_failures(stage, receipts):
    """Explain every way the receipt set misses the declared obligations; empty means satisfied."""
    needed = set(stage['required_obligations'] or ['output'])
    optional = set(stage.get('optional_obligations', []))
    covered = {r['obligation_id'] for r in receipts}
    counts = {}
    for receipt in receipts:
        counts[receipt['obligation_id']] = counts.get(receipt['obligation_id'], 0) + 1
    failures = []
    if not needed <= covered:
        failures.append('missing required obligations: ' + ', '.join(sorted(needed - covered)))
    if covered - needed - optional:
        failures.append('undeclared extra obligations: ' + ', '.join(sorted(covered - needed - optional)))
    if len(receipts) != len(covered):
        failures.append('duplicate obligation receipts: ' + ', '.join(sorted(o for o, n in counts.items() if n > 1)))
    return failures


def identity(task, stage, inputs, pinned=None):
    value = {'files': {str(Path(p).resolve()): ev.sha(p) for p in inputs}}
    if pinned:
        value['pinned'] = pinned
    if stage.get('scope') == 'tree':
        value['tree'] = ev.code_tree(task['repo'])
    if stage['id'] in ('standards', 'spec-review', 'close'):
        value['acceptance'] = digest(task.get('acceptance'))
        value['conditions'] = digest(task.get('conditions'))
    if not value['files'] and not value.get('pinned') and 'tree' not in value:
        raise ValueError('Stage needs relevant input files')
    return value


def verify_identity(task, value):
    for path, expected in value['files'].items():
        if ev.sha(path) != expected:
            raise ValueError('Changed stage input: ' + path)
    for path, snapshot in value.get('pinned', {}).items():
        if not Path(snapshot['path']).is_file() or ev.sha(snapshot['path']) != snapshot['sha256']:
            raise ValueError('Pinned input snapshot missing or changed: ' + path)
    if 'tree' in value and ev.code_tree(task['repo']) != value['tree']:
        raise ValueError('Changed code tree')
    for key in ('conditions', 'acceptance'):
        if key in value and value[key] != digest(task.get(key)):
            raise ValueError('Changed ' + key + '; recheck review/closure inputs')


def verify_receipt(task, stage, receipt_path):
    receipt_path = Path(receipt_path)
    receipt = read(receipt_path)
    if (receipt['task_id'], receipt['stage_id']) != (task['task_id'], stage['id']):
        raise ValueError('Receipt task/stage identity mismatch')
    if receipt['obligation_id'] not in declared_obligations(stage) + ['output']:
        raise ValueError('Unexpected obligation')
    if receipt['mode'] not in ('native', 'read', 'reuse', 'degraded'):
        raise ValueError('Invalid component mode')
    if receipt['mode'] == 'degraded':
        raise ValueError('Degraded receipt preserves a limitation; it cannot satisfy a required stage')
    if not receipt.get('adaptation', '').strip():
        raise ValueError('Component adaptation is required')
    if receipt['verification'] != 'pass':
        raise ValueError('Stage verification is not pass')
    if stage['id'] in ('standards', 'spec-review', 'close') and not {'conditions', 'acceptance'} <= receipt['input_identity'].keys():
        raise ValueError('Original conditions and acceptance identity required; recheck legacy review/closure')
    verify_identity(task, receipt['input_identity'])
    refs = receipt['sources'] + receipt['artifacts']
    if receipt.get('observed_event_ref'):
        refs.append(receipt['observed_event_ref'])
    if receipt.get('refile'):
        refs.append(receipt['refile']['source_receipt'])
    for item in refs:
        ev.verify_artifact(receipt_path.parent, item)
    if stage['id'] == 'verify' and not receipt.get('checks'):
        raise ValueError('Actual verification needs at least one captured check')
    if stage.get('doctor_check') and not any(item.get('role') == 'doctor' for item in receipt.get('checks', [])):
        raise ValueError('Doctor-gated interaction verification needs a captured doctor check proving the running instance; run the project doctor via the run tool and pass --doctor-check')
    for check_ref in receipt.get('checks', []):
        ev.verify_artifact(receipt_path.parent, check_ref)
        check_path = ev.resolve_file(receipt_path.parent, check_ref['path'])
        check = read(check_path)
        tree = ev.code_tree(task['repo'])
        if check['exit_code'] != 0 or check['tree_before'] != tree or check['tree_after'] != tree:
            raise ValueError('Failed or stale verification check')
        if check['output_sha256'] != ev.sha(check_path.parent / 'output.log'):
            raise ValueError('Check output changed')
    if not receipt['artifacts']:
        raise ValueError('Verified stage needs output artifacts')
    if receipt['obligation_id'] != 'output':
        expected = task.get('component_sources', {}).get(receipt['obligation_id'])
        actual = [str(ev.resolve_file(receipt_path.parent, item['path']).resolve()) for item in receipt['sources']]
        if not expected or str(Path(expected).resolve()) not in actual:
            raise ValueError('Target component canonical source identity missing')
        if receipt['mode'] in ('native', 'read', 'reuse'):
            if not receipt.get('observed_event_ref'):
                raise ValueError('Component obligation requires an observed event; register one or recreate the receipt')
            event = read(ev.resolve_file(receipt_path.parent, receipt['observed_event_ref']['path']))
            event_path = str(ev.resolve_file(receipt_path.parent, receipt['observed_event_ref']['path']).resolve())
            if event_path not in {str(Path(value).resolve()) for value in task['events']}:
                raise ValueError('Component event is not registered to this task')
            if (event.get('task_id'), event.get('stage_id'), event.get('component'), event.get('mode'), event.get('status')) != (task['task_id'], stage['id'], receipt['obligation_id'], receipt['mode'], 'success'):
                raise ValueError('A successful component event bound to this task/stage/mode is required')
            if event.get('observer') not in ('zcode_hook', 'agent_declared'):
                raise ValueError('Component event observer is unsupported')
            if receipt['mode'] == 'native' and event.get('observer') != 'zcode_hook':
                raise ValueError('Native mode requires a host-observed event')
            if task['host']['status'] == 'events_observed' and event.get('observer') != 'zcode_hook':
                raise ValueError('This task has host observation enabled; manual events cannot replace it')
            if event.get('observer') == 'zcode_hook':
                binding = read(Path(task['record_path'] + '.events') / 'binding.json')
                sessions = set(binding.get('previous_sessions', [])) | {binding['session_id']}
                if event.get('session_id') not in sessions:
                    raise ValueError('Component event session is not bound to this task')
                raw_ref = event['raw_event_ref']
                ev.verify_artifact(receipt_path.parent, raw_ref)
                raw_event = read(ev.resolve_file(receipt_path.parent, raw_ref['path']))
                raw_name = raw_event.get('hook_event_name', raw_event.get('hookEventName'))
                raw_session = raw_event.get('session_id', raw_event.get('sessionId'))
                raw_tool = raw_event.get('tool_name', raw_event.get('toolName'))
                raw_input = raw_event.get('tool_input', raw_event.get('toolInput', {}))
                raw_response = raw_event.get('tool_response', raw_event.get('toolResponse', {}))
                raw_path = raw_input.get('file_path') if isinstance(raw_input, dict) else None
                response_path = raw_response.get('filePath', raw_response.get('file_path')) if isinstance(raw_response, dict) else None
                response_content = raw_response.get('content') if isinstance(raw_response, dict) else None
                raw_path = Path(raw_path or '')
                response_path = Path(response_path or '')
                if not raw_path.is_absolute():
                    raw_path = Path(task['repo']) / raw_path
                if not response_path.is_absolute():
                    response_path = Path(task['repo']) / response_path
                if (raw_name != 'PostToolUse' or raw_session != event['session_id'] or raw_tool != 'Read'
                        or str(raw_path.resolve()) != str(Path(expected).resolve())
                        or str(response_path.resolve()) != str(Path(expected).resolve())
                        or not isinstance(response_content, str)
                        or hashlib.sha256(response_content.encode('utf-8')).hexdigest() != event['source_hash']
                        or raw_response.get('truncated') is True):
                    raise ValueError('Raw host event does not prove a complete read of this component source')
            if event.get('observer') == 'agent_declared':
                ev.verify_artifact(receipt_path.parent, event['execution_proof'])
            if str(Path(event.get('source', '')).resolve()) != str(Path(expected).resolve()):
                raise ValueError('Component event source identity mismatch')
            if event.get('source_hash') not in {source['sha256'] for source in receipt['sources']
                                                if str(ev.resolve_file(receipt_path.parent, source['path']).resolve()) == str(Path(expected).resolve())}:
                raise ValueError('Component event source hash differs from captured source')
    if stage.get('independent') and (receipt['independent'] is not True or not receipt['reviewer_id'].strip()):
        raise ValueError('Independent reviewer required')
    if receipt['mode'] == 'reuse':
        if not receipt.get('reuse_check'):
            raise ValueError('Reuse needs applicability verification')
        ev.verify_artifact(receipt_path.parent, receipt['reuse_check'])
    return receipt


def receipt_problems(task, stage):
    """Receipt-level verification only; independent of the stage status field."""
    try:
        receipts = [verify_receipt(task, stage, p) for p in stage['receipts']]
        failures = obligation_failures(stage, receipts)
        if failures:
            raise ValueError('Stage obligation set mismatch: ' + '; '.join(failures))
        if stage.get('independent'):
            others = [read(p) for s in task['stages'] if s['id'] in ('standards', 'spec-review')
                      and s['id'] != stage['id'] and s['status'] == 'passed' for p in s['receipts']]
            if any(a['reviewer_id'] == b['reviewer_id'] for a in receipts for b in others):
                raise ValueError('Standards and Spec require separate reviewers')
        return []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [stage['id'] + ': ' + str(exc)]


def problems(task, stage):
    if stage['status'] != 'passed':
        return ['stage ' + stage['id'] + ' is ' + stage['status']]
    return receipt_problems(task, stage)


def refresh(task):
    for stage in task['stages']:
        deps = [s for s in task['stages'] if s['id'] in stage['depends_on']]
        if stage['status'] == 'passed':
            errors = receipt_problems(task, stage)
            if errors or any(s['status'] != 'passed' for s in deps):
                reason = errors or ['Dependency changed']
                stage['status'] = 'needs_verification'
                stage['invalidated_reason'] = reason
                stage.setdefault('invalidation_history', []).append({'at': time.time(), 'reason': reason})
                task['status'] = 'IN_PROGRESS'
        elif stage['status'] == 'needs_verification' and stage.get('receipts') and not stage.get('recheck_required'):
            # A stage demoted only by a dependency failure still holds valid evidence
            # once the dependency recovers; revalidate instead of forcing manual replay.
            if all(s['status'] == 'passed' for s in deps) and not receipt_problems(task, stage):
                stage['status'] = 'passed'
                stage.pop('invalidated_reason', None)
                stage.setdefault('revalidations', []).append({'at': time.time()})
    if task['stages'] and ac.problems(task) and task['status'] == 'VERIFIED':
        task['status'] = 'IN_PROGRESS'


def view(task):
    labels = {'pending': '待开始', 'passed': '通过', 'needs_verification': '待验证', 'blocked': '受阻'}
    lines = [f"目标：{task['goal']} | 修订 {len(task['revisions'])} | 本地 {task['status']} | 宿主 {task['host']['status']}",
             '| 阶段 | 所需组件 | 通过依据 | 状态 |', '|---|---|---|---|']
    for s in task['stages']:
        lines.append('| ' + ' | '.join([s['id'] + ' · ' + s['goal'], ', '.join(s['components']) or '核心流程',
                                        s['done_when'], labels[s['status']]]) + ' |')
    return '\n'.join(lines)


def operate(args):
    with locked(args.record) as path:
        task = load(path)
        refresh(task)
        if args.command == 'next':
            stage = next((s for s in task['stages'] if s['status'] not in ('passed', 'blocked')
                          and all(stage_by_id(task, dep)['status'] == 'passed' for dep in s['depends_on'])), None)
            save(path, task)
            print(json.dumps(stage, ensure_ascii=False) if args.json else view(task))
            return 0
        if args.command == 'finish':
            if ev.volatile(path):
                save(path, task)
                raise ValueError('Record location is periodically purged; VERIFIED evidence would not persist')
            missing = (ac.problems(task) if task['stages'] else []) + ['operation ' + k + ' remains unknown; reconcile before retry' for k, v in task.get('operations', {}).items() if v['status'] == 'unknown'] + [p for s in task['stages'] for p in problems(task, s)]
            if missing:
                save(path, task)
                raise ValueError('Missing requirements; complete/verify: ' + '; '.join(missing))
            task['status'] = 'VERIFIED' if task['stages'] else 'ANSWER_ONLY'
            save(path, task)
            print(task['status'] + ': record consistency only; external actions require separate authorization')
            print(ac.summary(task))
            return 0
        stage = stage_by_id(task, args.stage)
        if any(v['stage_id'] == stage['id'] and v['status'] == 'unknown' for v in task.get('operations', {}).values()):
            raise ValueError('Operation outcome unknown; reconcile before retry or completion')
        if stage['attempts'] >= task['max_attempts']:
            raise ValueError('Stage budget exhausted; preserve evidence and resolve blocker')
        cost = None
        if getattr(args, 'cost', None):
            cost = read(args.cost)
            if not isinstance(cost, dict) or not str(cost.get('basis', '')).strip():
                raise ValueError('Cost declaration needs a non-empty basis describing its measurement source')
            for key in ('tokens', 'duration_ms'):
                if key in cost and (type(cost[key]) not in (int, float) or cost[key] < 0):
                    raise ValueError('Cost ' + key + ' must be a non-negative number')
            cost = {key: cost[key] for key in ('tokens', 'duration_ms', 'basis', 'note') if key in cost}
        deps = [s for s in task['stages'] if s['id'] in stage['depends_on']]
        if any(s['status'] != 'passed' for s in deps):
            save(path, task)
            raise ValueError('Dependencies unmet: ' + ', '.join(s['id'] for s in deps if s['status'] != 'passed'))
        old_receipts = stage['receipts'][:]
        try:
            receipts = [verify_receipt(task, stage, p) for p in args.receipt]
            failures = obligation_failures(stage, receipts)
            if failures:
                raise ValueError('Stage obligation set mismatch: ' + '; '.join(failures))
            stage.update(status='passed', receipts=[str(Path(p).resolve()) for p in args.receipt])
            errors = problems(task, stage)
            if errors:
                raise ValueError('; '.join(errors))
            stage.pop('recheck_required', None)
            stage.setdefault('completions', []).append({'at': time.time()})
            if cost is not None:
                stage.setdefault('costs', []).append({'at': time.time(), **cost})
            # One completion can recover dependencies; cascade revalidation immediately.
            refresh(task)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            stage['receipts'] = old_receipts
            stage['attempts'] += 1
            stage.setdefault('attempt_history', []).append({'attempt': stage['attempts'], 'error': str(exc),
                                                           'at': time.time()})
            stage['status'] = 'blocked' if stage['attempts'] >= task['max_attempts'] else 'needs_verification'
            stage['last_error'] = str(exc)
            task['status'] = 'BLOCKED' if stage['status'] == 'blocked' else 'IN_PROGRESS'
            save(path, task)
            raise
        save(path, task)
        print(view(task))
        return 0


def latest_event(task, stage, obligation, mode):
    """Newest registered success event matching this receipt; events are append-ordered."""
    match = None
    for value in task['events']:
        try:
            event = read(value)
        except (OSError, ValueError):
            continue
        if (event.get('task_id'), event.get('stage_id'), event.get('component'),
                event.get('mode'), event.get('status')) == (task['task_id'], stage['id'], obligation, mode, 'success'):
            match = ev.artifact(value)
    return match


def receipt(args):
    task = load(args.record)
    stage = stage_by_id(task, args.stage)
    out = Path(args.out).resolve()
    ev.outside_repo(task['repo'], out)
    if out.exists():
        raise ValueError('Receipt already exists; preserve history with a new path')
    inputs = [str(Path(p).resolve()) for p in args.input]
    pins = [str(Path(p).resolve()) for p in args.pin_input]
    overlap = sorted(set(inputs) & set(pins))
    if overlap:
        raise ValueError('Inputs are live-bound or pinned, not both: ' + ', '.join(overlap))
    if len(set(pins)) != len(pins):
        raise ValueError('Duplicate pinned inputs')
    if pins and stage.get('scope') == 'tree':
        # Final gates must keep binding the delivered tree; pinned snapshots would weaken that.
        raise ValueError('Tree-scoped stages bind the full tree; inputs cannot be pinned here')
    pinned = {}
    if pins:
        store = out.parent / (out.stem + '.inputs')
        store.mkdir(parents=True, exist_ok=False)
        for index, source in enumerate(pins):
            target = store / (str(index) + '-' + Path(source).name)
            shutil.copyfile(source, target)
            pinned[source] = ev.artifact(target)
    event_ref = None
    if args.event:
        event_ref = ev.artifact(args.event)
        if args.obligation != 'output':
            try:
                json.loads(Path(args.event).resolve().read_text())
            except ValueError:
                raise ValueError('component 阶段的 --event 必须是 component-event 产出的 JSON 文件')
    elif args.obligation != 'output':
        event_ref = latest_event(task, stage, args.obligation, args.mode)
        if event_ref is None:
            raise ValueError('No registered success event for obligation ' + args.obligation + ' on stage ' +
                             stage['id'] + ' mode ' + args.mode + '; run component-event first or pass --event')
    data = {'task_id': task['task_id'], 'stage_id': stage['id'], 'obligation_id': args.obligation,
            'mode': args.mode, 'verification': args.verification, 'adaptation': args.adaptation,
            'input_identity': identity(task, stage, args.input, pinned),
            'sources': [ev.artifact(p) for p in args.source],
            'checks': [ev.artifact(p) for p in args.check] +
                      ([{**ev.artifact(args.doctor_check), 'role': 'doctor'}] if args.doctor_check else []),
            'observed_event_ref': event_ref, 'artifacts': [ev.artifact(p) for p in args.artifact],
            'independent': args.independent, 'reviewer_id': args.reviewer_id,
            'at': time.time(),
            'attestation': 'caller-declared; source/event hashes do not prove method quality'}
    if args.reuse_check:
        data['reuse_check'] = ev.artifact(args.reuse_check)
    if not args.adaptation.strip():
        raise ValueError('Adaptation is required')
    out.parent.mkdir(parents=True, exist_ok=True)
    save(out, data)
    print(out)
    return 0


def refile(args):
    """Rebind a file-bound receipt to current hashes after a semantics-neutral change."""
    task = load(args.record)
    source_path = Path(args.receipt).resolve()
    source = read(source_path)
    if (source.get('task_id'), source.get('stage_id')) != (task['task_id'], args.stage):
        raise ValueError('Receipt task/stage identity mismatch')
    if not args.reason.strip():
        raise ValueError('Refile needs an explicit reason for why semantics are unchanged')
    stage = stage_by_id(task, args.stage)
    if source.get('obligation_id') not in declared_obligations(stage) + ['output']:
        raise ValueError('Unexpected obligation')
    previous = source.get('input_identity')
    if not previous or set(previous) - {'files', 'pinned'}:
        raise ValueError('Only file-bound receipts can be refiled; tree/condition-bound work needs a fresh receipt')
    files = {str(Path(p).resolve()): ev.sha(p) for p in previous['files']}
    changed = sorted(path for path, value in files.items() if previous['files'][path] != value)
    data = {key: value for key, value in source.items() if key not in ('input_identity', 'refile')}
    identity_value = {'files': files}
    if 'pinned' in previous:
        identity_value['pinned'] = previous['pinned']
    data['input_identity'] = identity_value
    data['refile'] = {'source_receipt': ev.artifact(source_path), 'reason': args.reason.strip(),
                      'changed_paths': changed, 'at': time.time()}
    out = Path(args.out).resolve()
    ev.outside_repo(task['repo'], out)
    if out.exists():
        raise ValueError('Receipt already exists; preserve history with a new path')
    out.parent.mkdir(parents=True, exist_ok=True)
    save(out, data)
    print(out)
    return 0


def operation(args):
    with locked(args.record) as path:
        task = load(path)
        stage_by_id(task, args.stage)
        operations = task.setdefault('operations', {})
        old = operations.get(args.operation_id)
        if args.result == 'begin':
            if old:
                raise ValueError('Operation identity already exists; reconcile instead of retry')
            operations[args.operation_id] = {'stage_id': args.stage, 'status': 'unknown'}
        else:
            if not old or old['stage_id'] != args.stage or not args.proof:
                raise ValueError('Reconciliation needs existing operation identity and proof')
            old.update(status=args.result, reconciliation=ev.artifact(args.proof))
        task['status'] = 'IN_PROGRESS'
        save(path, task)
    print('Operation recorded; no side effect executed by this command')
    return 0


def resume_stage(args):
    with locked(args.record) as path:
        task = load(path)
        stage = stage_by_id(task, args.stage)
        if stage['status'] != 'blocked':
            raise ValueError('Only a budget-exhausted stage can be explicitly resumed')
        if stage.get('resume_cycles', 0) >= 1:
            raise ValueError('The single bounded resume cycle was exhausted; create a reviewed new task for a new attempt')
        proof = ev.artifact(args.proof)
        stage.setdefault('attempt_history', []).append({'resume_reason': args.reason,
                                                        'recovery_proof': proof, 'at': time.time()})
        stage.update(status='needs_verification', attempts=0,
                     resume_cycles=stage.get('resume_cycles', 0) + 1, last_error='')
        task['status'] = 'IN_PROGRESS'
        save(path, task)
    print('Stage resumed with a new bounded attempt cycle; prior failures are preserved')
    return 0


def component_event(args):
    with locked(args.record) as path:
        task = load(path)
        stage = stage_by_id(task, args.stage)
        if args.obligation not in declared_obligations(stage):
            raise ValueError('Component is not declared for this stage')
        if args.mode not in ('read', 'reuse'):
            raise ValueError('Manual events can record read or reuse; native requires host observation')
        source = Path(args.source).resolve()
        expected = task.get('component_sources', {}).get(args.obligation)
        if not expected or source != Path(expected).resolve():
            raise ValueError('Source path does not match the registered component')
        proof = ev.artifact(args.proof)
        events_dir = Path(str(path) + '.events')
        events_dir.mkdir(exist_ok=True)
        index = len(list(events_dir.glob('manual-*.json')))
        event_path = events_dir / ('manual-' + str(index) + '.json')
        value = {'task_id': task['task_id'], 'stage_id': stage['id'], 'component': args.obligation,
                 'source': str(source), 'source_hash': ev.sha(source), 'mode': args.mode,
                 'status': args.status, 'observer': 'agent_declared', 'execution_proof': proof,
                 'attestation': 'agent declared after reading/rechecking; no host auto-observation'}
        save(event_path, value)
        task['events'].append(str(event_path))
        save(path, task)
    print(event_path)
    return 0


def acceptance(args):
    with locked(args.record) as path:
        task = load(path)
        value = ac.capture(task, args.report)
        if task.get('acceptance') != value:
            if task.get('acceptance'):
                task.setdefault('acceptance_history', []).append(task['acceptance'])
            task['acceptance'] = value
            task['status'] = 'IN_PROGRESS'
        refresh(task)
        save(path, task)
    print(ac.summary(task))
    print('Observations captured; run finish after required acceptance and reviews')
    return 0


def add_parsers(sub):
    p = sub.add_parser('acceptance', help='Capture observations against original conditions; never grants completion')
    p.add_argument('record')
    p.add_argument('--report', required=True)
    p = sub.add_parser('stage-resume', help='Begin a new bounded attempt cycle after a concrete fix')
    p.add_argument('record')
    p.add_argument('--stage', required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--proof', required=True)
    p = sub.add_parser('component-event', help='Record a declared read/reuse event; native requires the host adapter')
    p.add_argument('record')
    for name in ('stage', 'obligation', 'source', 'proof'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--mode', choices=['read', 'reuse'], required=True)
    p.add_argument('--status', choices=['success', 'failed', 'unknown'], required=True)
    p = sub.add_parser('operation', help='Persist unknown outcome before an authorized side effect; reconcile before retry')
    p.add_argument('record')
    p.add_argument('--stage', required=True)
    p.add_argument('--operation-id', required=True)
    p.add_argument('--result', choices=['begin', 'applied', 'not_applied'], required=True)
    p.add_argument('--proof')
    p = sub.add_parser('plan', help='Compile evidenced task facts into cumulative obligations')
    p.add_argument('--facts', required=True)
    p.add_argument('--record', required=True)
    p.add_argument('--repo', default='.')
    p.add_argument('--reason', default='')
    for name in ('next', 'finish', 'stage-complete'):
        p = sub.add_parser(name)
        p.add_argument('record')
        if name == 'next':
            p.add_argument('--json', action='store_true')
        if name == 'stage-complete':
            p.add_argument('--stage', required=True)
            p.add_argument('--receipt', action='append', required=True)
            p.add_argument('--cost', help='Optional declared cost JSON: {tokens?, duration_ms?, basis}')
    p = sub.add_parser('receipt-refile', help='Rebind a file-bound receipt to current hashes after a semantics-neutral change')
    p.add_argument('record')
    for name in ('receipt', 'stage', 'reason', 'out'):
        p.add_argument('--' + name, required=True)
    p = sub.add_parser('stage-receipt')
    p.add_argument('record')
    for name in ('stage', 'obligation', 'out', 'adaptation'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--event', default='', help='Optional; auto-matches the latest registered success event when omitted')
    p.add_argument('--mode', choices=['native', 'read', 'reuse', 'degraded'], required=True)
    p.add_argument('--verification', choices=['pass', 'fail', 'unknown'], required=True)
    for name in ('input', 'pin-input', 'source', 'artifact', 'check'):
        p.add_argument('--' + name, action='append', default=[])
    p.add_argument('--doctor-check', default='',
                   help='Captured run-tool result proving the running instance for doctor-gated stages')
    p.add_argument('--independent', action='store_true')
    p.add_argument('--reviewer-id', default='')
    p.add_argument('--reuse-check')


def dispatch(args):
    if args.command == 'acceptance':
        return acceptance(args)
    if args.command == 'component-event':
        return component_event(args)
    if args.command == 'stage-resume':
        return resume_stage(args)
    if args.command == 'operation':
        return operation(args)
    if args.command == 'plan':
        return plan(args)
    if args.command == 'stage-receipt':
        return receipt(args)
    if args.command == 'receipt-refile':
        return refile(args)
    return operate(args)
