# Remote Install

Use this when you publish `ios-ui-testability-contract` as its own Git repository and want other people to consume it without copying files manually.

## Repository Contract

The repository root should contain:

- `pyproject.toml`
- `SKILL.md`
- `README.md`
- `REMOTE_INSTALL.md`
- `PUBLISHING.md`
- `src/`
- `references/`
- `scripts/`
- `tests/`
- optional `examples/`

Point your remote skill installer at the repository root, not a nested subfolder.

The same repository can also be installed as a Python package to expose the `ios-ui-testability` CLI. The CLI is a helper surface; the skill workflow remains the source of judgment for deciding what code or scenario changes to make.

## Versioning

Recommend one of these pins:

- exact release tag such as `v0.1.0`
- moving major tag such as `v0`

Avoid telling consumers to install from `main` once the skill is used outside local experiments.

## Suggested Consumer Flow

1. install the skill from the repository root at a release tag
2. run the skill against a local artifact bundle or failing repo
3. upgrade by moving the pinned tag only after rerunning the sample checks or one local smoke repro

## Suggested Maintainer Flow

1. run `./scripts/check-skill.sh`
2. commit the change
3. tag a release
4. optionally move a major tag such as `v0`
5. tell consumers to update their pin, not to reinstall from `main`
