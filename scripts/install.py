#!/usr/bin/env python3
"""Install a complete versioned package, preserving edits and recoverable backups."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

FILES = (
    'VERSION', 'SKILL.md', 'WORKFLOW.md', 'ADAPTERS.md', 'README.md',
    'PROJECT.template.md', 'TASK.template.md', 'RELEASE.template.md', 'ROUTING.md',
    'scripts/evidence.py', 'scripts/workflow.py', 'scripts/acceptance.py', 'scripts/workflow_rules.json',
    'scripts/zcode_hook.py', 'docs/EXECUTION.md', 'docs/ZCODE.md', 'docs/TOOLS.md', 'docs/COMPONENTS.md', 'docs/BENCHMARK.md',
    'docs/COMPATIBILITY.md', 'docs/VISUAL.md', 'LICENSE', 'CHANGELOG.md',
)
MARKER = '.personal-coding-install.json'
ROOTS = {'codex': '.agents/skills', 'claude': '.claude/skills', 'zcode': '.zcode/skills'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_file(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.workflow-', delete=False) as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
        temporary = Path(out.name)
    os.replace(temporary, path)


def verify(destination):
    if destination.is_symlink():
        raise ValueError('Refusing symlink destination: ' + str(destination))
    marker = destination / MARKER
    if not destination.is_dir() or marker.is_symlink() or not marker.is_file():
        raise ValueError('Destination is not a managed installation: ' + str(destination))
    old = json.loads(marker.read_text())
    if old.get('name') != 'personal-coding' or not isinstance(old.get('files'), dict):
        raise ValueError('Invalid installation manifest')
    if not old['files'] or set(old['files']) - set(FILES):
        raise ValueError('Old package contains other files; migrate it explicitly')
    # Check every directory entry, including empty directories and symlinks.
    allowed = set(old['files']) | {MARKER}
    for name in old['files']:
        allowed.update(str(p) for p in Path(name).parents if str(p) != '.')
    actual = {str(p.relative_to(destination)) for p in destination.rglob('*')}
    if actual != allowed:
        raise ValueError('Unmanaged files in destination; preserve and inspect them first')
    for name in allowed:
        if (destination / name).is_symlink():
            raise ValueError('Refusing symlink in destination: ' + name)
    for name, expected in old['files'].items():
        path = destination / name
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError('Local modification detected; refusing overwrite: ' + str(path))
    return old


def journal_path(destination):
    return destination.parent / ('.' + destination.name + '.transaction.json')


def state_root():
    override = os.environ.get('PERSONAL_CODING_STATE_ROOT')
    if override:
        return Path(override)
    return Path.home() / '.local' / 'state' / 'personal-coding'


def backups_root(destination):
    scope = destination.parent.parent.name.lstrip('.') or 'root'
    return state_root() / 'backups' / scope / destination.name


def resolve_backup(destination, value):
    """Accept the current absolute state-directory path or a legacy in-place name."""
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError('Invalid transaction path')
    if Path(value).is_absolute():
        path = Path(value)
        if path.parent != backups_root(destination) or path.name in ('', '.', '..'):
            raise ValueError('Invalid transaction path')
        return path
    if Path(value).name != value or not value.startswith('.' + destination.name + '.previous-'):
        raise ValueError('Invalid transaction path')
    return destination.parent / value


def prune_backups(destination, keep):
    root = backups_root(destination)
    if not root.is_dir():
        return
    for child in root.iterdir():
        if child != keep:
            shutil.rmtree(child, ignore_errors=True)


def recover(destination):
    """Resolve a prior directory switch. Preserve stages for inspection."""
    journal = journal_path(destination)
    if not journal.exists():
        return
    if journal.is_symlink():
        raise ValueError('Refusing symlink transaction journal')
    state = json.loads(journal.read_text())
    if Path(state['stage']).name != state['stage'] or not state['stage'].startswith('.' + destination.name + '.stage-'):
        raise ValueError('Invalid transaction path')
    if (destination.parent / state['stage']).is_symlink():
        raise ValueError('Refusing symlink transaction directory')
    backup = resolve_backup(destination, state.get('backup'))
    if backup is not None and backup.is_symlink():
        raise ValueError('Refusing symlink transaction directory')
    if destination.is_symlink():
        raise ValueError('Refusing symlink destination')
    if not destination.exists() and backup is not None and backup.exists():
        os.replace(backup, destination)
    # Preserve local changes made during the interruption; normal install verifies them.
    if destination.exists():
        journal.unlink()
    elif state['had_destination']:
        raise ValueError('Recovery requires the missing previous directory; inspect journal')
    else:
        journal.unlink()  # First installation interrupted before the complete stage switch.


def install(source, destination, check=False):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if source.resolve() == destination.resolve():
        raise ValueError('Source and destination must differ')
    if check and journal_path(destination).exists():
        raise ValueError('Pending transaction; run install again to recover')
    if not check:
        recover(destination)
    payload = {}
    for name in FILES:
        path = source / name
        if any((source / p).is_symlink() for p in (Path(name), *Path(name).parents)) or not path.is_file():
            raise ValueError('Missing or symlinked source: ' + str(path))
        payload[name] = path.read_bytes()
    version = payload['VERSION'].decode().strip()
    desired = {'name': 'personal-coding', 'version': version,
               'files': {name: digest(data) for name, data in payload.items()}}
    if destination.is_symlink():
        raise ValueError('Refusing symlink destination: ' + str(destination))
    if destination.exists():
        old = verify(destination)
        if old == desired:
            return 'CURRENT ' + str(destination)
        if check:
            raise ValueError('Installed copy differs from source: ' + str(destination))
        if old.get('version') == version:
            raise ValueError('Same-version content changed; increment VERSION before updating')
    elif check:
        raise ValueError('Not installed: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + destination.name + '.stage-', dir=destination.parent))
    backup = None
    if destination.exists():
        label = old.get('version')
        if not isinstance(label, str) or Path(label).name != label or label in ('', '.', '..'):
            raise ValueError('Invalid version label for backup')
        # Outside client skill scan paths; one retained copy, older versions live in git.
        backup = backups_root(destination) / label
        backup.parent.mkdir(parents=True, exist_ok=True)
    for name, data in payload.items():
        (stage / name).parent.mkdir(parents=True, exist_ok=True)
        replace_file(stage / name, data)
    replace_file(stage / MARKER, (json.dumps(desired, indent=2) + '\n').encode())
    verify(stage)
    state = {'stage': stage.name, 'backup': str(backup) if backup is not None else None,
             'had_destination': destination.exists()}
    replace_file(journal_path(destination), (json.dumps(state) + '\n').encode())
    if backup is not None:
        os.replace(destination, backup)
    os.replace(stage, destination)
    journal_path(destination).unlink()
    if backup is not None:
        prune_backups(destination, backup)
    return 'INSTALLED ' + version + ' ' + str(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=ROOTS)
    parser.add_argument('--check', action='store_true', help='Verify without changing files')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    destination = Path.home() / ROOTS[args.target] / 'personal-coding'
    try:
        print(install(source, destination, args.check))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, 'ERROR: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
