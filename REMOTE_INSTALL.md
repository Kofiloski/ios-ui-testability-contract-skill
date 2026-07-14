# Remote Install

The repository publishes two related surfaces:

- an Agent Skills package at `skills/ios-ui-testability-contract/`
- a Python package that exposes the optional `ios-ui-testability` CLI

The skill can diagnose and repair a UI automation contract without the CLI. Install both when you want deterministic inventory and artifact-triage commands alongside the agent workflow.

## Install the Agent Skill

GitHub CLI discovers the canonical skill directory and can install it for supported coding agents. Pin an exact release for reproducibility:

```bash
gh skill install Kofiloski/ios-ui-testability-contract-skill \
  ios-ui-testability-contract@vX.Y.Z \
  --agent codex \
  --scope user
```

Replace `vX.Y.Z` with an available release that contains the `skills/ios-ui-testability-contract/` layout. Use `--scope project` when the skill should be checked into or available only from one repository.

Preview the same version before installing:

```bash
gh skill preview Kofiloski/ios-ui-testability-contract-skill \
  ios-ui-testability-contract@vX.Y.Z
```

GitHub CLI injects source-tracking metadata into the installed copy so `gh skill update` can detect new releases. The canonical checked-in `SKILL.md` intentionally contains only the portable `name` and `description` frontmatter fields.

## Install the CLI

Until the package is available from PyPI, install its exact Git tag with `pipx`:

```bash
pipx install "git+https://github.com/Kofiloski/ios-ui-testability-contract-skill.git@vX.Y.Z"
ios-ui-testability --version
```

Once a release has been published to PyPI through Trusted Publishing, the shorter install is:

```bash
pipx install ios-ui-testability-contract
```

## Versioning

- package version `X.Y.Z` is released as Git tag `vX.Y.Z`
- exact tags are recommended for deterministic installs
- moving major tags such as `vX` are for consumers who explicitly accept compatible updates
- avoid installing from `main` outside evaluation or pre-release testing

## Maintainer Validation

From the repository root, validate both surfaces before publishing:

```bash
./scripts/check-skill.sh
gh skill publish --dry-run "$PWD/skills"
```

The Python package remains the implementation source for the CLI. The skill directory contains portable instructions and references, so a GitHub skill install does not require copying the package source tree.
