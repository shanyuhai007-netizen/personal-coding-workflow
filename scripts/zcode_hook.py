#!/usr/bin/env python3
"""Opt-in ZCode hook adapter. Cooperative guard, scoped to one repo and session."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import evidence as ev
import workflow as wf

WORKFLOW = Path(__file__).resolve().parent.parent / 'WORKFLOW.md'


def event_value(event, snake, camel, default=None):
    return event.get(snake, event.get(camel, default))


def guard(task):
    wf.refresh(task)
    missing = [error for stage in task['stages'] for error in wf.problems(task, stage)]
    if task['stages']:
        missing += wf.ac.problems(task)
    missing += ['operation ' + k + ' is unknown; reconcile before retry' for k, v in task.get('operations', {}).items() if v['status'] == 'unknown']
    if task['status'] not in ('VERIFIED', 'ANSWER_ONLY'):
        missing += ['run finish after satisfying all required stages']
    return missing


def read_path(value, repo):
    if isinstance(value, str) and value:
        return (repo / value).resolve()
    return None


def complete_read(event, repo, expected):
    response = event_value(event, 'tool_response', 'toolResponse', {})
    if (event_value(event, 'hook_event_name', 'hookEventName') != 'PostToolUse'
            or not isinstance(response, dict)
            or any(response.get(k) is True for k in ('isError', 'is_error', 'truncated'))):
        return False
    content = response.get('content')
    return (read_path(response.get('filePath', response.get('file_path')), repo) == expected
            and isinstance(content, str)
            and hashlib.sha256(content.encode('utf-8')).hexdigest() == ev.sha(expected))


def observe(task, event, directory, index, repo):
    name = event_value(event, 'hook_event_name', 'hookEventName')
    if name not in ('PostToolUse', 'PostToolUseFailure'):
        return []
    tool = event_value(event, 'tool_name', 'toolName', '')
    args = event_value(event, 'tool_input', 'toolInput', {})
    if tool != 'Read' or not isinstance(args, dict):
        return []
    actual = read_path(args.get('file_path'), repo)
    outputs = []
    for component, source in task.get('component_sources', {}).items():
        expected = Path(source).resolve()
        if actual != expected:
            continue
        ready = [s['id'] for s in task['stages'] if component in s['components'] and s['status'] != 'passed'
                 and all(wf.stage_by_id(task, d)['status'] == 'passed' for d in s['depends_on'])]
        event_data = {'task_id': task['task_id'], 'component': component, 'source': str(expected),
                      'source_hash': ev.sha(expected), 'mode': 'read',
                      'status': 'success' if complete_read(event, repo, expected) else 'failed',
                      'observer': 'zcode_hook', 'session_id': event_value(event, 'session_id', 'sessionId'),
                      'tool_use_id': event_value(event, 'tool_use_id', 'toolUseId'),
                      'raw_event_ref': ev.artifact(directory / ('raw-' + str(index) + '.json')),
                      'attestation': 'host payload observed; loading does not prove method or output quality'}
        for stage_id in ready or [None]:
            output = directory / f'event-{index}-{len(outputs)}.json'
            wf.save(output, {**event_data, 'stage_id': stage_id})
            outputs.append(str(output))
    return outputs


def delivery_identity(task, session):
    return {'session_id': session, 'acceptance': wf.digest(task.get('acceptance')),
            'workflow_sha256': ev.sha(WORKFLOW)}


def observe_delivery_read(task, event, session, repo, raw_path):
    args = event_value(event, 'tool_input', 'toolInput', {})
    if (event_value(event, 'tool_name', 'toolName') == 'Read' and isinstance(args, dict)
            and read_path(args.get('file_path'), repo) == WORKFLOW
            and complete_read(event, repo, WORKFLOW)):
        task['delivery_read'] = {'identity': delivery_identity(task, session), 'raw': ev.artifact(raw_path)}


def delivery_read_current(task, session, repo):
    record = task.get('delivery_read', {})
    if record.get('identity') != delivery_identity(task, session):
        return False
    ref = record['raw']
    ev.verify_artifact(repo, ref)
    return complete_read(wf.read(ev.resolve_file(repo, ref['path'])), repo, WORKFLOW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True)
    parser.add_argument('--repo', required=True)
    args = parser.parse_args()
    event_name = ''
    try:
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Hook payload exceeds supported 1 MiB limit')
        event = json.loads(raw)
        event_name = event_value(event, 'hook_event_name', 'hookEventName', '')
        session = event_value(event, 'session_id', 'sessionId')
        cwd = Path(event.get('cwd', '')).resolve()
        repo = Path(args.repo).resolve()
        if cwd != repo:
            # Config may be global: other repositories are outside this adapter's scope.
            return 0
        if not isinstance(session, str) or not session:
            raise ValueError('Hook needs a session identity')
        with wf.locked(args.record) as path:
            directory = Path(str(path) + '.events')
            directory.mkdir(exist_ok=True)
            binding_path = directory / 'binding.json'
            if binding_path.exists():
                binding = wf.read(binding_path)
                if binding['session_id'] != session:
                    if event_name != 'SessionStart' or event.get('source') not in ('startup', 'resume'):
                        raise ValueError('Another session owns this record; rebind only on a new SessionStart')
                    binding.setdefault('previous_sessions', []).append(binding['session_id'])
                    binding.update(session_id=session, rebound_by='SessionStart')
                    wf.save(binding_path, binding)
            else:
                wf.save(binding_path, {'session_id': session, 'repo': str(repo)})
            index = len(list(directory.glob('raw-*.json')))
            raw_path = directory / ('raw-' + str(index) + '.json')
            wf.save(raw_path, event)
            task = wf.load(path, repo) if path.exists() else None
            missing = ['No task plan; create an evidenced plan with evidence.py plan']
            if task:
                task['host'] = {'status': 'events_observed', 'session_id': session,
                                'last_event': event_name, 'raw_event': str(directory / ('raw-' + str(index) + '.json'))}
                wf.refresh(task)
                task['events'].extend(observe(task, event, directory, index, repo))
                missing = guard(task)
                if task['stages'] and not missing:
                    observe_delivery_read(task, event, session, repo, raw_path)
                wf.save(path, task)
            tool = event_value(event, 'tool_name', 'toolName', '')
            tool_input = event_value(event, 'tool_input', 'toolInput', {})
            command = tool_input.get('command', '') if isinstance(tool_input, dict) else ''
            is_pretool = event_name == 'PreToolUse' and tool == 'Bash'
            commit = is_pretool and bool(re.search(r'\bgit\s+commit\b', command))
            external_actions = [action for action, pattern in (
                ('push', r'\bgit\s+push\b'),
                ('pr_create', r'\bgh\s+pr\s+create\b'),
                ('pr_merge', r'\bgh\s+pr\s+merge\b'),
            ) if is_pretool and re.search(pattern, command)]
            if commit and task and task['status'] not in ('VERIFIED', 'ANSWER_ONLY'):
                missing.append('local commit requires a verified local task')
            for external_action in external_actions:
                authorization = task.get('external_actions', {}).get(external_action, {}) if task else {}
                try:
                    if authorization.get('status') != 'authorized':
                        raise ValueError('authorization status missing')
                    ev.verify_artifact(path.parent, authorization['evidence'])
                except (OSError, ValueError, KeyError, TypeError):
                    missing.append('external action ' + external_action + ' has no verifiable authorization evidence')
            delivery = commit or bool(external_actions)
            if delivery and task and task['stages'] and not missing and not delivery_read_current(task, session, repo):
                missing.append('read the complete installed WORKFLOW.md after finish and before delivery')
            if (event_name == 'Stop' or delivery) and missing:
                message = 'PERSONAL_CODING_INCOMPLETE: ' + '; '.join(missing)
                wf.save(directory / ('rejection-' + str(index) + '.json'), {'event': event_name, 'reason': message})
                print(message, file=sys.stderr)
                return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print('PERSONAL_CODING_HOOK_ERROR: ' + str(exc), file=sys.stderr)
        return 2 if event_name in ('Stop', 'PreToolUse') else 1


if __name__ == '__main__':
    sys.exit(main())
