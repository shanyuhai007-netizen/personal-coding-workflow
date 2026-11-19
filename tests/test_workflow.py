"""Contract tests through the installed public CLI, with synthetic repositories."""
import hashlib
import json
import os
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
        # Synthetic fixtures live under temp dirs; the production guard stays covered below.
        os.environ['PERSONAL_CODING_ALLOW_VOLATILE_RECORD'] = '1'
        self.addCleanup(os.environ.pop, 'PERSONAL_CODING_ALLOW_VOLATILE_RECORD', None)
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
        self.contract = self.root / 'acceptance.md'
        self.contract.write_text('Local fixture behavior must be checked.\n')

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
        for name in ('tdd', 'code-review', 'grilling', 'research', 'diagnosing-bugs', 'modern-web-guidance', 'vercel-react-best-practices', 'ui-taste-loop', 'frontend-design'):
            source = self.root / (name + '.md')
            source.write_text('Synthetic ' + name + ' source.\n')
            sources[name] = str(source)
        path.write_text(json.dumps({'component_sources': sources, 'task_id': 'fixture-task', 'goal': 'Exercise public contract',
                                    'facts': facts, 'max_attempts': 3,
                                    'conditions': [{'id': 'local', 'source': str(self.contract),
                                                    'locator': 'line 1', 'requirement': 'Local fixture behavior must be checked.',
                                                    'target': 'local fixture'}]}))
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


    def test_visual_only_work_has_direction_build_and_final_visual_gate(self):
        result = self.plan(ui=True, visual_change=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        stages = {s['id']: s for s in self.state()['stages']}
        self.assertIn('visual-build', stages)
        self.assertNotIn('document', stages)
        self.assertIn('visual-direction', stages['visual-build']['depends_on'])
        self.assertIn('web', stages['visual-direction']['depends_on'])
        self.assertIn('visual-review', stages['verify']['depends_on'])
        self.assertEqual(stages['visual-review']['components'], ['ui-taste-loop'])
        self.assertEqual(stages['visual-review']['scope'], 'tree')
        self.assertTrue(stages['visual-review']['independent'])

    def test_visual_completion_and_behavior_paths_keep_visual_review(self):
        for flags in ({'implementation_complete': True, 'existing_implementation': True},
                      {'behavior_change': True}, {}):
            with self.subTest(flags=flags):
                self.record = self.root / ('task-' + str(len(list(self.root.glob('task-*.json')))) + '.json')
                result = self.plan(ui=True, visual_change=True, **flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                stages = {s['id']: s for s in self.state()['stages']}
                self.assertIn('visual-review', stages['verify']['depends_on'])
                self.assertIn('visual-direction', stages['visual-review']['depends_on'])
                if flags.get('behavior_change'):
                    self.assertIn('implement', stages['visual-review']['depends_on'])
                else:
                    self.assertIn('visual-build', stages['visual-review']['depends_on'])

    def test_logic_only_ui_does_not_start_taste_loop(self):
        result = self.plan(ui=True, behavior_change=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(s['id'].startswith('visual-') for s in self.state()['stages']))

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
        if stage in ('standards', 'spec-review', 'close') and not self.state().get('acceptance'):
            self.assertEqual(self.accept().returncode, 0)
        path = self.make_receipt(stage, obligation, **options)
        return self.cli('stage-complete', self.record, '--stage', stage, '--receipt', path)

    def accept(self, rows=None):
        raw = self.root / 'observation.txt'
        raw.write_text('Observed fixture operation returns expected result locally.\n')
        rows = rows if rows is not None else [{'id': 'local', 'status': 'pass',
                'behavior': 'Run fixture operation', 'target': 'local fixture',
                'observation': 'Returned expected fixture result', 'evidence': [str(raw)]}]
        report = self.root / 'acceptance-report.json'
        report.write_text(json.dumps(rows))
        return self.cli('acceptance', self.record, '--report', report)

    def test_green_stages_do_not_replace_missing_original_acceptance(self):
        self.assertEqual(self.plan().returncode, 0)
        for stage in ('preflight', 'document', 'verify', 'close'):
            receipt = self.make_receipt(stage)
            self.assertEqual(self.cli('stage-complete', self.record, '--stage', stage,
                                     '--receipt', receipt).returncode, 0)
        # Every stage and captured check passed, but the original required behavior is unverified.
        result = self.cli('finish', self.record)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('local', result.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')

    def test_unknown_original_environment_cannot_be_replaced_by_neighbor(self):
        self.assertEqual(self.plan().returncode, 0)
        self.assertEqual(self.accept([{'id': 'local', 'status': 'unknown',
            'next_action': 'Replay original operation in local fixture'}]).returncode, 0)
        self.assertIn('Replay original', self.cli('finish', self.record).stderr)
        result = self.accept([{'id': 'local', 'status': 'pass', 'behavior': 'Run operation',
            'target': 'neighbor fixture', 'observation': 'OK', 'evidence': ['observation.txt']}])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('target differs', result.stderr)

    def test_one_passing_condition_does_not_cover_required_production_replay(self):
        self.assertEqual(self.plan().returncode, 0)
        path = self.root / 'facts.json'
        facts = json.loads(path.read_text())
        facts['conditions'].append({'id': 'original-webview', 'source': str(self.contract),
            'locator': 'original issue / required environment', 'requirement': 'Replay original cancellation',
            'target': 'production original webview'})
        path.write_text(json.dumps(facts))
        self.assertEqual(self.cli('plan', '--facts', path, '--record', self.record,
            '--reason', 'Original issue requires production webview replay as well as local checks').returncode, 0)
        for stage in ('preflight', 'document', 'verify', 'close'):
            self.assertEqual(self.complete(stage).returncode, 0)
        result = self.cli('finish', self.record)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('original-webview: unverified', result.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')

    def test_acceptance_changes_invalidate_review_and_sources_require_explicit_revision(self):
        self.assertEqual(self.plan(intent='review').returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('standards', 'code-review', reviewer='reviewer-a').returncode, 0)
        self.assertEqual(self.complete('spec-review', 'code-review', reviewer='reviewer-b').returncode, 0)
        self.assertEqual(self.complete('close').returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        self.assertEqual(self.accept([{'id': 'local', 'status': 'unknown',
                                     'next_action': 'Recheck contradicted observation'}]).returncode, 0)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')
        self.assertEqual(json.loads(self.cli('next', self.record, '--json').stdout)['id'], 'standards')
        self.assertEqual(len(self.state()['acceptance_history']), 1)
        self.contract.write_text('Changed original environment requirement.\n')
        self.assertNotEqual(self.accept().returncode, 0)
        self.assertIn('changed evidence', self.cli('finish', self.record).stderr)
        self.assertEqual(self.plan(intent='review').returncode, 2)
        revised = self.cli('plan', '--facts', self.root / 'facts.json', '--record', self.record,
                           '--reason', 'Original environment contract changed; recheck projected conditions')
        self.assertEqual(revised.returncode, 0, revised.stderr)
        self.assertEqual(json.loads(self.cli('next', self.record, '--json').stdout)['id'], 'preflight')

    def test_legacy_review_receipt_must_bind_new_acceptance_inputs_after_migration(self):
        self.assertEqual(self.plan(intent='review').returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.accept().returncode, 0)
        path = self.make_receipt('standards', 'code-review', reviewer='legacy-reviewer')
        legacy = json.loads(path.read_text())
        # Synthetic v0.3.0 receipt shape, which predates acceptance identity fields.
        legacy['input_identity'].pop('acceptance')
        legacy['input_identity'].pop('conditions')
        path.write_text(json.dumps(legacy))
        result = self.cli('stage-complete', self.record, '--stage', 'standards', '--receipt', path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('acceptance identity', result.stderr)

    def test_acceptance_evidence_and_code_tree_remain_current_after_finish(self):
        self.test_short_document_path_recovers_across_processes_and_finishes()
        (self.root / 'observation.txt').write_text('Contradicting new observation.\n')
        result = self.cli('finish', self.record)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('changed evidence', result.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')
        self.assertEqual(self.accept().returncode, 0)
        (self.repo / 'new-untracked.txt').write_text('New deliverable invalidates observations.\n')
        self.assertIn('Stale acceptance', self.cli('finish', self.record).stderr)

    def test_missing_duplicate_and_unknown_conditions_are_rejected(self):
        self.assertEqual(self.plan().returncode, 0)
        facts_path = self.root / 'facts.json'
        facts = json.loads(facts_path.read_text())
        facts['conditions'] = []
        facts_path.write_text(json.dumps(facts))
        self.assertIn('conditions are required', self.cli('plan', '--facts', facts_path,
                      '--record', self.root / 'other.json').stderr)
        self.assertNotEqual(self.accept([{'id': 'wrong', 'status': 'unknown', 'next_action': 'Recheck'}]).returncode, 0)
        row = {'id': 'local', 'status': 'unknown', 'next_action': 'Recheck'}
        self.assertNotEqual(self.accept([row, row]).returncode, 0)
        self.assertEqual(self.accept([]).returncode, 0)
        self.assertIn('local: unverified', self.cli('finish', self.record).stderr)

    def test_failed_acceptance_reports_actual_observation_and_remaining_action(self):
        self.assertEqual(self.plan().returncode, 0)
        (self.root / 'failed.log').write_text('fixture operation returned unexpected error code 7\n')
        result = self.accept([{'id': 'local', 'status': 'fail', 'behavior': 'Invoke fixture operation',
            'target': 'local fixture', 'observation': 'Returned unexpected error code 7',
            'evidence': ['failed.log'], 'next_action': 'Fix error 7 and rerun original operation'}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Returned unexpected error code 7', result.stdout)
        self.assertIn('failed.log', result.stdout)
        self.assertIn('Fix error 7', self.cli('finish', self.record).stderr)

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
        # Independent fact verification is an internal procedure, not an external skill slot.
        self.assertEqual({s['id']: s for s in self.state()['stages']}['fact-review']['components'], [])
        self.assertIn('document', [s['id'] for s in self.state()['stages']])
        self.assertTrue(all(s['status'] == 'needs_verification' for s in self.state()['stages']
                            if s['status'] == 'passed'))
        self.assertEqual(json.loads(self.cli('next', self.record, '--json').stdout)['id'], 'preflight')
        self.assertEqual(len(self.state()['revisions']), 2)

    def cli_env(self, env, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=self.repo,
                              capture_output=True, text=True, env=env)

    def test_purged_record_locations_are_refused_at_plan_and_finish(self):
        purged = {key: value for key, value in os.environ.items()
                  if key != 'PERSONAL_CODING_ALLOW_VOLATILE_RECORD'}
        path = self.root / 'facts.json'
        path.write_text(json.dumps({'task_id': 'fixture-task', 'goal': 'Exercise public contract',
                                    'facts': {'intent': {'value': 'implement', 'evidence': 'synthetic'}},
                                    'conditions': [], 'max_attempts': 1}))
        result = self.cli_env(purged, 'plan', '--facts', path, '--record', self.record)
        self.assertEqual(result.returncode, 2)
        self.assertIn('purged', result.stderr)
        self.assertFalse(self.record.exists())
        self.assertEqual(self.plan().returncode, 0)
        result = self.cli_env(purged, 'finish', self.record)
        self.assertEqual(result.returncode, 2)
        self.assertIn('purged', result.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')

    def test_output_obligation_receipts_no_longer_need_event_files(self):
        self.assertEqual(self.plan().returncode, 0)
        proof = self.root / 'proof.md'
        proof.write_text('Synthetic stage completed without any hand-written event JSON.\n')
        out = self.root / 'preflight-no-event.json'
        result = self.cli('stage-receipt', self.record, '--stage', 'preflight', '--obligation', 'output',
                          '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic pc contract',
                          '--artifact', proof, '--input', self.root / 'facts.json', '--out', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(out.read_text())['observed_event_ref'])
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'preflight',
                                  '--receipt', out).returncode, 0)

    def test_component_receipts_auto_match_the_latest_registered_event(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        # Dedicated files: overwriting a hash-bound artifact of a passed stage would
        # invalidate it, which is exactly the guard tested elsewhere.
        proof = self.root / 'red-green.md'
        proof.write_text('Synthetic red-green execution trace.\n')
        source = self.root / 'tdd.md'
        source.write_text('Synthetic tdd source.\n')
        self.assertEqual(self.cli('component-event', self.record, '--stage', 'implement', '--obligation', 'tdd',
                                  '--mode', 'read', '--source', source, '--proof', proof,
                                  '--status', 'success').returncode, 0)
        out = self.root / 'implement-auto.json'
        result = self.cli('stage-receipt', self.record, '--stage', 'implement', '--obligation', 'tdd',
                          '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic pc contract',
                          '--source', source, '--artifact', proof, '--input', self.repo / 'app.txt', '--out', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(Path(json.loads(out.read_text())['observed_event_ref']['path']).read_text())
        self.assertEqual(event['component'], 'tdd')
        self.assertEqual(event['stage_id'], 'implement')
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'implement',
                                  '--receipt', out).returncode, 0)
        missing = self.cli('stage-receipt', self.record, '--stage', 'verify', '--obligation', 'tdd',
                           '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic pc contract',
                           '--source', source, '--artifact', proof, '--input', self.repo / 'app.txt',
                           '--out', self.root / 'no-event.json')
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('No registered success event', missing.stderr)


if __name__ == '__main__':
    unittest.main()
