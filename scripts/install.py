#!/usr/bin/env python3
"""Install a versioned local workflow copy without overwriting local edits."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


FILES = (
    "VERSION", "SKILL.md", "WORKFLOW.md", "ADAPTERS.md", "README.md",
    "PROJECT.template.md", "TASK.template.md", "RELEASE.template.md", "ROUTING.md",
)
MARKER = ".personal-coding-install.json"
ROOTS = {"codex": ".agents/skills", "claude": ".claude/skills", "zcode": ".zcode/skills"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_file(path, data):
    # Replace the directory entry so an upgrade cannot mutate hardlinked backups.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".workflow-", delete=False) as out:
        out.write(data)
        temporary = Path(out.name)
    os.replace(temporary, path)


def install(source, destination, check=False):
    source, destination = Path(source), Path(destination)
    payload = {}
    for name in FILES:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or symlinked source: " + str(path))
        payload[name] = path.read_bytes()
    version = payload["VERSION"].decode().strip()
    desired = {"name": "personal-coding", "version": version,
               "files": {name: digest(data) for name, data in payload.items()}}
    if destination.is_symlink():
        raise ValueError("Refusing symlink destination: " + str(destination))
    if destination.exists():
        marker = destination / MARKER
        if not destination.is_dir() or marker.is_symlink() or not marker.is_file():
            raise ValueError("Destination is not a managed installation: " + str(destination))
        old = json.loads(marker.read_text())
        if old.get("name") != "personal-coding" or not isinstance(old.get("files"), dict):
            raise ValueError("Invalid installation manifest")
        if set(old["files"]) - set(FILES):
            raise ValueError("Old package contains other files; migrate it explicitly")
        if {p.name for p in destination.iterdir()} != set(old["files"]) | {MARKER}:
            raise ValueError("Unmanaged files in destination; preserve and inspect them first")
        for name, expected in old["files"].items():
            path = destination / name
            if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError("Local modification detected; refusing overwrite: " + str(path))
        if old == desired:
            return "CURRENT " + str(destination)
        if check:
            raise ValueError("Installed copy differs from source: " + str(destination))
        if old.get("version") == version:
            raise ValueError("Same-version content changed; increment VERSION before updating")
    elif check:
        raise ValueError("Not installed: " + str(destination))
    if destination.resolve() == source.resolve():
        raise ValueError("Source and destination must differ")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in payload.items():
        replace_file(destination / name, data)
    replace_file(destination / MARKER, (json.dumps(desired, indent=2) + "\n").encode())
    return "INSTALLED " + version + " " + str(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=ROOTS)
    parser.add_argument("--check", action="store_true", help="Verify without changing files")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    # CODEX_HOME is deliberately not changed; the current documented user root is .agents.
    destination = Path.home() / ROOTS[args.target] / "personal-coding"
    try:
        print(install(source, destination, args.check))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, "ERROR: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
