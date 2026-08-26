# SemVer bump rules

Follow [Semantic Versioning 2.0.0](https://semver.org). Public surface = user-visible behavior of the site, app, or WordPress plugin (admin UI, front end, REST/public PHP API, stored options), not internal file structure.

## Precedence

One version per git commit, not per edit. If the commit mixes change types, use the highest bump:

breaking → major (or minor while `0.x`)  
feature → minor  
fix → patch  
docs / chore → none

## `0.x` vs `1.x`

- `0.y.z` is initial development. Anything may change.
- In `0.x`, incompatible changes increment `y`, not the major version.
- Do not jump to `1.0.0` on your own. Wait for the user to call it stable or production.

## What is breaking

Treat as breaking (major, or minor in `0.x`):

- Removing a user-facing feature, page, route, setting, or button people already use
- Changing a URL, public API, REST route, stored data shape, option key, or consent/storage key in a way that resets or migrates users
- Requiring action from existing users or site admins to keep the same behavior

A visual redesign that keeps the same pages and actions is **minor**, not breaking.

## What is not a bump

Leave these in `[Unreleased]` under **Docs** (or skip changelog if there is nothing user-facing):

- README, comments, types-only, lint/format
- Refactors that do not change behavior
- Test-only changes
- Recreating a missing changelog file

## Same-day versions

Multiple **commits** on the same day each get their own version (`1.2.0` then `1.2.1`). Do not amend an already-cut header. Do not bump between commits.

## Reading the current version

**WordPress plugin:** use the bootstrap file `Version:` header. `Stable tag:` and `*_VERSION` must match it after the bump.

**Otherwise:** parse the highest `## [X.Y.Z]` header in the changelog. Ignore `[Unreleased]`. Ignore dates.

If sources disagree before the bump, the plugin header wins on a WordPress plugin; the changelog wins everywhere else, unless the user says otherwise.

## Runtime and deployment markers

Some projects keep a separate release identifier for startup logs, status
messages, health checks, or deployment fallbacks. These are version sources
when they identify the deployed release.

Examples:

- `DEPLOY_MARKER = "v4.9.0"` → update to the new release as `"v4.19.0"`
- `APP_VERSION = "4.9.0"` → update to `"4.19.0"`
- `__version__ = "4.9.0"` → update to `"4.19.0"`

Search for the old version and inspect each match. Synchronize release markers
in the same commit as the changelog. Preserve a leading `v` or other existing
format.

Do not update values that represent a data envelope, database schema,
migration, API protocol, dependency, fixture, or historical release. When the
purpose is unclear, inspect its callers and ask rather than guessing.
