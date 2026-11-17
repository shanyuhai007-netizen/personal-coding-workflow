# Development

Read [docs/SPEC.md](docs/SPEC.md) for scope and acceptance. Python 3.10+, standard library only; commands run from the repository root.

Run `python3 -m unittest discover -s tests -v`. Test observable CLI/file behavior with synthetic fixtures. Keep user index, HEAD, edits and evidence intact. Fault injection at filesystem boundaries is appropriate for crash recovery tests.

Workflow instructions live in WORKFLOW.md; component selection in ROUTING.md; adaptations in ADAPTERS.md; tool contracts in docs/TOOLS.md. Change one authoritative location and link to it. Increment VERSION before updating installed copies. Avoid unsupported claims about client discovery or runtime enforcement.

This repository contains generic workflow assets only. Local task records and session evidence stay outside tracked files. Third-party skills are optional references, never bundled. Public changes require authorization for this repository and must pass a tracked-file/history inspection.
