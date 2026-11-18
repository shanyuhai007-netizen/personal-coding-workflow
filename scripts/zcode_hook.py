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


def event_value(event, snake, camel, default=None):
    return event.get(snake, event.get(camel, default))


def guard(task):
    wf.refresh(task)
    missing = [error for stage in task['stages'] for error in wf.problems(task, stage)]
    missing += ['operation ' + k + ' is unknown; reconcile before retry' for k, v in task.get('operations', {}).items() if v['status'] == 'unknown']
    if task['status'] not in ('VERIFIED', 'ANSWER_ONLY'):
        missing += ['run finish after satisfying all required stages']
    return missing


def observe(task, event, directory, index, repo):
    name = event_value(event, 'hook_event_name', 'hookEventName')
    if name not in ('PostToolUse', 'PostToolUseFailure'):
        return None
    tool = event_value(event, 'tool_name', 'toolName', '')
    args = event_value(event, 'tool_input', 'toolInput', {})
    response = event_value(event, 'tool_response', 'toolResponse', {})
    failed = name == 'PostToolUseFailure' or (isinstance(response, dict) and (
        any(response.get(k) is True for k in ('isError', 'is_error')) or response.get('truncated') is True))
    for component, source in task.get('component_sources', {}).items():
        expected = Path(source).resolve()
        mode = None
        if tool == 'Read' and isinstance(args.get('file_path'), str):
            actual = Path(args['file_path'])
            actual = actual if actual.is_absolute() else repo / actual
            if actual.resolve() == expected:
                mode = 'read'
        if not mode:
            continue
        if mode == 'read':
            response_path = response.get('filePath', response.get('file_path')) if isinstance(response, dict) else None
            content = response.get('content') if isinstance(response, dict) else None
            response_matches = False
            if isinstance(response_path, str):
                resolved_response = Path(response_path)
                if not resolved_response.is_absolute():
                    resolved_response = repo / resolved_response
                response_matches = resolved_response.resolve() == expected
            content_matches = isinstance(content, str) and hashlib.sha256(content.encode('utf-8')).hexdigest() == ev.sha(expected)
            failed = failed or not response_matches or not content_matches
        stage = next((s for s in task['stages'] if component in s['components'] and s['status'] != 'passed'
                      and all(wf.stage_by_id(task, d)['status'] == 'passed' for d in s['depends_on'])), None)
        result = {'task_id': task['task_id'], 'stage_id': stage['id'] if stage else None,
                  'component': component, 'source': str(expected), 'source_hash': ev.sha(expected),
                  'mode': mode, 'status': 'failed' if failed else 'success', 'observer': 'zcode_hook',
                  'session_id': event_value(event, 'session_id', 'sessionId'),
                  'tool_use_id': event_value(event, 'tool_use_id', 'toolUseId'),
                  'raw_event_ref': ev.artifact(directory / ('raw-' + str(index) + '.json')),
                  'attestation': 'host payload observed; loading does not prove method or output quality'}
        output = directory / ('event-' + str(index) + '.json')
        wf.save(output, result)
        return str(output)
    return None


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
            wf.save(directory / ('raw-' + str(index) + '.json'), event)
            task = wf.load(path, repo) if path.exists() else None
            missing = ['No task plan; create an evidenced plan with evidence.py plan']
            if task:
                task['host'] = {'status': 'events_observed', 'session_id': session,
                                'last_event': event_name, 'raw_event': str(directory / ('raw-' + str(index) + '.json'))}
                wf.refresh(task)
                output = observe(task, event, directory, index, repo)
                if output:
                    task['events'].append(output)
                missing = guard(task)
                wf.save(path, task)
            tool = event_value(event, 'tool_name', 'toolName', '')
            tool_input = event_value(event, 'tool_input', 'toolInput', {})
            command = tool_input.get('command', '') if isinstance(tool_input, dict) else ''
            is_pretool = event_name == 'PreToolUse' and tool == 'Bash'
            commit = is_pretool and bool(re.search(r'\bgit\s+commit\b', command))
            external_action = None
            if is_pretool and re.search(r'\bgit\s+push\b', command):
                external_action = 'push'
            elif is_pretool and re.search(r'\bgh\s+pr\s+create\b', command):
                external_action = 'pr_create'
            elif is_pretool and re.search(r'\bgh\s+pr\s+merge\b', command):
                external_action = 'pr_merge'
            if commit and task and task['status'] not in ('VERIFIED', 'ANSWER_ONLY'):
                missing.append('local commit requires a verified local task')
            if external_action:
                authorization = task.get('external_actions', {}).get(external_action, {}) if task else {}
                try:
                    if authorization.get('status') != 'authorized':
                        raise ValueError('authorization status missing')
                    ev.verify_artifact(path.parent, authorization['evidence'])
                except (OSError, ValueError, KeyError, TypeError):
                    missing.append('external action ' + external_action + ' has no verifiable authorization evidence')
            delivery = commit or external_action is not None
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
