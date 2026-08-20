#!/usr/bin/env python3
"""Copy Sir-5rM8 data from the legacy Supabase project into Discord Bots."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.migrate_supabase import (  # noqa: E402
    MigrationError,
    preview_old_supabase_migration,
    run_old_supabase_migration,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate data from legacy Sir-5rM8 Supabase into Discord Bots."
    )
    parser.add_argument("--apply", action="store_true", help="Write to Discord Bots.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Discord Bots rows.")
    args = parser.parse_args()

    try:
        summary = preview_old_supabase_migration()
    except MigrationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print(summary.format("Legacy Supabase source"))
    if not args.apply:
        print("\nDry run only — re-run with --apply to migrate.")
        return

    try:
        result = run_old_supabase_migration(force=args.force)
    except MigrationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("\nMigration applied successfully.")
    print(result.source.format("Imported into Discord Bots"))
    print("\nDiscord Bots row counts:", result.database_counts)


if __name__ == "__main__":
    main()
