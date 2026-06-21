#!/usr/bin/env python3
"""Standalone read-only Supabase connection ping (no db package import)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_BOT_JWT")
    )
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not (key or (publishable and os.environ.get("SUPABASE_BOT_JWT"))):
        print(
            "Missing SUPABASE_URL and credentials "
            "(SUPABASE_SERVICE_KEY or SUPABASE_BOT_JWT + publishable key).",
            file=sys.stderr,
        )
        return 1

    try:
        if os.environ.get("SUPABASE_BOT_JWT") and publishable:
            from supabase import ClientOptions, create_client

            opts = ClientOptions(headers={"Authorization": f"Bearer {os.environ['SUPABASE_BOT_JWT']}"})
            client = create_client(url, publishable, opts)
        else:
            from supabase import create_client

            client = create_client(url, key)
        client.table("rate_state").select("id").eq("id", 1).limit(1).execute()
    except Exception as exc:
        print(f"Supabase probe failed: {exc}", file=sys.stderr)
        return 1

    print("Supabase probe OK (rate_state readable).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
