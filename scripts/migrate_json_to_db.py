#!/usr/bin/env python3
"""
Migrate Sir-5rM8 data from local JSON files to Postgres REST.

Usage:
  python scripts/migrate_json_to_db.py              # dry run (default)
  python scripts/migrate_json_to_db.py --apply      # write to the database
  python scripts/migrate_json_to_db.py --apply --force  # overwrite existing DB rows

Stop the bot before migrating so JSON files are not being written mid-import.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.migrate_json import (  # noqa: E402
    MigrationError,
    preview_migration,
    run_migration,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate JSON bot data to the remote database.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write data to the database (default is dry run only).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow migration when the database already has rows.",
    )
    args = parser.parse_args()

    try:
        summary = preview_migration()
    except MigrationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print(summary.format("JSON source"))

    if not args.apply:
        print("\nDry run only — no changes written. Re-run with --apply to migrate.")
        return

    print("\nConnecting to the remote database...")
    try:
        result = run_migration(force=args.force)
    except MigrationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("\nMigration applied successfully.")
    print(result.source.format("Imported from JSON"))
    print("\nDatabase row counts:", result.database_counts)
    print(
        "\nNext steps:\n"
        "  1. Verify counts look correct in the table editor.\n"
        "  2. Confirm startup log shows: Storage backend: Postgres REST ... connection OK\n"
        "  3. Keep JSON files as backup until you are satisfied, then archive them."
    )


if __name__ == "__main__":
    main()
