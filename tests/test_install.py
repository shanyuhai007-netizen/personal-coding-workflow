"""Distribution invariants: preserve edits, reject collisions, verify copies."""

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install.py"
spec = importlib.util.spec_from_file_location("workflow_install", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class WorkflowInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.dest = self.root / "source", self.root / "installed"
        self.source.mkdir()
        for name in installer.FILES:
            (self.source / name).parent.mkdir(parents=True, exist_ok=True)
            (self.source / name).write_text("0.1.0\n" if name == "VERSION" else "original\n")

    def test_install_and_repeat_keep_the_same_files(self):
        installer.install(self.source, self.dest)
        before = {str(p.relative_to(self.dest)): p.read_bytes() for p in self.dest.rglob("*") if p.is_file()}
        installer.install(self.source, self.dest)
        self.assertEqual(before, {str(p.relative_to(self.dest)): p.read_bytes() for p in self.dest.rglob("*") if p.is_file()})
        self.assertTrue(installer.install(self.source, self.dest, check=True).startswith("CURRENT"))

    def test_check_does_not_create_missing_installation(self):
        with self.assertRaisesRegex(ValueError, "Not installed"):
            installer.install(self.source, self.dest, check=True)
        self.assertFalse(self.dest.exists())

    def test_new_version_updates_unmodified_managed_copy(self):
        installer.install(self.source, self.dest)
        (self.source / "VERSION").write_text("0.1.1\n")
        (self.source / "WORKFLOW.md").write_text("new behavior\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            installer.install(self.source, self.dest, check=True)
        self.assertEqual((self.dest / "WORKFLOW.md").read_text(), "original\n")
        installer.install(self.source, self.dest)
        self.assertEqual((self.dest / "WORKFLOW.md").read_text(), "new behavior\n")

    def test_local_edits_survive_an_attempted_upgrade(self):
        installer.install(self.source, self.dest)
        (self.dest / "WORKFLOW.md").write_text("user edit\n")
        (self.source / "VERSION").write_text("0.1.1\n")
        with self.assertRaisesRegex(ValueError, "Local modification"):
            installer.install(self.source, self.dest)
        self.assertEqual((self.dest / "WORKFLOW.md").read_text(), "user edit\n")

    def test_unmanaged_directory_and_symlink_are_preserved(self):
        self.dest.mkdir()
        (self.dest / "SKILL.md").write_text("user skill\n")
        with self.assertRaisesRegex(ValueError, "not a managed"):
            installer.install(self.source, self.dest)
        link = self.root / "link"
        link.symlink_to(self.dest, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            installer.install(self.source, link)
        self.assertEqual((self.dest / "SKILL.md").read_text(), "user skill\n")

    def test_same_version_drift_requires_a_version_bump(self):
        installer.install(self.source, self.dest)
        (self.source / "WORKFLOW.md").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "increment VERSION"):
            installer.install(self.source, self.dest)
        self.assertEqual((self.dest / "WORKFLOW.md").read_text(), "original\n")

    def test_upgrade_preserves_a_hardlinked_backup(self):
        installer.install(self.source, self.dest)
        backup = self.root / "backup.md"
        backup.hardlink_to(self.dest / "WORKFLOW.md")
        (self.source / "VERSION").write_text("0.1.1\n")
        (self.source / "WORKFLOW.md").write_text("new behavior\n")
        installer.install(self.source, self.dest)
        self.assertEqual((self.dest / "WORKFLOW.md").read_text(), "new behavior\n")
        self.assertEqual(backup.read_text(), "original\n")

    def test_interrupted_switch_is_recoverable_without_mixing_files(self):
        installer.install(self.source, self.dest)
        (self.source / 'VERSION').write_text('0.2.0\n')
        (self.source / 'WORKFLOW.md').write_text('new\n')
        replace = os.replace

        def interrupt(source, target):
            if Path(source).is_dir() and Path(target) == self.dest:
                raise OSError('simulated interruption')
            return replace(source, target)

        with patch.object(os, 'replace', side_effect=interrupt):
            with self.assertRaises(OSError):
                installer.install(self.source, self.dest)
        installer.install(self.source, self.dest)
        self.assertEqual((self.dest / 'WORKFLOW.md').read_text(), 'new\n')
        self.assertTrue(installer.install(self.source, self.dest, check=True).startswith('CURRENT'))
        backups = list(self.root.glob('.installed.previous-*'))
        self.assertTrue(any((p / 'WORKFLOW.md').read_text() == 'original\n' for p in backups))

    def test_recovery_check_is_readonly_and_preserves_later_edits(self):
        installer.install(self.source, self.dest)
        (self.source / 'VERSION').write_text('0.2.0\n')
        replace = os.replace

        def interrupt(source, target):
            if Path(source).is_dir() and Path(target) == self.dest:
                raise OSError('interrupted')
            return replace(source, target)

        with patch.object(os, 'replace', side_effect=interrupt):
            with self.assertRaises(OSError):
                installer.install(self.source, self.dest)
        with self.assertRaisesRegex(ValueError, 'Pending transaction'):
            installer.install(self.source, self.dest, check=True)
        self.assertFalse(self.dest.exists())
        backup = next(self.root.glob('.installed.previous-*'))
        (backup / 'WORKFLOW.md').write_text('preserved user edit\n')
        with self.assertRaisesRegex(ValueError, 'Local modification'):
            installer.install(self.source, self.dest)
        self.assertEqual((self.dest / 'WORKFLOW.md').read_text(), 'preserved user edit\n')

    def test_installed_helper_is_runnable(self):
        source = SCRIPT.parents[1]
        installer.install(source, self.dest)
        result = subprocess.run([sys.executable, str(self.dest / 'scripts/evidence.py'), '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('snapshot', result.stdout)
        self.assertIn('plan', result.stdout)

    def test_installed_acceptance_records_observations_and_refuses_incomplete_task(self):
        installer.install(SCRIPT.parents[1], self.dest)
        repo = self.root / 'repo'
        repo.mkdir()
        for args in (('init', '-q'), ('config', 'user.email', 'fixture@example.invalid'),
                     ('config', 'user.name', 'Fixture')):
            subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
        (repo / 'app.txt').write_text('synthetic fixture\n')
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixture'],
                       check=True, capture_output=True)

        def cli(*args, expected=0):
            # Execute the installed entry from a different cwd, ignoring PYTHON* env.
            result = subprocess.run([sys.executable, '-E', str(self.dest / 'scripts/evidence.py'),
                                     *map(str, args)], cwd=repo, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            return result

        contract = self.root / 'contract.md'
        contract.write_text('Check the fixture repository and replay a second operation.\n')
        facts = self.root / 'facts.json'
        facts.write_text(json.dumps({
            'task_id': 'installed-acceptance', 'goal': 'Exercise installed acceptance gates',
            'facts': {'intent': {'value': 'implement', 'evidence': str(contract)}},
            'conditions': [
                {'id': name, 'source': str(contract), 'locator': 'line 1',
                 'requirement': requirement, 'target': 'local synthetic repository'}
                for name, requirement in (('repository', 'Check the fixture repository'),
                                          ('replay', 'Replay a second operation'))]}))
        record = self.root / 'task.json'
        cli('plan', '--facts', facts, '--record', record)
        check = self.root / 'check'
        cli('run', '--out', check, '--', 'git', 'rev-parse', '--is-inside-work-tree')
        raw = check / 'output.log'
        self.assertEqual(raw.read_text().strip(), 'true')
        report = self.root / 'observations.json'
        report.write_text(json.dumps([{
            'id': 'repository', 'status': 'pass',
            'behavior': 'git rev-parse --is-inside-work-tree',
            'target': 'local synthetic repository', 'observation': raw.read_text().strip(),
            'evidence': [str(raw)]}]))
        cli('acceptance', record, '--report', report)
        state = json.loads(record.read_text())
        observation, = state['acceptance']['observations']
        self.assertEqual(observation['id'], 'repository')
        self.assertEqual(observation['status'], 'pass')
        self.assertEqual(observation['observation'], 'true')
        self.assertEqual(observation['evidence'][0]['sha256'],
                         hashlib.sha256(raw.read_bytes()).hexdigest())
        refused = cli('finish', record, expected=2)
        self.assertIn('preflight', refused.stderr)
        self.assertIn('replay: unverified', refused.stderr)
        self.assertNotEqual(json.loads(record.read_text())['status'], 'VERIFIED')

        # Complete synthetic stage declarations through the same installed CLI:
        # green stages must still leave the unobserved original condition unmet.
        proof = self.root / 'stage-proof.md'
        proof.write_text('Synthetic stage fixture; repository check is in check/output.log.\n')
        for stage in ('preflight', 'document', 'verify', 'close'):
            event = self.root / (stage + '-event.json')
            event.write_text(json.dumps({
                'task_id': 'installed-acceptance', 'stage_id': stage, 'component': 'output',
                'mode': 'read', 'status': 'success'}))
            receipt = self.root / (stage + '-receipt.json')
            args = ['stage-receipt', record, '--stage', stage, '--obligation', 'output',
                    '--mode', 'read', '--verification', 'pass', '--event', event,
                    '--artifact', proof, '--input', facts, '--adaptation', 'synthetic fixture',
                    '--out', receipt]
            if stage == 'verify':
                args += ['--check', check / 'result.json']
            cli(*args)
            cli('stage-complete', record, '--stage', stage, '--receipt', receipt)
        refused = cli('finish', record, expected=2)
        self.assertIn('replay: unverified', refused.stderr)
        self.assertNotIn('preflight:', refused.stderr)
        state = json.loads(record.read_text())
        self.assertNotEqual(state['status'], 'VERIFIED')
        self.assertEqual(state['acceptance']['observations'], [observation])


if __name__ == "__main__":
    unittest.main()
