---
name: semver
description: >-
  Applies Semantic Versioning once per git commit, not on each edit. Cuts a
  dated changelog entry and, in WordPress plugins, keeps the plugin header,
  *_VERSION constant, readme.txt Stable tag, and runtime/deployment markers in
  sync. Use when creating a commit, committing changes, or when the user
  mentions version, semver, bump, changelog, or release.
---

# SemVer

Bump the version **once per git commit**, never on each code edit.

While work is in progress, leave user-visible changes in `[Unreleased]` (`changelog-keeper`). Do not rename `[Unreleased]`, do not bump plugin headers, and do not cut a dated version until the user asks to commit (or you are creating the commit).

Docs-only, comments, formatting, tests, and internal refactors with no user-visible behavior still go to `[Unreleased]` and do **not** bump even at commit time.

## Detect the project

A **WordPress plugin** has a bootstrap PHP file whose header includes `Plugin Name:` and `Version:`. Treat it as a plugin even if it also has `CHANGELOG.md`.

Everything else uses the generic changelog flow below. WordPress extras: [references/wordpress.md](references/wordpress.md).

## File

**Generic projects:** existing `CHANGELOG.md` or `docs/CHANGELOG.md`. If neither exists, create `docs/CHANGELOG.md` from the template in this skill when the first version-affecting change lands — keep it on `[Unreleased]` until commit.

**WordPress plugins:** do **not** create `docs/CHANGELOG.md`. At commit time, cut `== Changelog ==` in `readme.txt` (and `.wordpress-org/README.txt` if present). If the plugin already has `CHANGELOG.md`, cut that too so both stay aligned.

Match the file's existing section names. If creating a new Keep a Changelog file, use **Features**, **Fixes**, and **Docs**.

## Discover version sources

Before committing a version-affecting change, search the repository for the current version and version-like identifiers. In addition to the changelog, inspect runtime and deployment code for constants such as `VERSION`, `__version__`, `APP_VERSION`, `BUILD_VERSION`, `RELEASE_VERSION`, and `DEPLOY_MARKER`.

If a marker is used to display, identify, or fall back to the deployed release, synchronize it to the new version in the same commit. Preserve the repository's format, including a leading `v` (`v4.19.0`) when that is how the marker is written. In ALICE, `main.py`'s `DEPLOY_MARKER` is a release marker and must not drift from the changelog version.

Do not change protocol/data-format versions, dependency versions, migration/schema versions, historical changelog entries, or test fixtures unless the change specifically requires it. If a version-like value is ambiguous, inspect its callers and ask before changing it.

## Classify the bump

At commit time, read the current version (changelog header, or the plugin `Version:` header if this is a WordPress plugin). Classify **everything in this commit plus `[Unreleased]`**, then:

| Change | Bump |
| --- | --- |
| Breaking: removed or incompatible user-facing behavior | major |
| New or changed user-facing behavior (features, copy, UI, integrations) | minor |
| Bug fix, broken link, accessibility repair, regression | patch |
| Docs, comments, formatting, changelog scaffolding, no user-visible change | none |

When the commit mixes change types, bump once using the highest-impact change.

While the major version is `0`, breaking changes bump **minor**, not major. Move to `1.0.0` only when the user says the project is stable or production.

If there is no version yet: first minor → `0.1.0`, first patch → `0.0.1`.

See [references/bump-rules.md](references/bump-rules.md) for edge cases.

## Cut the version

In the same turn as the **commit**, before `git commit`:

1. Compute `X.Y.Z` from the table above.
2. Fold `[Unreleased]` bullets into this cut.
3. Insert this block directly below `[Unreleased]`:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Features

### Fixes

### Docs
```

4. Put this commit's bullets (and any previously unreleased bullets) in the right sections. Drop empty sections from the cut version.
5. Leave a fresh empty `[Unreleased]` with all three section headers at the top.
6. Use today's date (`YYYY-MM-DD`). One bullet per user-visible change, plain language, same style as `changelog-keeper`.
7. Stage the changelog, runtime/deployment markers, and WordPress version files in **this same commit**. Do not make a follow-up commit just for the bump.

**WordPress plugins:** after cutting the changelog, set the same `X.Y.Z` on the bootstrap `Version:` header, the plugin's `*_VERSION` constant in that same file, and `Stable tag:` in `readme.txt`. Do not bump `Requires at least`, `Tested up to`, `Requires PHP`, or a separate `DB_VERSION` / schema constant.

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

Create it when first needed. Cut the first dated version only at commit time.
