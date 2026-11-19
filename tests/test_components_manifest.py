"""Manifest consistency: skill references in tracked docs stay within docs/COMPONENTS.md."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs' / 'COMPONENTS.md'

# 外部 skill 词表，与 docs/COMPONENTS.md 清单同步维护；新增登记时同步此表。
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
    def test_manifest_registers_every_external_skill(self):
        manifest = MANIFEST.read_text(encoding='utf-8')
        missing = [name for name in EXTERNAL_SKILLS if name not in manifest]
        self.assertEqual(missing, [])

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
