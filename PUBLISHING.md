# Publishing

This repository publishes an Agent Skills package, a GitHub release, and an optional Python distribution from the same versioned source.

## Distribution Channels

The GitHub release and PyPI publication serve different consumers:

- the Git tag and GitHub release distribute the Agent Skill and provide immutable source installs for both the skill and CLI
- PyPI distributes only the optional `ios-ui-testability` CLI for `uvx --from ios-ui-testability-contract ios-ui-testability` or `pipx install ios-ui-testability-contract`

Every version receives a GitHub release. PyPI publishing is an additional CI job because OpenID Connect Trusted Publishing must obtain a short-lived identity from GitHub Actions; it is not a separate agent-skill release.

## Repository Shape

Keep these surfaces intact:

- `skills/ios-ui-testability-contract/SKILL.md` and its `agents/` and `references/` directories
- `pyproject.toml` and `src/ios_ui_testability_contract/` for the Python package
- `scripts/` compatibility wrappers and repository checks
- `tests/` fixtures and regression coverage
- `.github/workflows/release.yml` for tags and GitHub releases
- `.github/workflows/publish-pypi.yml` for secretless PyPI publishing

## Pre-Publish Checks

Run:

```bash
./scripts/check-skill.sh
gh skill publish --dry-run "$PWD/skills"
python3 -m pip install .
ios-ui-testability --version
```

The package metadata, runtime `__version__`, CLI version, release tag, and citation metadata must all agree on `X.Y.Z`.

## Configure PyPI Trusted Publishing Once

The workflow intentionally contains no PyPI API token. Before the first PyPI release, create a pending Trusted Publisher at <https://pypi.org/manage/account/publishing/> with:

- PyPI project: `ios-ui-testability-contract`
- GitHub owner: `Kofiloski`
- repository: `ios-ui-testability-contract-skill`
- workflow: `publish-pypi.yml`
- environment: `pypi`

Create the `pypi` environment in GitHub and require maintainer approval for deployments. PyPI can create the project on the first successful publish when the pending publisher matches these values.

The publish workflow separates building from publishing. Only the two-step publish job receives `id-token: write`: it downloads the verified distributions and runs `pypa/gh-action-pypi-publish@release/v1`.

## Release Flow

1. update the package and runtime versions plus `CITATION.cff`
2. run the pre-publish checks
3. commit and push the release changes to the default branch
4. dispatch `.github/workflows/release.yml` with the exact `vX.Y.Z` tag
5. let that workflow validate versions, create or reuse the tag, optionally update `vX`, and create the GitHub release
6. approve the `pypi` environment deployment when the release workflow dispatches the top-level `.github/workflows/publish-pypi.yml` run
7. verify the package page and install it into a clean environment

The release workflow dispatches the PyPI workflow from the repository's current default branch while passing the immutable release tag as `release_tag`. This keeps the publishing machinery current without changing the source being packaged: the build job still checks out the tag and verifies its package, runtime, CLI, and citation versions against that tag.

The GitHub release flow is resumable. An existing semantic tag is accepted only when it resolves to the current commit, an existing release is left intact, and the Trusted Publishing step skips distribution files already present on PyPI. PyPI versions are immutable, so never reuse a package version after it has been uploaded.

To retry PyPI publication for an existing release with the latest safe workflow definition, dispatch from the default branch and pass the exact tag:

```bash
gh workflow run publish-pypi.yml \
  --ref main \
  --field release_tag=v0.4.1
```

The workflow checks out `v0.4.1`; `--ref main` selects only the workflow definition. Replace both values as appropriate if the default branch or release changes.

## Consumer Guidance

- recommend a full release tag for deterministic agent-skill and Git installs
- recommend `uvx --from ios-ui-testability-contract ios-ui-testability` for one-off use
- recommend `pipx install ios-ui-testability-contract` for a persistent command
- use a moving major tag only for consumers who intentionally accept compatible updates
- keep `main` installs limited to evaluation of unreleased changes
