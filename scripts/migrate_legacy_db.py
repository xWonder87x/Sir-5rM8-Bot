#!/usr/bin/env python3
"""Copy Sir-5rM8 data from a legacy Postgres REST project into Discord Bots."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.migrate_legacy import (  # noqa: E402
    MigrationError,
    preview_legacy_migration,
    run_legacy_migration,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate data from the legacy Sir-5rM8 database into Discord Bots."
    )
    parser.add_argument("--apply", action="store_true", help="Write to Discord Bots.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Discord Bots rows.")
    args = parser.parse_args()

    try:
        summary = preview_legacy_migration()
    except MigrationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print(summary.format("Legacy database source"))
    if not args.apply:
        print("\nDry run only — re-run with --apply to migrate.")
        return

    try:
        result = run_legacy_migration(force=args.force)
    except MigrationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("\nMigration applied successfully.")
    print(result.source.format("Imported into Discord Bots"))
    print("\nDiscord Bots row counts:", result.database_counts)


if __name__ == "__main__":
    main()
