# SemVer bump rules

Follow [Semantic Versioning 2.0.0](https://semver.org). Public surface = user-visible behavior of the site or app, not internal file structure.

## Precedence

One version per turn. If the turn mixes change types, use the highest bump:

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

- Removing a user-facing feature, page, route, or button people already use
- Changing a URL, public API, stored data shape, or consent/storage key in a way that resets or migrates users
- Requiring action from existing users to keep the same behavior

A visual redesign that keeps the same pages and actions is **minor**, not breaking.

## What is not a bump

Leave these in `[Unreleased]` under **Docs** (or skip changelog if there is nothing user-facing):

- README, comments, types-only, lint/format
- Refactors that do not change behavior
- Test-only changes
- Recreating a missing changelog file

## Same-day versions

Multiple turns on the same day each get their own version (`1.2.0` then `1.2.1`). Do not amend an already-cut header.

## Reading the current version

Parse the highest `## [X.Y.Z]` header in the changelog. Ignore `[Unreleased]`. Ignore dates. If headers disagree with any other version source, the changelog wins unless the user says otherwise.
