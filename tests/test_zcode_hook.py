"""Replay-level observer calibration; these tests do not launch the host."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_workflow as contract

HOOK = Path(__file__).resolve().parents[1] / 'scripts/zcode_hook.py'


class HookTests(unittest.TestCase):
    setUp = contract.WorkflowTests.setUp
    git = contract.WorkflowTests.git
    cli = contract.WorkflowTests.cli
    plan = contract.WorkflowTests.plan
    state = contract.WorkflowTests.state
    make_receipt = contract.WorkflowTests.make_receipt
    complete = contract.WorkflowTests.complete
    accept = contract.WorkflowTests.accept
    def hook(self, kind, **extra):
        event = {'hook_event_name': kind, 'session_id': 'fixture-session', 'cwd': str(self.repo)}
        event.update(extra)
        return subprocess.run([sys.executable, str(HOOK), '--record', str(self.record), '--repo', str(self.repo)],
                              input=json.dumps(event), capture_output=True, text=True)

    def test_stop_without_plan_is_rejected_without_calling_validator(self):
        result = self.hook('Stop')
        self.assertEqual(result.returncode, 2)
        self.assertIn('No task plan', result.stderr)
        self.assertFalse(self.record.exists())

    def test_prefix_same_filename_success_and_failure_are_distinguished(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        wrong = self.root / 'elsewhere' / 'tdd.md'
        wrong.parent.mkdir()
        wrong.write_text('not the registered component')
        for tool, tool_input in [('Bash', {'command': 'true'}), ('Read', {'file_path': str(wrong)})]:
            self.assertEqual(self.hook('PostToolUse', tool_name=tool, tool_input=tool_input).returncode, 0)
        self.assertEqual(self.state()['events'], [])
        content = (self.root / 'tdd.md').read_text()
        expected_path = str(self.root / 'tdd.md')
        events = [
            ('PostToolUseFailure', {}),
            ('PostToolUse', {'filePath': expected_path, 'content': content, 'truncated': True}),
            ('PostToolUse', {'filePath': str(wrong), 'content': content, 'truncated': False}),
            ('PostToolUse', {'filePath': expected_path, 'content': content, 'truncated': False}),
        ]
        for kind, response in events:
            result = self.hook(kind, tool_name='Read', tool_input={'file_path': str(self.root / 'tdd.md')},
                               tool_response=response, tool_use_id=kind)
            self.assertEqual(result.returncode, 0, result.stderr)
        observed = [json.loads(Path(p).read_text()) for p in self.state()['events']]
        self.assertEqual([e['status'] for e in observed], ['failed', 'failed', 'failed', 'success'])
        self.assertEqual(observed[3]['stage_id'], 'implement')
        result = self.hook('Stop')
        self.assertEqual(result.returncode, 2)
        self.assertIn('implement', result.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')
        proof = self.root / 'captured-method.md'
        proof.write_text('The specialist source was read in the host and its guidance was applied to the synthetic implementation.\n')
        receipt = self.root / 'host-read-receipt.json'
        result = self.cli('stage-receipt', self.record, '--stage', 'implement', '--obligation', 'tdd',
                          '--mode', 'read', '--verification', 'pass', '--source', self.root / 'tdd.md',
                          '--input', self.root / 'facts.json', '--input', self.repo / 'app.txt',
                          '--event', self.state()['events'][-1], '--artifact', proof,
                          '--adaptation', 'Synthetic ZCode Read payload adapter', '--out', receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('stage-complete', self.record, '--stage', 'implement', '--receipt', receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hook('PreToolUse', tool_name='Bash', tool_input={'command': 'git commit -m fixture'}).returncode, 2)

    def test_completed_document_task_passes_stop_and_other_repo_is_untouched(self):
        contract.WorkflowTests.test_short_document_path_recovers_across_processes_and_finishes(self)
        self.assertEqual(self.hook('Stop').returncode, 0)
        self.assertEqual(self.hook('Stop', cwd=str(self.root)).returncode, 0)
        self.assertEqual(self.hook('Stop', session_id='different-session').returncode, 2)

    def test_push_requires_recorded_external_authorization(self):
        self.assertEqual(self.plan().returncode, 0)
        for stage in ('preflight', 'document', 'verify', 'close'):
            self.assertEqual(self.complete(stage).returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        result = self.hook('PreToolUse', tool_name='Bash', tool_input={'command': 'git push origin main'})
        self.assertEqual(result.returncode, 2)
        self.assertIn('no verifiable authorization evidence', result.stderr)
        task = self.state()
        proof = self.root / 'authorization.md'
        proof.write_text('Synthetic explicit user authorization for this fixture push.\n')
        import hashlib
        task['external_actions']['push'] = {'status': 'authorized', 'evidence': {
            'path': str(proof), 'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()}}
        self.record.write_text(json.dumps(task))
        self.assertEqual(self.hook('PreToolUse', tool_name='Bash', tool_input={'command': 'git push origin main'}).returncode, 0)

    def test_compound_command_requires_each_external_action_authorization(self):
        self.test_push_requires_recorded_external_authorization()
        commands = [
            ('git push origin main && gh pr create --title fixture', 'pr_create'),
            ('git push origin main; gh pr merge 1', 'pr_merge'),
        ]
        for command, missing in commands:
            result = self.hook('PreToolUse', tool_name='Bash', tool_input={'command': command})
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('external action ' + missing, result.stderr)
        task = self.state()
        task['external_actions']['pr_create'] = task['external_actions']['push']
        self.record.write_text(json.dumps(task))
        result = self.hook('PreToolUse', tool_name='Bash', tool_input={
            'command': 'gh pr create --title fixture && gh pr merge 1'})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('external action pr_merge', result.stderr)
        task = self.state()
        task['external_actions']['pr_merge'] = task['external_actions']['push']
        self.record.write_text(json.dumps(task))
        self.assertEqual(self.hook('PreToolUse', tool_name='Bash', tool_input={
            'command': 'git push origin main && gh pr create --title fixture && gh pr merge 1'}).returncode, 0)

    def test_new_session_can_resume_persisted_task_only_at_session_start(self):
        self.assertEqual(self.plan().returncode, 0)
        self.assertEqual(self.hook('SessionStart', source='startup').returncode, 0)
        self.assertEqual(self.hook('Stop', session_id='new-session').returncode, 2)
        rebound = self.hook('SessionStart', source='resume', session_id='new-session')
        self.assertEqual(rebound.returncode, 0, rebound.stderr)
        self.assertEqual(self.state()['host']['session_id'], 'new-session')
        binding = json.loads((Path(str(self.record) + '.events') / 'binding.json').read_text())
        self.assertEqual(binding['previous_sessions'], ['fixture-session'])
