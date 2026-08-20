---
name: semver
description: >-
  Applies Semantic Versioning on every version-affecting code change by cutting
  a dated version in the changelog in the same turn. Use when adding features,
  fixing bugs, making breaking changes, or when the user mentions version,
  semver, bump, changelog, or release.
---

# SemVer

On every **version-affecting** code change, cut a new changelog version in the same turn. Do not leave those changes in `[Unreleased]`.

This overrides `changelog-keeper`'s "do not auto-release" rule for product changes. Docs-only, comments, formatting, and internal refactors with no user-visible behavior still go to `[Unreleased]` and do **not** bump.

## File

Use the existing changelog, in this order: `CHANGELOG.md`, `docs/CHANGELOG.md`. If neither exists, create `docs/CHANGELOG.md` from the template in this skill.

Match the file's existing section names. If creating a new file, use **Features**, **Fixes**, and **Docs**.

## Classify the bump

Read the current highest version header. Then:

| Change | Bump |
| --- | --- |
| Breaking: removed or incompatible user-facing behavior | major |
| New or changed user-facing behavior (features, copy, UI, integrations) | minor |
| Bug fix, broken link, accessibility repair, regression | patch |
| Docs, comments, formatting, changelog scaffolding, no user-visible change | none |

When several edits land in one turn, bump once using the highest-impact change.

While the major version is `0`, breaking changes bump **minor**, not major. Move to `1.0.0` only when the user says the project is stable or production.

If there is no version yet: first minor → `0.1.0`, first patch → `0.0.1`.

See [references/bump-rules.md](references/bump-rules.md) for edge cases.

## Cut the version

In the same turn as the code edit:

1. Compute `X.Y.Z` from the table above.
2. If `[Unreleased]` already has bullets, include them in this cut.
3. Insert this block directly below `[Unreleased]`:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Features

### Fixes

### Docs
```

4. Put this turn's bullets (and any previously unreleased bullets) in the right sections. Drop empty sections from the cut version.
5. Leave a fresh empty `[Unreleased]` with all three section headers at the top.
6. Use today's date (`YYYY-MM-DD`). One bullet per user-visible change, plain language, same style as `changelog-keeper`.

Do not update `package.json`, git tags, or GitHub releases unless the user asks.

## Missing changelog

```markdown
# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org).

## [Unreleased]

### Features

### Fixes

### Docs
```

Create it, then immediately cut the first version for the current change.
