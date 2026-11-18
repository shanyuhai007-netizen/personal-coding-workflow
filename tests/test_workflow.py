"""Contract tests through the installed public CLI, with synthetic repositories."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evidence.py'


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'app.txt').write_text('fixture\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.record = self.root / 'task.json'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args]).decode().strip()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=self.repo,
                              capture_output=True, text=True)

    def plan(self, intent='implement', **features):
        facts = {'intent': {'value': intent, 'evidence': 'synthetic user request'}}
        facts.update({k: {'value': v, 'evidence': 'synthetic fixture contract'} for k, v in features.items()})
        path = self.root / 'facts.json'
        sources = {}
        for name in ('tdd', 'code-review', 'grilling', 'research', 'diagnosing-bugs', 'independent-fact-review', 'modern-web-guidance', 'vercel-react-best-practices'):
            source = self.root / (name + '.md')
            source.write_text('Synthetic ' + name + ' source.\n')
            sources[name] = str(source)
        path.write_text(json.dumps({'component_sources': sources, 'task_id': 'fixture-task', 'goal': 'Exercise public contract',
                                    'facts': facts, 'max_attempts': 3}))
        return self.cli('plan', '--facts', path, '--record', self.record)

    def state(self):
        return json.loads(self.record.read_text())

    def test_plan_unions_ui_react_obligations_and_finish_rejects_omission(self):
        result = self.plan(behavior_change=True, ui=True, react=True, interaction=True, nontrivial=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        stages = self.state()['stages']
        required = {c for s in stages for c in s['components']}
        self.assertTrue({'modern-web-guidance', 'vercel-react-best-practices', 'tdd', 'code-review'} <= required)
        result = self.cli('finish', self.record)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preflight', result.stderr)
        result = self.cli('next', self.record, '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['id'], 'preflight')
        self.assertNotEqual(self.state()['status'], 'VERIFIED')


    def make_receipt(self, stage, obligation='output', mode='read', **options):
        proof = self.root / 'proof.md'
        proof.write_text('Synthetic successful execution and verification trace.\n')
        source = self.root / (obligation + '.md')
        source.write_text('Synthetic ' + obligation + ' source.\n')
        out = self.root / ('receipt-' + str(len(list(self.root.glob('receipt-*.json')))) + '.json')
        event = self.root / ('event-' + str(len(list(self.root.glob('receipt-*.json')))) + '.json')
        if obligation != 'output' and mode in ('read', 'reuse'):
            result = self.cli('component-event', self.record, '--stage', stage, '--obligation', obligation,
                              '--mode', mode, '--source', source, '--proof', proof,
                              '--status', options.get('event_status', 'success'))
            self.assertEqual(result.returncode, 0, result.stderr)
            event = Path(result.stdout.strip())
        else:
            event.write_text(json.dumps({'task_id': 'fixture-task', 'stage_id': stage, 'component': obligation,
                                         'source': str(source), 'source_hash': hashlib.sha256(source.read_bytes()).hexdigest(),
                                         'mode': mode, 'status': options.get('event_status', 'success')}))
        args = ['stage-receipt', self.record, '--stage', stage, '--obligation', obligation,
                '--mode', mode, '--verification', options.get('verification', 'pass'),
                '--adaptation', 'synthetic pc contract', '--event', event, '--artifact', proof,
                '--input', self.root / 'facts.json', '--out', out]
        if stage in ('implement', 'document'):
            args += ['--input', self.repo / 'app.txt']
        if stage == 'verify':
            check = self.root / ('check-' + out.stem)
            self.assertEqual(self.cli('run', '--out', check, '--', sys.executable, '-c', 'print("fixture behavior checked")').returncode, 0)
            args += ['--check', check / 'result.json']
        if obligation != 'output':
            args += ['--source', source]
        if options.get('reviewer'):
            args += ['--independent', '--reviewer-id', options['reviewer']]
        if options.get('reuse_check'):
            args += ['--reuse-check', proof]
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out

    def complete(self, stage, obligation='output', **options):
        path = self.make_receipt(stage, obligation, **options)
        return self.cli('stage-complete', self.record, '--stage', stage, '--receipt', path)

    def test_short_document_path_recovers_across_processes_and_finishes(self):
        self.assertEqual(self.plan().returncode, 0)
        self.assertEqual([s['id'] for s in self.state()['stages']],
                         ['preflight', 'document', 'verify', 'close'])
        for stage in ('preflight', 'document', 'verify', 'close'):
            self.assertEqual(json.loads(self.cli('next', self.record, '--json').stdout)['id'], stage)
            result = self.complete(stage)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        self.assertEqual(self.state()['status'], 'VERIFIED')
        self.assertEqual(self.state()['external_actions'], {})

    def test_old_task_receipt_dependencies_and_degraded_do_not_pass(self):
        self.assertEqual(self.plan().returncode, 0)
        self.assertIn('Dependencies unmet', self.complete('verify').stderr)
        path = self.make_receipt('preflight')
        value = json.loads(path.read_text())
        value['task_id'] = 'other-task'
        path.write_text(json.dumps(value))
        result = self.cli('stage-complete', self.record, '--stage', 'preflight', '--receipt', path)
        self.assertIn('identity mismatch', result.stderr)
        self.assertIn('Degraded', self.complete('preflight', mode='degraded').stderr)
        self.assertEqual(self.complete('preflight').returncode, 0)

    def test_changed_inputs_invalidate_evidence_and_budget_preserves_blocker(self):
        self.assertEqual(self.plan().returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('document').returncode, 0)
        (self.repo / 'app.txt').write_text('changed implementation\n')
        result = self.cli('next', self.record, '--json')
        self.assertEqual(json.loads(result.stdout)['id'], 'document')
        # Preflight has explicit stable inputs; code edits do not erase it.
        self.assertEqual(self.state()['stages'][0]['status'], 'passed')
        for _ in range(3):
            self.assertNotEqual(self.complete('document', verification='unknown').returncode, 0)
        self.assertEqual(self.state()['status'], 'BLOCKED')
        self.assertIn('budget exhausted', self.complete('document').stderr)
        self.assertNotEqual(self.cli('finish', self.record).returncode, 0)
        recovery = self.root / 'recovery.md'
        recovery.write_text('Root cause fixed; starting a new bounded cycle.\n')
        resumed = self.cli('stage-resume', self.record, '--stage', 'document', '--reason', 'Repaired fixture input', '--proof', recovery)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.complete('document').returncode, 0)
        self.assertEqual(self.state()['stages'][1]['attempt_history'][-1]['resume_reason'], 'Repaired fixture input')
        for _ in range(3):
            self.assertNotEqual(self.complete('document', verification='unknown').returncode, 0)
        self.assertEqual(self.state()['stages'][1]['status'], 'blocked')
        second_resume = self.cli('stage-resume', self.record, '--stage', 'document',
                                 '--reason', 'Another attempt', '--proof', recovery)
        self.assertNotEqual(second_resume.returncode, 0)
        self.assertIn('single bounded resume cycle', second_resume.stderr)

    def test_reuse_needs_current_applicability_and_review_needs_independence(self):
        self.assertEqual(self.plan(intent='review').returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertIn('Independent', self.complete('standards', 'code-review').stderr)
        self.assertEqual(self.complete('standards', 'code-review', reviewer='reviewer-a').returncode, 0)
        self.assertIn('separate reviewers', self.complete('spec-review', 'code-review', reviewer='reviewer-a').stderr)
        self.assertEqual(self.complete('spec-review', 'code-review', reviewer='reviewer-b').returncode, 0)
        self.assertIn('applicability', self.complete('close', mode='reuse').stderr)
        self.assertEqual(self.complete('close', mode='reuse', reuse_check=True).returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)

    def test_business_clarification_allows_independent_research(self):
        self.assertEqual(self.plan(business_unknown=True, unfamiliar_api=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('research', 'research').returncode, 0)
        self.assertIn('Dependencies unmet', self.complete('document').stderr)

    def test_unknown_side_effect_requires_reconciliation_before_completion(self):
        self.assertEqual(self.plan().returncode, 0)
        for stage in ('preflight', 'document', 'verify', 'close'):
            self.assertEqual(self.complete(stage).returncode, 0)
        args = ['operation', self.record, '--stage', 'close', '--operation-id', 'fixture-write']
        self.assertEqual(self.cli(*args, '--result', 'begin').returncode, 0)
        applied = self.root / 'applied.txt'
        applied.write_text('authorized fixture side effect applied once\n')
        self.assertNotEqual(self.cli(*args, '--result', 'begin').returncode, 0)
        self.assertIn('unknown', self.cli('finish', self.record).stderr)
        self.assertEqual(self.cli(*args, '--result', 'applied', '--proof', applied).returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)

    def test_structured_routing_fixtures_not_natural_language_classification(self):
        cases = json.loads((SCRIPT.parents[1] / 'tests/fixtures/routes.json').read_text())
        for case in cases:
            with self.subTest(case=case['id']):
                # Each case is a fresh task, not a revision that accumulates debt.
                self.record = self.root / (case['id'] + '.json')
                result = self.plan(case['intent'], **case['features'])
                self.assertEqual(result.returncode, 0, result.stderr)
                selected = {s['id'] for s in self.state()['stages']}
                self.assertTrue(set(case['required']) <= selected)
                self.assertFalse(set(case['forbidden']) & selected)

    def test_unrelated_component_source_cannot_satisfy_named_obligation(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        path = self.make_receipt('implement', 'tdd')
        value = json.loads(path.read_text())
        other = self.root / 'unrelated.md'
        other.write_text('Unrelated source with valid hash\n')
        value['sources'] = [{'path': str(other), 'sha256': hashlib.sha256(other.read_bytes()).hexdigest()}]
        path.write_text(json.dumps(value))
        result = self.cli('stage-complete', self.record, '--stage', 'implement', '--receipt', path)
        self.assertIn('canonical source identity', result.stderr)

    def test_unregistered_success_event_cannot_satisfy_component_obligation(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        receipt = self.make_receipt('implement', 'tdd')
        value = json.loads(receipt.read_text())
        original = Path(value['observed_event_ref']['path'])
        spoof = self.root / 'unregistered-success.json'
        spoof.write_bytes(original.read_bytes())
        value['observed_event_ref'] = {'path': str(spoof), 'sha256': hashlib.sha256(spoof.read_bytes()).hexdigest()}
        receipt.write_text(json.dumps(value))
        result = self.cli('stage-complete', self.record, '--stage', 'implement', '--receipt', receipt)
        self.assertIn('not registered to this task', result.stderr)

    def test_completed_existing_implementation_skips_work_and_binds_preflight_tree(self):
        self.assertEqual(self.plan(behavior_change=True, nontrivial=True, existing_implementation=True,
                                   implementation_complete=True).returncode, 0)
        task = self.state()
        stages = {stage['id']: stage for stage in task['stages']}
        self.assertNotIn('implement', stages)
        self.assertEqual(stages['preflight']['scope'], 'tree')
        self.assertTrue({'verify', 'standards', 'spec-review'} <= set(stages))
        self.assertEqual(self.complete('preflight').returncode, 0)
        preflight = self.state()['stages'][0]
        receipt = json.loads(Path(preflight['receipts'][0]).read_text())
        self.assertIn('tree', receipt['input_identity'])
        (self.repo / 'app.txt').write_text('new code after preflight\n')
        self.assertEqual(json.loads(self.cli('next', self.record, '--json').stdout)['id'], 'preflight')

    def test_failed_component_event_cannot_be_claimed_success(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        result = self.complete('implement', 'tdd', event_status='failed')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('successful component event', result.stderr)

    def test_plan_revision_adds_formal_review_and_retains_old_obligations(self):
        self.assertEqual(self.plan().returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        result = self.plan(intent='design', formal_decision=True)
        self.assertNotEqual(result.returncode, 0)
        result = self.cli('plan', '--facts', self.root / 'facts.json', '--record', self.record,
                          '--reason', 'New ADR scope from user')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('fact-review', [s['id'] for s in self.state()['stages']])
        self.assertIn('document', [s['id'] for s in self.state()['stages']])
        self.assertTrue(all(s['status'] == 'needs_verification' for s in self.state()['stages']
                            if s['status'] == 'passed'))
        self.assertEqual(json.loads(self.cli('next', self.record, '--json').stdout)['id'], 'preflight')
        self.assertEqual(len(self.state()['revisions']), 2)


if __name__ == '__main__':
    unittest.main()
