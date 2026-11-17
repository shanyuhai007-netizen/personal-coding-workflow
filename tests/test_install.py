"""Distribution invariants: preserve edits, reject collisions, verify copies."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


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
            (self.source / name).write_text("0.1.0\n" if name == "VERSION" else "original\n")

    def test_install_and_repeat_keep_the_same_files(self):
        installer.install(self.source, self.dest)
        before = {p.name: p.read_bytes() for p in self.dest.iterdir()}
        installer.install(self.source, self.dest)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.dest.iterdir()})
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


if __name__ == "__main__":
    unittest.main()
