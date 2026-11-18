#!/usr/bin/env python3
"""Local evidence helpers. Records are declarations, not runtime attestations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def git(repo, *args, env=None):
    return subprocess.check_output(['git', '-C', str(repo), *args], env=env).decode().strip()


def code_tree(repo):
    """Use an alternate index; Git stores objects, but no refs/index are changed."""
    with tempfile.TemporaryDirectory(prefix='workflow-index-') as temp:
        env = os.environ.copy()
        env['GIT_INDEX_FILE'] = str(Path(temp) / 'index')
        # Start with staged files too, including explicitly force-added ignored files.
        real_index = Path(git(repo, 'rev-parse', '--git-path', 'index'))
        if not real_index.is_absolute():
            real_index = Path(repo) / real_index
        if real_index.exists():
            shutil.copyfile(real_index, env['GIT_INDEX_FILE'])
        else:
            git(repo, 'read-tree', 'HEAD', env=env)
        git(repo, 'add', '-A', '--', '.', env=env)
        return git(repo, 'write-tree', env=env)


def outside_repo(repo, out):
    root = Path(git(repo, 'rev-parse', '--show-toplevel')).resolve()
    if Path(out).resolve().is_relative_to(root):
        raise ValueError('Evidence output must be outside the repository')
    return root


def snapshot(repo, base, out):
    repo = outside_repo(repo, out)
    base = git(repo, 'rev-parse', '--verify', base + '^{commit}')
    tree = code_tree(repo)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    patch = subprocess.check_output(['git', '-C', str(repo), 'diff', '--binary', base, tree, '--'])
    (out / 'review.patch').write_bytes(patch)
    write_json(out / 'snapshot.json', {
        'base': base, 'head': git(repo, 'rev-parse', 'HEAD'), 'tree': tree,
        'patch_sha256': sha(out / 'review.patch'), 'empty': not bool(patch),
        'review_command': ['git', 'diff', '--binary', base, tree, '--'],
    })
    return 0


def run_check(repo, out, argv):
    repo = outside_repo(repo, out)
    if not argv:
        raise ValueError('A command is required after --')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    before = code_tree(repo)
    start = time.time()
    # No shell wrapper: capture the command status rather than tail/tee status.
    with (out / 'output.log').open('wb') as log:
        try:
            process = subprocess.run(argv, cwd=repo, stdout=log, stderr=subprocess.STDOUT)
            status = process.returncode
        except OSError as exc:
            log.write(str(exc).encode())
            status = 127
    after = code_tree(repo)
    write_json(out / 'result.json', {
        'argv': argv, 'cwd': str(repo), 'head': git(repo, 'rev-parse', 'HEAD'),
        'tree_before': before, 'tree_after': after, 'exit_code': status,
        'started_at': start, 'duration_seconds': time.time() - start,
        'output_sha256': sha(out / 'output.log'),
    })
    print(str(out / 'result.json'))
    return status if status >= 0 else 128 - status


def archive(out, files):
    files = [Path(p).resolve() for p in files]
    if not files or len({p.name for p in files}) != len(files) or any(p.name == 'manifest.json' for p in files):
        raise ValueError('Archive needs files with distinct names, excluding manifest.json')
    payload = {p.name: p.read_bytes() for p in files}
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    for name, data in payload.items():
        (out / name).write_bytes(data)
    write_json(out / 'manifest.json', {name: sha(out / name) for name in payload})
    return 0


def verify_archive(out):
    out = Path(out)
    manifest = json.loads((out / 'manifest.json').read_text())
    if not manifest:
        raise ValueError('Empty archive manifest')
    for name, expected in manifest.items():
        if Path(name).name != name or sha(out / name) != expected:
            raise ValueError('Archive hash mismatch: ' + name)
    print('ARCHIVE_HASHES_VALID')
    return 0


def artifact(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def component(args):
    if args.mode == 'degraded' and not args.reason:
        raise ValueError('Degradation requires an observed restriction or absence reason')
    if args.mode != 'degraded' and not args.skill:
        raise ValueError('A component source is required for native/read/reuse modes')
    out = Path(args.out).resolve()
    proof = Path(args.proof).read_bytes()
    if not proof.strip():
        raise ValueError('Execution proof must be nonempty')
    sources = [Path(p).resolve() for p in ([args.skill] if args.skill else []) + args.file]
    data = [(p, p.read_bytes()) for p in sources]
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.md').write_bytes(proof)
    captured = []
    for index, (source, content) in enumerate(data):
        target = out / (str(index) + '-' + source.name)
        target.write_bytes(content)
        captured.append({'origin': str(source), 'path': target.name, 'sha256': sha(target)})
    write_json(out / 'component.json', {
        'name': args.name, 'mode': args.mode, 'adaptation': args.adaptation,
        'reason': args.reason, 'sources': captured,
        'evidence': {'path': 'execution.md', 'sha256': sha(out / 'execution.md')},
        'attestation': 'caller-declared; hash capture does not prove execution',
    })
    return 0


def resolve_file(parent, value):
    path = Path(value)
    return path if path.is_absolute() else parent / path


def verify_artifact(parent, value):
    path = resolve_file(parent, value['path'])
    if not path.is_file() or not path.stat().st_size or sha(path) != value['sha256']:
        raise ValueError('Missing, empty or changed evidence: ' + str(path))


def validate(record, repo):
    path = Path(record).resolve()
    parent = path.parent
    task = json.loads(path.read_text())
    independent_required = task.get('independent_required', True)
    if type(independent_required) is not bool:
        raise ValueError('independent_required must be a boolean')
    reason = task.get('independence_reason', '')
    if not independent_required and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError('Limited review requires an independence_reason')
    root = git(repo, 'rev-parse', '--show-toplevel')
    tree = code_tree(root)
    if task['tree'] != tree:
        raise ValueError('Current code tree differs from task evidence')
    if not task['conditions']:
        raise ValueError('At least one observable condition is required')
    for condition in task['conditions']:
        if condition.get('required', True):
            if condition['status'] != 'pass':
                raise ValueError('Required condition is unverified: ' + condition['id'])
            verify_artifact(parent, condition['evidence'])
    if not task['checks']:
        raise ValueError('At least one check record is required')
    for value in task['checks']:
        result_path = resolve_file(parent, value)
        result = json.loads(result_path.read_text())
        if result['exit_code'] != 0 or result['tree_before'] != tree or result['tree_after'] != tree:
            raise ValueError('Failed or stale check: ' + str(result_path))
        if sha(result_path.parent / 'output.log') != result['output_sha256']:
            raise ValueError('Check output hash mismatch')
    # Every triggered component belongs here, including reused or degraded stages.
    if not task['components']:
        raise ValueError('At least one component receipt is required')
    for value in task['components']:
        receipt_path = resolve_file(parent, value)
        receipt = json.loads(receipt_path.read_text())
        if not receipt['name'] or not receipt['adaptation']:
            raise ValueError('Component needs name and adaptation')
        if receipt['mode'] not in ('native', 'read', 'reuse', 'degraded'):
            raise ValueError('Invalid component mode')
        if receipt['mode'] == 'degraded':
            if not receipt['reason']:
                raise ValueError('Degradation requires a reason')
        elif not receipt['sources']:
            raise ValueError('Component needs source hashes')
        for source in receipt['sources']:
            verify_artifact(receipt_path.parent, source)
        verify_artifact(receipt_path.parent, receipt['evidence'])
    reviews = task['reviews']
    for axis in ('standards', 'spec'):
        matching = [r for r in reviews if r['axis'] == axis]
        if len(matching) != 1:
            raise ValueError('Exactly one review required for ' + axis)
        review = matching[0]
        if review['status'] != 'pass' or review['tree'] != tree:
            raise ValueError('Unresolved or stale review: ' + axis)
        if type(review['independent']) is not bool:
            raise ValueError('Review independence must be a boolean')
        if independent_required and review['independent'] is not True:
            raise ValueError('Independent review missing: ' + axis)
        verify_artifact(parent, review['evidence'])
    print('RECORD_VALID: declared evidence checks passed; semantic review remains agent responsibility')
    return 0


def main():
    workflow_commands = {'plan', 'next', 'finish', 'stage-complete', 'stage-receipt', 'stage-resume', 'operation', 'component-event'}
    workflow = None
    if sys.argv[1:2] and sys.argv[1] in workflow_commands:
        sys.dont_write_bytecode = True
        import workflow
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    snap = sub.add_parser('snapshot', help='Capture full worktree diff without touching real index')
    snap.add_argument('--base', required=True)
    snap.add_argument('--repo', default='.')
    snap.add_argument('--out', required=True)
    run = sub.add_parser('run', help='Save full output and original exit status')
    run.add_argument('--repo', default='.')
    run.add_argument('--out', required=True)
    run.add_argument('argv', nargs=argparse.REMAINDER)
    arc = sub.add_parser('archive', help='Copy selected files to durable evidence with hashes')
    arc.add_argument('--out', required=True)
    arc.add_argument('--file', action='append', required=True)
    verify = sub.add_parser('verify-archive')
    verify.add_argument('directory')
    comp = sub.add_parser('component', help='Capture declared component use and source hashes')
    comp.add_argument('--name', required=True)
    comp.add_argument('--mode', required=True, choices=['native', 'read', 'reuse', 'degraded'])
    comp.add_argument('--skill')
    comp.add_argument('--file', action='append', default=[])
    comp.add_argument('--proof', required=True, help='Execution trace/output, not just a source listing')
    comp.add_argument('--adaptation', required=True)
    comp.add_argument('--reason', default='')
    comp.add_argument('--out', required=True)
    val = sub.add_parser('validate', help='Check supplied evidence records against current tree')
    val.add_argument('record')
    val.add_argument('--repo', default='.')
    if workflow is not None:
        workflow.add_parsers(sub)
    elif sys.argv[1:] == ['--help'] or sys.argv[1:] == ['-h']:
        for name in sorted(workflow_commands):
            sub.add_parser(name, help='Task-scoped plan, execution, or completion command')
    args = parser.parse_args()
    try:
        if args.command in workflow_commands:
            return workflow.dispatch(args)
        if args.command == 'snapshot':
            return snapshot(args.repo, args.base, args.out)
        if args.command == 'run':
            argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
            return run_check(args.repo, args.out, argv)
        if args.command == 'archive':
            return archive(args.out, args.file)
        if args.command == 'verify-archive':
            return verify_archive(args.directory)
        if args.command == 'component':
            return component(args)
        if args.command == 'validate':
            return validate(args.record, args.repo)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, StopIteration) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
