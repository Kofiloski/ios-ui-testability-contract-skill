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
2. tag a release such as `v0.1.0`
3. push the tag
4. install the skill from that repository URL in any Codex-compatible environment that supports remote skill installation
5. if you support a moving compatibility tag, update `v0` after the release tag is published

The repo also ships `.github/workflows/release.yml` for the manual GitHub-side release path. It reruns `./scripts/check-skill.sh`, creates the requested semantic tag, optionally updates the matching major tag such as `v0`, and then creates the GitHub release notes.

The Python package exposes the `ios-ui-testability` command. Keep `src/` as the implementation source and leave the `scripts/` files as compatibility wrappers for older docs and skill installers.

## Upgrade Guidance

- use a full release tag when you want deterministic installs
- use a moving major tag such as `v0` only when you intentionally want compatible updates
- avoid telling consumers to install from `main` once the skill is in real use
