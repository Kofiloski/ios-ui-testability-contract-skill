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

- exact release tag `vX.Y.Z`, where `X.Y.Z` exactly matches the published Python package version
- moving major tag such as `vX`

Avoid telling consumers to install from `main` once the skill is used outside local experiments.
Prefer the exact release tag for reproducible installs. The moving major tag is only appropriate when consumers explicitly accept compatible updates without changing their pin.

## Suggested Consumer Flow

1. install the skill from the repository root at a release tag
2. run the skill against a local artifact bundle or failing repo
3. upgrade by moving the pinned tag only after rerunning the sample checks or one local smoke repro

## Suggested Maintainer Flow

1. run `./scripts/check-skill.sh`
2. confirm that installed package metadata and `ios-ui-testability --version` both report the same `X.Y.Z` version
3. commit the change
4. tag exactly `vX.Y.Z`
5. optionally move the matching major tag `vX`
6. tell consumers to update their pin, not to reinstall from `main`

The manual release workflow enforces this package/tag match before creating or pushing either tag.
