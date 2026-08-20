#!/usr/bin/env python3
"""Standalone read-only Postgres REST connection ping (no db package import)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def main() -> int:
    url = _first_env("POSTGREST_URL", "SUPABASE_URL")
    key = _first_env("POSTGREST_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_KEY", "POSTGREST_JWT", "SUPABASE_BOT_JWT")
    publishable = _first_env("POSTGREST_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY")
    bot_jwt = _first_env("POSTGREST_JWT", "SUPABASE_BOT_JWT")
    if not url or not (key or (publishable and bot_jwt)):
        print(
            "Missing POSTGREST_URL and credentials "
            "(POSTGREST_KEY or POSTGREST_JWT + POSTGREST_ANON_KEY).",
            file=sys.stderr,
        )
        return 1

    try:
        if bot_jwt and publishable:
            from supabase import ClientOptions, create_client

            opts = ClientOptions(headers={"Authorization": f"Bearer {bot_jwt}"})
            client = create_client(url, publishable, opts)
        else:
            from supabase import create_client

            client = create_client(url, key)
        client.table("rate_state").select("id").eq("id", 1).limit(1).execute()
    except Exception as exc:
        print(f"Postgres REST probe failed: {exc}", file=sys.stderr)
        return 1

    print("Postgres REST probe OK (rate_state readable).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
