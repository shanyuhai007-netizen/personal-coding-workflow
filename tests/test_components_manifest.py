"""Manifest consistency: skill references in tracked docs stay within docs/COMPONENTS.md."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs' / 'COMPONENTS.md'

# 外部 skill 词表；与 docs/COMPONENTS.md 清单双向相等由
# test_manifest_vocabulary_matches_table 强制，漏改任一侧都会失败。
EXTERNAL_SKILLS = (
    'grilling', 'tdd', 'code-review', 'diagnosing-bugs', 'research', 'retro',
    'handoff', 'to-spec', 'to-tickets', 'implement', 'implement-spec',
    'triage', 'wayfinder', 'domain-modeling', 'grill-with-docs',
    'improve-codebase-architecture',
    'modern-web-guidance', 'vercel-react-best-practices', 'web-design-guidelines',
    'frontend-design', 'emil-design-eng', 'ui-taste-loop',
)


def markdown_files():
    for path in sorted(ROOT.rglob('*.md')):
        if '.git' in path.parts or '__pycache__' in path.parts:
            continue
        yield path


class ManifestTests(unittest.TestCase):
    def registered_external_skills(self):
        """Parse 外部 skill rows of the manifest table into a name set."""
        names = set()
        for line in MANIFEST.read_text(encoding='utf-8').splitlines():
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) >= 2 and cells[1] == '外部 skill':
                names.update(part.strip() for part in cells[0].split('、') if part.strip())
        return names

    def test_manifest_registers_every_external_skill(self):
        manifest = MANIFEST.read_text(encoding='utf-8')
        missing = [name for name in EXTERNAL_SKILLS if name not in manifest]
        self.assertEqual(missing, [])

    def test_manifest_vocabulary_matches_table(self):
        table = self.registered_external_skills()
        vocabulary = set(EXTERNAL_SKILLS)
        self.assertEqual(
            vocabulary - table, set(),
            'names in test vocabulary but not in manifest table')
        self.assertEqual(
            table - vocabulary, set(),
            'names in manifest table but not in test vocabulary')

    def test_slash_invocations_in_docs_are_registered(self):
        manifest = MANIFEST.read_text(encoding='utf-8')
        pattern = re.compile(r'`/([a-z][a-z0-9-]+)`')
        offenders = {}
        for path in markdown_files():
            invoked = set(pattern.findall(path.read_text(encoding='utf-8')))
            unregistered = {name for name in invoked if name not in manifest}
            if unregistered:
                offenders[str(path.relative_to(ROOT))] = sorted(unregistered)
        self.assertEqual(offenders, {})


if __name__ == '__main__':
    unittest.main()
