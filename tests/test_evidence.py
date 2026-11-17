"""Public command invariants using synthetic repositories only."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evidence.py'


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'app.txt').write_text('old\n')
        (self.repo / 'delete.txt').write_text('remove\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args]).decode().strip()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=self.repo,
                              capture_output=True, text=True)

    def test_snapshot_covers_all_changes_and_preserves_index(self):
        (self.repo / 'app.txt').write_text('staged\n')
        self.git('add', 'app.txt')
        index_before = (self.repo / '.git/index').read_bytes()
        (self.repo / 'app.txt').write_text('working\n')
        (self.repo / 'delete.txt').unlink()
        (self.repo / 'new.txt').write_text('new content\n')
        head_before = self.git('rev-parse', 'HEAD')
        out = self.root / 'review'
        result = self.cli('snapshot', '--base', 'HEAD', '--out', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        patch = (out / 'review.patch').read_text()
        for expected in ('+working', '+new content', '-remove'):
            self.assertIn(expected, patch)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index_before)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head_before)
        manifest = json.loads((out / 'snapshot.json').read_text())
        self.assertEqual(self.git('show', manifest['tree'] + ':app.txt'), 'working')

    def test_run_preserves_long_output_and_failure_status(self):
        out = self.root / 'check'
        result = self.cli('run', '--out', out, '--', sys.executable, '-c',
                          "print('first'); print('x'*100000); print('last'); raise SystemExit(7)")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertTrue((out / 'output.log').read_text().startswith('first\n'))
        self.assertTrue((out / 'output.log').read_text().endswith('last\n'))
        record = json.loads((out / 'result.json').read_text())
        self.assertEqual(record['exit_code'], 7)
        self.assertEqual(record['tree_before'], record['tree_after'])

    def test_snapshot_includes_force_staged_ignored_files(self):
        (self.repo / '.gitignore').write_text('included.txt\n')
        (self.repo / 'included.txt').write_text('explicitly staged\n')
        self.git('add', '-f', 'included.txt')
        out = self.root / 'review'
        result = self.cli('snapshot', '--base', 'HEAD', '--out', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('+explicitly staged', (out / 'review.patch').read_text())

    def test_validator_rejects_unverified_stale_and_nonindependent_records(self):
        check = self.root / 'check'
        self.assertEqual(self.cli('run', '--out', check, '--', sys.executable, '-c', 'print("ok")').returncode, 0)
        tree = json.loads((check / 'result.json').read_text())['tree_after']
        proof = self.root / 'proof.md'
        proof.write_text('Synthetic output: behavior observed; both review axes pass.\n')
        skill = self.root / 'SKILL.md'
        skill.write_text('---\nname: fixture\ndescription: synthetic\n---\nRun a check.\n')
        component = self.root / 'component'
        result = self.cli('component', '--skill', skill, '--name', 'fixture', '--mode', 'read',
                          '--proof', proof, '--adaptation', 'No native skill tool in fixture', '--out', component)
        self.assertEqual(result.returncode, 0, result.stderr)
        artifact = {'path': str(proof), 'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()}
        task = {'tree': tree, 'independent_required': True,
                'conditions': [{'id': 'behavior', 'required': True, 'status': 'pass', 'evidence': artifact}],
                'checks': [str(check / 'result.json')],
                'components': [str(component / 'component.json')],
                'reviews': [{'axis': axis, 'tree': tree, 'independent': True, 'status': 'pass',
                             'evidence': artifact} for axis in ('standards', 'spec')]}
        record = self.root / 'task.json'

        def validate():
            record.write_text(json.dumps(task))
            return self.cli('validate', record)

        self.assertEqual(validate().returncode, 0)
        task['conditions'][0]['status'] = 'unverified'
        self.assertNotEqual(validate().returncode, 0)
        task['conditions'][0]['status'] = 'pass'
        task['reviews'][0]['independent'] = False
        self.assertNotEqual(validate().returncode, 0)
        task['reviews'][0]['independent'] = True
        (self.repo / 'app.txt').write_text('later change\n')
        self.assertNotEqual(validate().returncode, 0)

    def test_archive_survives_source_removal_and_detects_tampering(self):
        source = self.root / 'samples.tsv'
        source.write_text('duration_ms\n12\n')
        out = self.root / 'durable'
        result = self.cli('archive', '--out', out, '--file', source)
        self.assertEqual(result.returncode, 0, result.stderr)
        source.unlink()
        self.assertEqual(self.cli('verify-archive', out).returncode, 0)
        (out / 'samples.tsv').write_text('changed\n')
        self.assertNotEqual(self.cli('verify-archive', out).returncode, 0)


if __name__ == '__main__':
    unittest.main()
