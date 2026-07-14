# Publishing

This folder is intended to be publishable as its own repository root.

## Minimal Repository Shape

Keep these at the repo root:

- `pyproject.toml`
- `SKILL.md`
- `README.md`
- `PUBLISHING.md`
- `REMOTE_INSTALL.md`
- `src/`
- `references/`
- `scripts/`
- `tests/`
- optional `examples/`

## Pre-Publish Check

Run:

```bash
./scripts/check-skill.sh
```

That same check now runs automatically on every branch push and pull request through `.github/workflows/ci.yml`.

## Suggested Release Flow

1. commit the skill updates
2. confirm that `pyproject.toml`, installed package metadata, and `ios_ui_testability_contract.__version__` all contain the same `X.Y.Z` version
3. tag that exact version as `vX.Y.Z`
4. push the tag
5. install the skill from that repository URL in any Codex-compatible environment that supports remote skill installation
6. if you support a moving compatibility tag, update the matching major tag (for example, `vX`) after the release tag is published

The repo also ships `.github/workflows/release.yml` for the manual GitHub-side release path. It sets up Python 3.12, reruns `./scripts/check-skill.sh`, installs the package non-editably, and compares the requested tag version with both installed package metadata and the CLI/runtime version. Any mismatch fails before tagging. A successful run creates the requested semantic tag, optionally updates the matching major tag, and then creates the GitHub release notes. If a run stops after pushing the semantic tag, rerunning from the same commit resumes safely; an existing tag is accepted only when it resolves to that commit, and an existing GitHub release is left intact.

To inspect the version that a release tag must use:

```bash
python -m pip install .
python -c 'from importlib.metadata import version; print(version("ios-ui-testability-contract"))'
ios-ui-testability --version
```

If those commands print `X.Y.Z`, dispatch the release workflow with `version_tag` set to exactly `vX.Y.Z`.

The Python package exposes the `ios-ui-testability` command. Keep `src/` as the implementation source and leave the `scripts/` files as compatibility wrappers for older docs and skill installers.

## Upgrade Guidance

- use a full release tag when you want deterministic installs
- use a moving major tag such as `vX` only when you intentionally want compatible updates
- avoid telling consumers to install from `main` once the skill is in real use
