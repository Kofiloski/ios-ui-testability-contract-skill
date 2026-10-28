---
summary: Maintain the canonical testability skill and toolkit copy while keeping native Simulator exploration separate from XCTest contract verification.
read_when:
  - Updating native Xcode guidance or the testability verification loop
  - Synchronizing the skill with ios-release-quality-toolkit
---

# Skill maintenance

`skills/ios-ui-testability-contract/` is the canonical installable skill. The root `SKILL.md` forwards legacy installs to it. `ios-release-quality-toolkit` embeds a separate copy: a release in either repository does not update the other repository or already installed skills. Compare and synchronize the relevant instructions, references, and CLI pin when releasing changes.

Native Xcode Simulator tools can help reproduce an issue and gather screenshots. Discover their schemas at runtime and select the intended scheme and Simulator. A successful touch action does not prove identifier uniqueness, XCTest element type, or query resolution. Preserve inspection through the failing automation tool and replay of the original path as the completion standard.

Run `./scripts/check-skill.sh`, the skill-creator validator for the nested package, and `docs-list . --strict`. Keep package, runtime, citation, release-tag, and ephemeral CLI pin versions aligned. Verify GitHub release and PyPI publication separately; neither establishes that a user's installed copy has been upgraded.
