"""Contract tests through the installed public CLI, with synthetic repositories."""
import hashlib
import json
import os
from pathlib import Path
import shutil
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
        self.script = SCRIPT  # Tests with copied rule sets point this at the copy's CLI.
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
        return subprocess.run([sys.executable, str(self.script), *map(str, args)], cwd=self.repo,
                              capture_output=True, text=True)

    def plan(self, intent='implement', extra_sources=(), **features):
        facts = {'intent': {'value': intent, 'evidence': 'synthetic user request'}}
        facts.update({k: {'value': v, 'evidence': 'synthetic fixture contract'} for k, v in features.items()})
        path = self.root / 'facts.json'
        sources = {}
        names = ('tdd', 'code-review', 'grilling', 'research', 'diagnosing-bugs', 'modern-web-guidance',
                 'vercel-react-best-practices', 'ui-taste-loop', 'frontend-design', 'web-gui-tester')
        for name in names + tuple(extra_sources):
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
        self.assertTrue({'modern-web-guidance', 'vercel-react-best-practices', 'tdd', 'code-review', 'web-gui-tester'} <= required)
        result = self.cli('finish', self.record)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preflight', result.stderr)
        result = self.cli('next', self.record, '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['id'], 'preflight')
        self.assertNotEqual(self.state()['status'], 'VERIFIED')

    def test_interaction_stage_gates_on_fact_and_wires_dependencies(self):
        result = self.plan(behavior_change=True, ui=True, visual_change=True, interaction=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        stages = {s['id']: s for s in self.state()['stages']}
        self.assertEqual(stages['interaction-verify']['required_obligations'], ['web-gui-tester'])
        self.assertIn('interaction-verify', stages['verify']['depends_on'])
        self.assertIn('interaction-verify', stages['visual-review']['depends_on'])
        finish = self.cli('finish', self.record)
        self.assertNotEqual(finish.returncode, 0)
        self.assertIn('interaction-verify', finish.stderr)

    def test_interaction_stage_absent_without_fact(self):
        result = self.plan(behavior_change=True, ui=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        ids = {s['id'] for s in self.state()['stages']}
        self.assertNotIn('interaction-verify', ids)

    def doctor_result(self, name, code=0):
        out = self.root / name
        statement = 'print("doctor ok")' if code == 0 else 'raise SystemExit(%d)' % code
        status = self.cli('run', '--out', out, '--', sys.executable, '-c', statement).returncode
        self.assertEqual(status, code)
        return out / 'result.json'

    def test_doctor_check_gates_interaction_verify_receipts(self):
        self.assertEqual(self.plan(behavior_change=True, interaction=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('implement', 'tdd').returncode, 0)
        # Screenshots bind the code tree, not the running instance; only a captured
        # doctor check proves the driven instance is the current workspace/code/port/data.
        result = self.complete('interaction-verify', 'web-gui-tester')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('doctor', result.stderr)
        failed = self.complete('interaction-verify', 'web-gui-tester',
                               doctor=self.doctor_result('doctor-failing', code=3))
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('Failed or stale verification check', failed.stderr)
        passed = self.complete('interaction-verify', 'web-gui-tester',
                               doctor=self.doctor_result('doctor-ok'))
        self.assertEqual(passed.returncode, 0, passed.stderr)

    def test_interaction_verify_degrades_without_doctor_and_stays_unmet(self):
        # A project contract without a Doctor field degrades like a missing component:
        # the limitation is recorded, the interaction conditions stay unverified.
        self.assertEqual(self.plan(behavior_change=True, interaction=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('implement', 'tdd').returncode, 0)
        result = self.complete('interaction-verify', 'web-gui-tester', mode='degraded')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Degraded', result.stderr)
        finish = self.cli('finish', self.record)
        self.assertNotEqual(finish.returncode, 0)
        self.assertIn('interaction-verify', finish.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')

    def test_doctor_gate_failures_block_after_budget_with_single_resume(self):
        # Persistent doctor drift exhausts the stage budget into blocked, and the
        # stage gets exactly one bounded resume cycle, never unlimited retries.
        self.assertEqual(self.plan(behavior_change=True, interaction=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('implement', 'tdd').returncode, 0)
        drift = self.doctor_result('doctor-drift', code=3)
        for _ in range(3):
            self.assertNotEqual(self.complete('interaction-verify', 'web-gui-tester', doctor=drift).returncode, 0)
        self.assertIn('budget exhausted', self.complete('interaction-verify', 'web-gui-tester', doctor=drift).stderr)
        stage = {s['id']: s for s in self.state()['stages']}['interaction-verify']
        self.assertEqual(stage['status'], 'blocked')
        self.assertEqual(self.state()['status'], 'BLOCKED')
        recovery = self.root / 'doctor-recovery.md'
        recovery.write_text('Doctor drift fixed once; new doctor run captured.\n')
        resumed = self.cli('stage-resume', self.record, '--stage', 'interaction-verify',
                           '--reason', 'Doctor drift fixed once', '--proof', recovery)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        for _ in range(3):
            self.assertNotEqual(self.complete('interaction-verify', 'web-gui-tester', doctor=drift).returncode, 0)
        second = self.cli('stage-resume', self.record, '--stage', 'interaction-verify',
                          '--reason', 'Another doctor attempt', '--proof', recovery)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('single bounded resume cycle', second.stderr)

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
        if options.get('doctor'):
            args += ['--doctor-check', options['doctor']]
        if obligation != 'output':
            args += ['--source', source]
        if options.get('reviewer'):
            args += ['--independent', '--reviewer-id', options['reviewer']]
            if stage in ('standards', 'spec-review'):
                review = options.get('review', out.with_name(out.stem + '-review.json'))
                if 'review' not in options:
                    result = self.cli('review-input', self.record, '--stage', stage)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    review.write_text(json.dumps({'reviewed': json.loads(result.stdout),
                                                  'reviewer_id': options['reviewer'], 'verdict': 'pass',
                                                  'assessment': 'Fixture evidence reviewed independently.',
                                                  **options.get('review_details', {})}))
                args += ['--review', review]
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

    def test_changed_acceptance_cannot_be_resigned_with_old_review(self):
        self.assertEqual(self.plan(intent='review').returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertIn('Record current acceptance', self.cli('review-input', self.record, '--stage', 'standards').stderr)
        self.assertEqual(self.accept().returncode, 0)
        self.assertIn('Load and record code-review', self.cli('review-input', self.record, '--stage', 'standards').stderr)
        old = self.make_receipt('standards', 'code-review', reviewer='reviewer-a')
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'standards', '--receipt', old).returncode, 0)
        row = self.state()['acceptance']['observations'][0]
        row['observation'] = 'Returned a reformatted fixture result'
        row['evidence'] = [row['evidence'][0]['path']]
        self.assertEqual(self.accept([row]).returncode, 0)
        old_report = Path(json.loads(old.read_text())['review']['path'])
        result = self.complete('standards', 'code-review', reviewer='reviewer-a', review=old_report)
        self.assertIn('does not bind current review inputs', result.stderr)
        result = self.complete('standards', 'code-review', reviewer='reviewer-c')
        self.assertIn('original reviewer', result.stderr)
        self.assertEqual(self.complete('standards', 'code-review', reviewer='reviewer-a').returncode, 0)
        row['observation'] = 'Returned the final fixture result'
        self.assertEqual(self.accept([row]).returncode, 0)
        result = self.complete('standards', 'code-review', reviewer='reviewer-c',
                               review_details={'scope': 'full', 'replacement_reason': 'Original context expired'})
        self.assertEqual(result.returncode, 0, result.stderr)
        malformed = self.root / 'malformed-review.json'
        malformed.write_text('[]')
        result = self.complete('spec-review', 'code-review', reviewer='reviewer-b', review=malformed)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Reviewer report must be a JSON object', result.stderr)

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

    def numbers_report(self, numbers, log, status='pass'):
        raw = self.root / 'observation.txt'
        raw.write_text('Observed fixture operation returns expected result locally.\n')
        row = {'id': 'local', 'status': status, 'behavior': 'Run fixture checks',
               'target': 'local fixture', 'observation': 'Sealed sample summarized',
               'evidence': [str(raw)], 'numbers': numbers}
        if status == 'unknown':
            row['next_action'] = 'Recheck against the sealed sample'
        report = self.root / ('acceptance-numbers-' + str(len(list(self.root.glob('acceptance-numbers-*.json')))) + '.json')
        report.write_text(json.dumps([row]))
        return self.cli('acceptance', self.record, '--report', report)

    def complete_before_numbers(self):
        self.assertEqual(self.plan().returncode, 0)
        for stage in ('preflight', 'document', 'verify'):
            self.assertEqual(self.complete(stage).returncode, 0)

    def test_recomputable_number_claims_keep_observation_pass(self):
        self.complete_before_numbers()
        log = self.root / 'checks.log'
        log.write_text('latency 2.9\nlatency 3.7\nlatency 4.1\n' + 'ok\n' * 21)
        result = self.numbers_report([
            {'claim': 3.7, 'source': 'checks.log', 'pattern': r'latency ([0-9.]+)', 'compute': 'median'},
            {'claim': 21, 'source': 'checks.log', 'pattern': r'\bok\b', 'compute': 'count'},
            {'claim': 87.5, 'kind': 'approx', 'tolerance': 0.1, 'source': 'checks.log',
             'numerator': r'\bok\b', 'denominator': r'\bok\b|\blatency\b', 'compute': 'ratio', 'scale': 100},
        ], log)
        self.assertEqual(result.returncode, 0, result.stderr)
        observation = self.state()['acceptance']['observations'][0]
        self.assertEqual(observation['status'], 'pass')
        self.assertTrue(all(item['verdict'] for item in observation['numbers']))
        self.assertEqual(self.complete('close').returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        self.assertEqual(self.state()['status'], 'VERIFIED')

    def test_number_claims_that_do_not_recompute_downgrade_to_unknown(self):
        self.complete_before_numbers()
        log = self.root / 'baseline.log'
        log.write_text('sample 8.2\nsample 7.4\nsample 9.0\n')
        result = self.numbers_report([
            {'claim': 7.4, 'source': 'baseline.log', 'pattern': r'sample ([0-9.]+)', 'compute': 'median'},
            {'claim': 76.4, 'kind': 'approx', 'tolerance': 0.5, 'source': 'baseline.log',
             'numerator': r'sample 8', 'denominator': r'sample', 'compute': 'ratio', 'scale': 100},
        ], log)
        self.assertEqual(result.returncode, 0, result.stderr)
        observation = self.state()['acceptance']['observations'][0]
        self.assertEqual(observation['status'], 'unknown')
        self.assertIn('do not recompute', observation['next_action'])
        self.assertEqual(self.complete('close').returncode, 0)
        finish = self.cli('finish', self.record)
        self.assertNotEqual(finish.returncode, 0)
        self.assertIn('Number claims do not recompute', finish.stderr)
        self.assertIn('Claimed 7.4 but recomputed 8.2', finish.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')
        # A declared-unknown row keeps its own next_action; failed claims only add detail.
        again = self.numbers_report([{'claim': 99, 'source': 'baseline.log', 'pattern': 'sample', 'compute': 'count'}],
                                    log, status='unknown')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn('Recheck against the sealed sample', self.cli('finish', self.record).stderr)

    def test_number_claim_sources_remain_hash_bound_after_capture(self):
        self.complete_before_numbers()
        log = self.root / 'checks.log'
        log.write_text('ok\n' * 21)
        result = self.numbers_report(
            [{'claim': 21, 'source': 'checks.log', 'pattern': r'\bok\b', 'compute': 'count'}], log)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.complete('close').returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        # The number source is separate from the observation evidence list; tampering only it must still fail closure.
        log.write_text('ok\n' * 20 + 'FAIL\n')
        finish = self.cli('finish', self.record)
        self.assertNotEqual(finish.returncode, 0)
        self.assertIn('changed evidence', finish.stderr)

    def test_malformed_number_claims_are_rejected(self):
        self.assertEqual(self.plan().returncode, 0)
        log = self.root / 'checks.log'
        log.write_text('ok\n')
        base = {'source': 'checks.log'}
        cases = [
            {'claim': 1, 'compute': 'median'},
            {'claim': 1, 'pattern': 'ok', 'kind': 'approx'},
            {'claim': 1, 'pattern': 'ok', 'tolerance': 0.5},
            {'claim': 'three', 'pattern': 'ok'},
            {'claim': 1, 'pattern': 'ok', 'compute': 'median', 'scale': 2},
            {'claim': 1, 'pattern': 'ok', 'compute': 'ratio'},
            {'claim': 1, 'pattern': 'ok', 'compute': 'wow'},
            {'claim': 1, 'pattern': 'ok', 'kind': 'rough'},
        ]
        for numbers in cases + [[]]:
            with self.subTest(numbers=numbers):
                result = self.numbers_report({**base, **numbers} if isinstance(numbers, dict) else numbers, log)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ERROR', result.stderr)

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
        self.assertEqual(self.cli(*args, '--result', 'applied', '--proof', applied).returncode, 0)
        self.assertNotEqual(self.cli(*args, '--result', 'not_applied', '--proof', applied).returncode, 0)
        self.assertEqual(self.state()['status'], 'VERIFIED')

    def test_late_operation_tracks_follow_up_after_finish(self):
        self.assertEqual(self.plan().returncode, 0)
        for stage in ('preflight', 'document', 'verify', 'close'):
            self.assertEqual(self.complete(stage).returncode, 0)
        follow_ups = self.root / 'follow-ups.json'
        follow_ups.write_text(json.dumps([{'id': 'fixture', 'summary': 'Verify in another environment',
                                          'ticket': 'TODO', 'operation_id': 'ticket-fixture'}]))
        result = self.cli('finish', self.record, '--follow-ups', follow_ups)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('untracked', result.stdout)
        args = ['operation', self.record, '--stage', 'close', '--operation-id', 'ticket-fixture',
                '--result', 'applied', '--late']
        self.assertNotEqual(self.cli(*args).returncode, 0)
        proof = self.root / 'ticket.md'
        proof.write_text('Independent observation of an already recorded issue.')
        result = self.cli(*args, '--proof', proof)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.state()['operations']['ticket-fixture']['late'])
        self.assertEqual(self.state()['status'], 'VERIFIED')
        self.assertNotEqual(self.cli(*args, '--proof', proof).returncode, 0)
        self.assertIn('operation ticket-fixture', self.cli('finish', self.record).stdout)
        proof.write_text('Changed observation')
        self.assertIn('untracked', self.cli('finish', self.record).stdout)

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
        return subprocess.run([sys.executable, str(self.script), *map(str, args)], cwd=self.repo,
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

    def preflight_receipt(self, name, inputs=(), pins=()):
        """Preflight receipt with caller-chosen live and pinned inputs."""
        proof = self.root / (name + '-proof.md')
        proof.write_text('Synthetic preflight trace over fixture inputs.\n')
        out = self.root / (name + '.json')
        args = ['stage-receipt', self.record, '--stage', 'preflight', '--obligation', 'output',
                '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic pc contract',
                '--artifact', proof, '--out', out]
        for value in inputs:
            args += ['--input', value]
        for value in pins:
            args += ['--pin-input', value]
        self.assertEqual(self.cli(*args).returncode, 0)
        return out

    def test_pinned_inputs_survive_intended_modification_and_tampering_fails(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        out = self.preflight_receipt('preflight-pinned', pins=[self.repo / 'app.txt'])
        receipt = json.loads(out.read_text())
        (origin, snapshot), = receipt['input_identity']['pinned'].items()
        self.assertEqual(origin, str((self.repo / 'app.txt').resolve()))
        self.assertEqual(Path(snapshot['path']).parent.name, 'preflight-pinned.inputs')
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'preflight',
                                  '--receipt', out).returncode, 0)
        # The task's own planned edit no longer demotes the early receipt.
        (self.repo / 'app.txt').write_text('intended task modification\n')
        self.assertEqual(self.cli('next', self.record, '--json').returncode, 0)
        self.assertEqual(self.state()['stages'][0]['status'], 'passed')
        # The sealed bytes are the evidence; tampering with the snapshot fails.
        Path(snapshot['path']).write_text('tampered\n')
        self.assertEqual(self.cli('next', self.record, '--json').returncode, 0)
        self.assertEqual(self.state()['stages'][0]['status'], 'needs_verification')

    def test_pin_input_is_rejected_for_tree_scopes_and_double_binding(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        (self.root / 'proof.md').write_text('Synthetic trace.\n')
        result = self.cli('stage-receipt', self.record, '--stage', 'verify', '--obligation', 'output',
                          '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic',
                          '--artifact', self.root / 'proof.md', '--input', self.repo / 'app.txt',
                          '--pin-input', self.root / 'facts.json', '--out', self.root / 'verify-pin.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Tree-scoped', result.stderr)
        result = self.cli('stage-receipt', self.record, '--stage', 'preflight', '--obligation', 'output',
                          '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic',
                          '--artifact', self.root / 'proof.md', '--input', self.repo / 'app.txt',
                          '--pin-input', self.repo / 'app.txt', '--out', self.root / 'double.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not both', result.stderr)
        self.assertFalse((self.root / 'double.json').exists())

    def test_receipt_refile_rebinds_hashes_and_promotes_demoted_dependents(self):
        self.assertEqual(self.plan(unfamiliar_api=True).returncode, 0)
        self.assertIn('research', {s['id'] for s in self.state()['stages']})
        preflight = self.preflight_receipt('preflight-live', inputs=[self.repo / 'app.txt'])
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'preflight',
                                  '--receipt', preflight).returncode, 0)
        research = self.make_receipt('research', 'research')
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'research',
                                  '--receipt', research).returncode, 0)
        # A semantics-neutral edit invalidates preflight (live input) and cascades to research.
        (self.repo / 'app.txt').write_text('reflowed fixture\n')
        self.assertEqual(self.cli('next', self.record, '--json').returncode, 0)
        statuses = {s['id']: s['status'] for s in self.state()['stages']}
        self.assertEqual(statuses['preflight'], 'needs_verification')
        self.assertEqual(statuses['research'], 'needs_verification')
        refiled = self.root / 'preflight-refiled.json'
        result = self.cli('receipt-refile', self.record, '--receipt', preflight, '--stage', 'preflight',
                          '--reason', 'comment reflow only; verified facts unchanged', '--out', refiled)
        self.assertEqual(result.returncode, 0, result.stderr)
        new_receipt, old_receipt = json.loads(refiled.read_text()), json.loads(preflight.read_text())
        self.assertEqual(new_receipt['refile']['changed_paths'], [str((self.repo / 'app.txt').resolve())])
        self.assertEqual(new_receipt['refile']['source_receipt']['sha256'],
                         hashlib.sha256(preflight.read_bytes()).hexdigest())
        for key in ('task_id', 'stage_id', 'obligation_id', 'mode', 'verification', 'adaptation',
                    'sources', 'artifacts', 'at'):
            self.assertEqual(new_receipt[key], old_receipt[key])
        completed = self.cli('stage-complete', self.record, '--stage', 'preflight', '--receipt', refiled)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        # The dependent stage revalidated mechanically; no manual receipt replay needed.
        statuses = {s['id']: s for s in self.state()['stages']}
        self.assertEqual(statuses['preflight']['status'], 'passed')
        self.assertEqual(statuses['research']['status'], 'passed')
        self.assertTrue(statuses['research'].get('revalidations'))
        self.assertTrue(statuses['research'].get('invalidation_history'))

    def test_receipt_refile_rejects_tree_bindings_missing_inputs_and_blank_reasons(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        check = self.root / 'verify-check'
        self.assertEqual(self.cli('run', '--out', check, '--', sys.executable, '-c',
                                  'print("fixture")').returncode, 0)
        verify_receipt = self.root / 'verify-1.json'
        result = self.cli('stage-receipt', self.record, '--stage', 'verify', '--obligation', 'output',
                          '--mode', 'read', '--verification', 'pass', '--adaptation', 'synthetic',
                          '--artifact', self.root / 'proof.md', '--input', self.repo / 'app.txt',
                          '--check', check / 'result.json', '--out', verify_receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        refile = self.cli('receipt-refile', self.record, '--receipt', verify_receipt, '--stage', 'verify',
                          '--reason', 'comment reflow', '--out', self.root / 'verify-2.json')
        self.assertNotEqual(refile.returncode, 0)
        self.assertIn('file-bound', refile.stderr)
        gone = self.preflight_receipt('preflight-gone', inputs=[self.repo / 'app.txt'])
        (self.repo / 'app.txt').unlink()
        missing = self.cli('receipt-refile', self.record, '--receipt', gone, '--stage', 'preflight',
                           '--reason', 'file removed', '--out', self.root / 'gone.json')
        self.assertNotEqual(missing.returncode, 0)
        blank = self.cli('receipt-refile', self.record,
                         '--receipt', self.state()['stages'][0]['receipts'][0], '--stage', 'preflight',
                         '--reason', '   ', '--out', self.root / 'blank.json')
        self.assertNotEqual(blank.returncode, 0)
        self.assertIn('reason', blank.stderr)

    def test_plan_revision_recheck_is_not_satisfied_by_mechanical_revalidation(self):
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        # Preflight binds only app.txt, so a goal-only revision leaves its hashes intact.
        preflight = self.preflight_receipt('preflight-goal', inputs=[self.repo / 'app.txt'])
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'preflight',
                                  '--receipt', preflight).returncode, 0)
        path = self.root / 'facts.json'
        facts = json.loads(path.read_text())
        facts['goal'] = 'Revised goal with the same facts'
        path.write_text(json.dumps(facts))
        revised = self.cli('plan', '--facts', path, '--record', self.record,
                           '--reason', 'User sharpened the goal wording')
        self.assertEqual(revised.returncode, 0, revised.stderr)
        self.assertEqual(self.state()['stages'][0]['status'], 'needs_verification')
        self.assertTrue(self.state()['stages'][0]['recheck_required'])
        # Repeated mechanical revalidation must not silently satisfy the recheck.
        self.assertEqual(self.cli('next', self.record, '--json').returncode, 0)
        self.assertEqual(self.state()['stages'][0]['status'], 'needs_verification')
        # Explicit re-verification clears the recheck flag.
        refiled = self.root / 'preflight-goal-2.json'
        self.assertEqual(self.cli('receipt-refile', self.record, '--receipt', preflight,
                                  '--stage', 'preflight', '--reason', 'goal wording only',
                                  '--out', refiled).returncode, 0)
        self.assertEqual(self.cli('stage-complete', self.record, '--stage', 'preflight',
                                  '--receipt', refiled).returncode, 0)
        self.assertNotIn('recheck_required', self.state()['stages'][0])

    def test_stage_complete_records_declared_costs_and_rejects_malformed_ones(self):
        self.assertEqual(self.plan().returncode, 0)
        preflight = self.make_receipt('preflight')
        cost = self.root / 'cost.json'
        usage = {
            'last_request': {'tokens': 200, 'basis': 'last fixture request'},
            'main_total': {'tokens': 1100, 'basis': 'fixture sum including cached input'},
            'child_total': {'tokens': 100, 'basis': 'archived fixture child token counts'},
        }
        cost.write_text(json.dumps({'tokens': 1200, 'duration_ms': 3400,
                                   'basis': 'fixture measurement sources', **usage}))
        result = self.cli('stage-complete', self.record, '--stage', 'preflight',
                          '--receipt', preflight, '--cost', cost)
        self.assertEqual(result.returncode, 0, result.stderr)
        stage = self.state()['stages'][0]
        self.assertEqual(stage['costs'][-1]['tokens'], 1200)
        self.assertEqual(stage['costs'][-1]['basis'], 'fixture measurement sources')
        for key, metric in usage.items():
            self.assertEqual(stage['costs'][-1][key], metric)
        self.assertIn('at', stage['costs'][-1])
        self.assertTrue(stage['completions'])
        for bad in ({'tokens': -5, 'basis': 'x'}, {'tokens': 5}, {'tokens': 'many', 'basis': 'x'},
                    {'main_total': {'tokens': 10}, 'basis': 'root basis only'}):
            with self.subTest(bad=bad):
                path = self.root / ('bad-cost-' + str(len(list(self.root.glob('bad-cost-*.json')))) + '.json')
                path.write_text(json.dumps(bad))
                document = self.make_receipt('document')
                failed = self.cli('stage-complete', self.record, '--stage', 'document',
                                  '--receipt', document, '--cost', path)
                self.assertNotEqual(failed.returncode, 0)
                self.assertIn('Cost', failed.stderr)
                stage = {s['id']: s for s in self.state()['stages']}['document']
                self.assertFalse(stage.get('costs'))
                self.assertEqual(stage['attempts'], 0)

    def assert_interrogate_optional_wiring(self, stage):
        """Production-rule verify slot: interrogate is the sole component and it is optional."""
        self.assertEqual(stage['components'], ['interrogate'])
        self.assertEqual(stage['required_obligations'], [])
        self.assertEqual(stage['optional_obligations'], ['interrogate'])

    def test_default_ruleset_keeps_components_required_except_verify(self):
        # The production rule set wires exactly one optional component (interrogate on
        # verify); every other stage keeps all components required, as before.
        result = self.plan(behavior_change=True, ui=True, react=True, interaction=True,
                           nontrivial=True, unfamiliar_api=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        stages = self.state()['stages']
        self.assertTrue(stages)
        for stage in stages:
            if stage['id'] == 'verify':
                self.assert_interrogate_optional_wiring(stage)
            else:
                self.assertEqual(stage['required_obligations'], stage['components'])
                self.assertEqual(stage['optional_obligations'], [])

    def test_verify_optional_interrogate_slot_from_production_rules(self):
        # Production rules wire interrogate as verify's optional obligation: the slot
        # shows up in plan/next, and skipping it opens no obligation gap.
        self.assertEqual(self.plan().returncode, 0)
        verify = {s['id']: s for s in self.state()['stages']}['verify']
        self.assert_interrogate_optional_wiring(verify)
        self.assertEqual(self.complete('preflight').returncode, 0)
        self.assertEqual(self.complete('document').returncode, 0)
        result = self.cli('next', self.record, '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['id'], 'verify')
        self.assertEqual(json.loads(result.stdout)['optional_obligations'], ['interrogate'])
        # An output receipt alone completes verify: no interrogate receipt blocks nothing.
        self.assertEqual(self.complete('verify').returncode, 0)
        self.assertEqual({s['id']: s for s in self.state()['stages']}['verify']['status'], 'passed')


    def optional_scripts(self, stage_id='research', required=('research', 'diagnosing-bugs'), optional=('grilling',)):
        """Copied rule set declaring optional components on a stage; production rule bytes stay untouched."""
        scripts = Path(tempfile.mkdtemp(prefix='optional-rules-', dir=self.root)) / 'scripts'
        shutil.copytree(SCRIPT.parent, scripts, ignore=shutil.ignore_patterns('__pycache__'))
        rules = json.loads((scripts / 'workflow_rules.json').read_text())
        stage = next(s for s in rules['stages'] if s['id'] == stage_id)
        stage['components'] = list(required) + list(optional)
        stage['optional_components'] = list(optional)
        (scripts / 'workflow_rules.json').write_text(json.dumps(rules, ensure_ascii=False, indent=2) + '\n')
        return scripts / 'evidence.py'

    def plan_optional_research(self):
        self.script = self.optional_scripts()
        self.assertEqual(self.plan(unfamiliar_api=True).returncode, 0)
        research = {s['id']: s for s in self.state()['stages']}['research']
        self.assertEqual(research['components'], ['research', 'diagnosing-bugs', 'grilling'])
        self.assertEqual(research['required_obligations'], ['research', 'diagnosing-bugs'])
        self.assertEqual(research['optional_obligations'], ['grilling'])
        self.assertEqual(self.complete('preflight').returncode, 0)

    def test_optional_component_absence_leaves_no_obligation_gap(self):
        # Not executing an optional component is a valid outcome; it opens no receipt gap.
        self.plan_optional_research()
        result = self.cli('stage-complete', self.record, '--stage', 'research',
                          '--receipt', self.make_receipt('research', 'research'),
                          '--receipt', self.make_receipt('research', 'diagnosing-bugs'))
        self.assertEqual(result.returncode, 0, result.stderr)
        research = {s['id']: s for s in self.state()['stages']}['research']
        self.assertEqual(research['status'], 'passed')

    def test_optional_component_receipt_passes_full_verification(self):
        self.plan_optional_research()
        result = self.cli('stage-complete', self.record, '--stage', 'research',
                          '--receipt', self.make_receipt('research', 'research'),
                          '--receipt', self.make_receipt('research', 'diagnosing-bugs'),
                          '--receipt', self.make_receipt('research', 'grilling'))
        self.assertEqual(result.returncode, 0, result.stderr)
        research = {s['id']: s for s in self.state()['stages']}['research']
        self.assertEqual(research['status'], 'passed')

    def test_missing_required_receipt_still_rejected_alongside_optional(self):
        self.plan_optional_research()
        for missing in ('research', 'diagnosing-bugs'):
            with self.subTest(missing=missing):
                present = [o for o in ('research', 'diagnosing-bugs') if o != missing]
                result = self.cli('stage-complete', self.record, '--stage', 'research',
                                  '--receipt', self.make_receipt('research', present[0]),
                                  '--receipt', self.make_receipt('research', 'grilling'))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('obligation set mismatch', result.stderr)
                research = {s['id']: s for s in self.state()['stages']}['research']
                self.assertNotEqual(research['status'], 'passed')

    def test_receipt_outside_declared_obligations_is_rejected(self):
        self.plan_optional_research()
        stranger = self.make_receipt('research', 'grilling')
        value = json.loads(stranger.read_text())
        value['obligation_id'] = 'tdd'
        stranger.write_text(json.dumps(value))
        result = self.cli('stage-complete', self.record, '--stage', 'research',
                          '--receipt', self.make_receipt('research', 'research'),
                          '--receipt', self.make_receipt('research', 'diagnosing-bugs'),
                          '--receipt', stranger)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected obligation', result.stderr)

    def test_duplicate_optional_receipt_is_rejected(self):
        self.plan_optional_research()
        result = self.cli('stage-complete', self.record, '--stage', 'research',
                          '--receipt', self.make_receipt('research', 'research'),
                          '--receipt', self.make_receipt('research', 'diagnosing-bugs'),
                          '--receipt', self.make_receipt('research', 'grilling'),
                          '--receipt', self.make_receipt('research', 'grilling'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('obligation set mismatch', result.stderr)

    def test_degraded_optional_receipt_satisfies_no_obligation(self):
        # Skipping an optional component means no receipt at all; a degraded receipt satisfies nothing.
        self.plan_optional_research()
        result = self.cli('stage-complete', self.record, '--stage', 'research',
                          '--receipt', self.make_receipt('research', 'research'),
                          '--receipt', self.make_receipt('research', 'diagnosing-bugs'),
                          '--receipt', self.make_receipt('research', 'grilling', mode='degraded'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Degraded', result.stderr)
        research = {s['id']: s for s in self.state()['stages']}['research']
        self.assertNotEqual(research['status'], 'passed')

    def test_optional_receipt_supports_manual_events_and_refile(self):
        # The optional obligation stays usable through component-event and receipt-refile.
        self.plan_optional_research()
        grilling = self.make_receipt('research', 'grilling')
        result = self.cli('stage-complete', self.record, '--stage', 'research',
                          '--receipt', self.make_receipt('research', 'research'),
                          '--receipt', self.make_receipt('research', 'diagnosing-bugs'),
                          '--receipt', grilling)
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = self.root / 'facts.json'
        facts.write_text(facts.read_text() + '\n')
        self.assertEqual(self.cli('next', self.record, '--json').returncode, 0)
        research = {s['id']: s for s in self.state()['stages']}['research']
        self.assertEqual(research['status'], 'needs_verification')
        refiled = self.root / 'grilling-refiled.json'
        result = self.cli('receipt-refile', self.record, '--receipt', grilling, '--stage', 'research',
                          '--reason', 'fixture whitespace drift only', '--out', refiled)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(refiled.read_text())['obligation_id'], 'grilling')

    def plan_optional_verify(self):
        """Verify stage wired like the planned interrogate hosting: optional-only components."""
        self.script = self.optional_scripts(stage_id='verify', required=(), optional=('interrogate',))
        self.assertEqual(self.plan(extra_sources=('interrogate',)).returncode, 0)
        verify = {s['id']: s for s in self.state()['stages']}['verify']
        self.assertEqual(verify['required_obligations'], [])
        self.assertEqual(verify['optional_obligations'], ['interrogate'])
        for stage in ('preflight', 'document'):
            self.assertEqual(self.complete(stage).returncode, 0)
        return verify

    def test_finish_verifies_task_with_optional_verify_participation_end_to_end(self):
        # Optional participation enters through explicit registration (component-event) and a
        # verify-stage optional receipt; the executed receipt keeps full verification.
        self.plan_optional_verify()
        output = self.make_receipt('verify', 'output')
        optional = self.make_receipt('verify', 'interrogate')
        # Executing an optional component means a complete receipt, captured checks included.
        self.assertTrue(json.loads(optional.read_text())['checks'])
        event = json.loads(Path(json.loads(optional.read_text())['observed_event_ref']['path']).read_text())
        self.assertEqual((event['component'], event['stage_id']), ('interrogate', 'verify'))
        result = self.cli('stage-complete', self.record, '--stage', 'verify',
                          '--receipt', output, '--receipt', optional)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.complete('close').returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        self.assertEqual(self.state()['status'], 'VERIFIED')

    def test_degraded_optional_receipt_satisfies_nothing_but_absence_finishes(self):
        # Both calibers at once: a stage-level degraded receipt is rejected even for an optional
        # obligation (component-level degraded registration with a reason is the separate
        # validate-layer trace), while leaving the optional obligation unexecuted — no receipt
        # at all — opens no gap and finishes.
        self.plan_optional_verify()
        output = self.make_receipt('verify', 'output')
        degraded = self.make_receipt('verify', 'interrogate', mode='degraded')
        result = self.cli('stage-complete', self.record, '--stage', 'verify',
                          '--receipt', output, '--receipt', degraded)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Degraded', result.stderr)
        verify = {s['id']: s for s in self.state()['stages']}['verify']
        self.assertNotEqual(verify['status'], 'passed')
        self.assertNotEqual(self.cli('finish', self.record).returncode, 0)
        # Skipping the optional component is the valid path: required coverage alone passes.
        passed = self.cli('stage-complete', self.record, '--stage', 'verify', '--receipt', output)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(self.complete('close').returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        self.assertEqual(self.state()['status'], 'VERIFIED')

    def test_optional_receipt_without_adaptation_keeps_finish_open(self):
        # The finish layer still checks every registered component receipt for an adaptation;
        # optional obligations get no lighter treatment.
        self.plan_optional_verify()
        output = self.make_receipt('verify', 'output')
        broken = self.make_receipt('verify', 'interrogate')
        value = json.loads(broken.read_text())
        value['adaptation'] = ''
        broken.write_text(json.dumps(value))
        result = self.cli('stage-complete', self.record, '--stage', 'verify',
                          '--receipt', output, '--receipt', broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('adaptation is required', result.stderr)
        finish = self.cli('finish', self.record)
        self.assertNotEqual(finish.returncode, 0)
        self.assertIn('verify', finish.stderr)
        self.assertNotEqual(self.state()['status'], 'VERIFIED')

    def test_finish_conditions_unchanged_for_tasks_without_optional_participation(self):
        # The production rule set declares exactly one optional component (interrogate on
        # verify); this run files no optional receipt, and the finish gate behaves as
        # before: incomplete tasks are rejected with their missing stages named.
        self.assertEqual(self.plan(behavior_change=True).returncode, 0)
        self.assertEqual(self.complete('preflight').returncode, 0)
        early = self.cli('finish', self.record)
        self.assertNotEqual(early.returncode, 0)
        self.assertIn('implement', early.stderr)
        self.assertIn('Degraded', self.complete('implement', 'tdd', mode='degraded').stderr)
        self.assertEqual(self.complete('implement', 'tdd').returncode, 0)
        for stage in ('verify', 'close'):
            self.assertEqual(self.complete(stage).returncode, 0)
        self.assertEqual(self.cli('finish', self.record).returncode, 0)
        self.assertEqual(self.state()['status'], 'VERIFIED')


if __name__ == '__main__':
    unittest.main()
