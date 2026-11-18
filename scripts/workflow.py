"""Task-scoped cooperative workflow guards; not an execution attestation system."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import evidence as ev

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
            stage = {k: v for k, v in rule.items() if k not in ('when', 'after')}
            if rule['id'] == 'preflight' and facts.get('implementation_complete', {}).get('value', False):
                stage['scope'] = 'tree'
            stage.update(status='pending', receipts=[], attempts=0, goal_refs=['user-goal'], required_obligations=stage['components'][:])
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
    stages = compile_stages(facts, rules)
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
            changed_plan_facts = old['facts'] != facts or old['goal'] != source['goal']
            if changed_plan_facts:
                stage_by_id({'stages': stages}, 'preflight')['status'] = 'needs_verification'
            revisions = old['revisions'] + [{'reason': args.reason, 'facts': facts, 'at': time.time()}]
            task = old
            task.update(stages=stages, revisions=revisions, facts=facts, goal=source['goal'], status='IN_PROGRESS')
        else:
            task = {'schema': 1, 'task_id': source['task_id'], 'repo': str(root), 'goal': source['goal'],
                    'facts': facts, 'stages': stages, 'status': 'IN_PROGRESS',
                    'revisions': [{'reason': 'initial', 'facts': facts, 'at': time.time()}],
                    'max_attempts': budget, 'events': [], 'external_actions': {},
                    'component_sources': source.get('component_sources', {}),
                    'rules_hash': ev.sha(RULES), 'host': {'status': 'not_observed'}}
        task['component_sources'] = {**task.get('component_sources', {}), **source.get('component_sources', {})}
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


def identity(task, stage, inputs):
    value = {'files': {str(Path(p).resolve()): ev.sha(p) for p in inputs}}
    if stage.get('scope') == 'tree':
        value['tree'] = ev.code_tree(task['repo'])
    if not value['files'] and 'tree' not in value:
        raise ValueError('Stage needs relevant input files')
    return value


def verify_identity(task, value):
    for path, expected in value['files'].items():
        if ev.sha(path) != expected:
            raise ValueError('Changed stage input: ' + path)
    if 'tree' in value and ev.code_tree(task['repo']) != value['tree']:
        raise ValueError('Changed code tree')


def verify_receipt(task, stage, receipt_path):
    receipt_path = Path(receipt_path)
    receipt = read(receipt_path)
    if (receipt['task_id'], receipt['stage_id']) != (task['task_id'], stage['id']):
        raise ValueError('Receipt task/stage identity mismatch')
    if receipt['obligation_id'] not in stage['required_obligations'] + ['output']:
        raise ValueError('Unexpected obligation')
    if receipt['mode'] not in ('native', 'read', 'reuse', 'degraded'):
        raise ValueError('Invalid component mode')
    if receipt['mode'] == 'degraded':
        raise ValueError('Degraded receipt preserves a limitation; it cannot satisfy a required stage')
    if not receipt.get('adaptation', '').strip():
        raise ValueError('Component adaptation is required')
    if receipt['verification'] != 'pass':
        raise ValueError('Stage verification is not pass')
    verify_identity(task, receipt['input_identity'])
    for item in receipt['sources'] + receipt['artifacts'] + [receipt['observed_event_ref']]:
        ev.verify_artifact(receipt_path.parent, item)
    if stage['id'] == 'verify' and not receipt.get('checks'):
        raise ValueError('Actual verification needs at least one captured check')
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


def problems(task, stage):
    if stage['status'] != 'passed':
        return ['stage ' + stage['id'] + ' is ' + stage['status']]
    try:
        receipts = [verify_receipt(task, stage, p) for p in stage['receipts']]
        needed = set(stage['required_obligations'] or ['output'])
        if needed != {r['obligation_id'] for r in receipts} or len(receipts) != len(needed):
            raise ValueError('Missing or duplicate obligation receipts')
        if stage.get('independent'):
            others = [read(p) for s in task['stages'] if s['id'] in ('standards', 'spec-review')
                      and s['id'] != stage['id'] and s['status'] == 'passed' for p in s['receipts']]
            if any(a['reviewer_id'] == b['reviewer_id'] for a in receipts for b in others):
                raise ValueError('Standards and Spec require separate reviewers')
        return []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [stage['id'] + ': ' + str(exc)]


def refresh(task):
    for stage in task['stages']:
        if stage['status'] == 'passed':
            errors = problems(task, stage)
            deps = [s for s in task['stages'] if s['id'] in stage['depends_on']]
            if errors or any(s['status'] != 'passed' for s in deps):
                stage['status'] = 'needs_verification'
                stage['invalidated_reason'] = errors or ['Dependency changed']
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
            missing = ['operation ' + k + ' remains unknown; reconcile before retry' for k, v in task.get('operations', {}).items() if v['status'] == 'unknown'] + [p for s in task['stages'] for p in problems(task, s)]
            if missing:
                save(path, task)
                raise ValueError('Missing requirements; complete/verify: ' + '; '.join(missing))
            task['status'] = 'VERIFIED' if task['stages'] else 'ANSWER_ONLY'
            save(path, task)
            print(task['status'] + ': record consistency only; external actions require separate authorization')
            return 0
        stage = stage_by_id(task, args.stage)
        if any(v['stage_id'] == stage['id'] and v['status'] == 'unknown' for v in task.get('operations', {}).values()):
            raise ValueError('Operation outcome unknown; reconcile before retry or completion')
        if stage['attempts'] >= task['max_attempts']:
            raise ValueError('Stage budget exhausted; preserve evidence and resolve blocker')
        deps = [s for s in task['stages'] if s['id'] in stage['depends_on']]
        if any(s['status'] != 'passed' for s in deps):
            save(path, task)
            raise ValueError('Dependencies unmet: ' + ', '.join(s['id'] for s in deps if s['status'] != 'passed'))
        old_receipts = stage['receipts'][:]
        try:
            needed = set(stage['required_obligations'] or ['output'])
            receipts = [verify_receipt(task, stage, p) for p in args.receipt]
            if {r['obligation_id'] for r in receipts} != needed or len(receipts) != len(needed):
                raise ValueError('Required obligation set mismatch: ' + ', '.join(sorted(needed)))
            stage.update(status='passed', receipts=[str(Path(p).resolve()) for p in args.receipt])
            errors = problems(task, stage)
            if errors:
                raise ValueError('; '.join(errors))
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


def receipt(args):
    task = load(args.record)
    stage = stage_by_id(task, args.stage)
    out = Path(args.out).resolve()
    ev.outside_repo(task['repo'], out)
    data = {'task_id': task['task_id'], 'stage_id': stage['id'], 'obligation_id': args.obligation,
            'mode': args.mode, 'verification': args.verification, 'adaptation': args.adaptation,
            'input_identity': identity(task, stage, args.input), 'sources': [ev.artifact(p) for p in args.source],
            'checks': [ev.artifact(p) for p in args.check],
            'observed_event_ref': ev.artifact(args.event), 'artifacts': [ev.artifact(p) for p in args.artifact],
            'independent': args.independent, 'reviewer_id': args.reviewer_id,
            'attestation': 'caller-declared; source/event hashes do not prove method quality'}
    if args.reuse_check:
        data['reuse_check'] = ev.artifact(args.reuse_check)
    if not args.adaptation.strip():
        raise ValueError('Adaptation is required')
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise ValueError('Receipt already exists; preserve history with a new path')
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
        if args.obligation not in stage['required_obligations']:
            raise ValueError('Component is not required by this stage')
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


def add_parsers(sub):
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
    p = sub.add_parser('stage-receipt')
    p.add_argument('record')
    for name in ('stage', 'obligation', 'out', 'event', 'adaptation'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--mode', choices=['native', 'read', 'reuse', 'degraded'], required=True)
    p.add_argument('--verification', choices=['pass', 'fail', 'unknown'], required=True)
    for name in ('input', 'source', 'artifact', 'check'):
        p.add_argument('--' + name, action='append', default=[])
    p.add_argument('--independent', action='store_true')
    p.add_argument('--reviewer-id', default='')
    p.add_argument('--reuse-check')


def dispatch(args):
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
    return operate(args)
