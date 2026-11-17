"""Distribution invariants: preserve edits, reject collisions, verify copies."""

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
