---
summary: Maintain the canonical testability skill and toolkit copy while keeping native Simulator exploration separate from XCTest contract verification.
read_when:
  - Updating native Xcode guidance or the testability verification loop
  - Synchronizing the skill with ios-release-quality-toolkit
---

# Skill maintenance

`skills/ios-ui-testability-contract/` is the canonical installable skill. The root `SKILL.md` forwards legacy installs to it. `ios-release-quality-toolkit` embeds a separate copy: a release in either repository does not update the other repository or already installed skills. Compare and synchronize the relevant instructions, references, and CLI pin when releasing changes.

Native Xcode Simulator tools can help reproduce an issue and gather screenshots. Discover their schemas at runtime and select the intended scheme and Simulator. A successful touch action does not prove identifier uniqueness, XCTest element type, or query resolution. Preserve inspection through the failing automation tool and replay of the original path as the completion standard.

The verification reference also covers optional bounded app logs, relevant persisted-state reads, and focused runtime inspection when the cause remains unclear. Correlate them with the same reproduction; keep raw state local and instrumented observations separate. These diagnostics add no jailbreak/injection dependency and do not change the CLI, triage buckets, or inspect/replay completion standard.

Run `./scripts/check-skill.sh`, the skill-creator validator for the nested package, and `docs-list . --strict`. Keep package, runtime, citation, release-tag, and ephemeral CLI pin versions aligned. Verify GitHub release and PyPI publication separately; neither establishes that a user's installed copy has been upgraded.

The local November 4, 2026 Firefox and DuckDuckGo source evaluation exposed expensive identifier lexing of generated files without identifier tokens. The source scanner now skips those files before lexing; files containing Swift/property or Objective-C setter tokens still use the existing parser. The large generated-companion regression test retains both forms of real identifier. Replayed reports matched the original reports exactly: Firefox took 2.40 seconds versus 84.39, and DuckDuckGo 4.29 seconds versus 99.70 on this host. These are dated local measurements, not a performance guarantee or evidence that a published CLI already includes the change.
