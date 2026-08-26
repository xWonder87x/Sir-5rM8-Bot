# WordPress plugin versions

Detect a plugin from a PHP file whose docblock has `Plugin Name:` and `Version:`. Typical layout: `odi-tool.php`, `inncha-ai.php`, `webpartner-tools.php` at the repo root.

Keep SemVer bump rules from [bump-rules.md](bump-rules.md). WordPress.org accepts `X.Y.Z`.

## Files to bump together

Set the **same** `X.Y.Z` in the commit, not on each edit:

| Location | What to change |
| --- | --- |
| Bootstrap PHP header | `* Version:           1.0.1` (keep the file's spacing) |
| Bootstrap PHP constant | `define( 'PLUGIN_VERSION', '1.0.1' );` or `ODI_TOOL_VERSION` / `INNCHA_AI_VERSION` in that same file |
| `readme.txt` | `Stable tag: 1.0.1` |
| `readme.txt` changelog | Newest `= 1.0.1 =` section under `== Changelog ==` |
| `.wordpress-org/README.txt` | Same Stable tag + changelog if that file exists |
| `CHANGELOG.md` | Cut Keep a Changelog **only if the file already exists** |

Do **not** create `docs/CHANGELOG.md` for a plugin that already uses `readme.txt`.

Do **not** bump:

- `Requires at least`, `Tested up to`, `Requires PHP`
- `DB_VERSION`, schema versions, or migration constants
- Nested third-party modules that ship their own `Plugin Name` header (e.g. bundled `widget-css-classes.php`) unless you edited that module

GitHub updaters compare the plugin constant to the latest release. If header and constant drift, updates break.

## `readme.txt` changelog

Newest first. Match existing bullet style (`*` in these plugins). One user-visible change per bullet, plain language.

```text
== Changelog ==

= 1.0.1 =
* Fix Greeklish conversion skipping pages with mixed scripts.

= 1.0.0 =
* Initial release.
```

If the plugin uses Features / Fixes / Docs in `CHANGELOG.md`, keep that file's sections. In `readme.txt`, still use a flat `*` list (WordPress.org does not use those headings).

## Upgrade notice

Skip `== Upgrade Notice ==` on patch and minor. On a **major** (or `0.x` breaking) bump, add a one-line notice under `= X.Y.Z =` telling admins what they must do.

## Current version

Read `Version:` from the bootstrap header, not `readme.txt` first. After the bump, header, constant, and Stable tag must be identical.
