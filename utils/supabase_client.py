"""Shared Supabase client factory for per-bot JWT auth."""
from __future__ import annotations

import os
from typing import Any


def create_bot_supabase_client() -> Any:
    from supabase import ClientOptions, create_client

    url = (os.environ.get("SUPABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")

    api_key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or ""
    ).strip()
    bot_jwt = (os.environ.get("SUPABASE_BOT_JWT") or "").strip()
    publishable = (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    ).strip()

    if bot_jwt and publishable:
        opts = ClientOptions(headers={"Authorization": f"Bearer {bot_jwt}"})
        return create_client(url, publishable, opts)

    if api_key:
        return create_client(url, api_key)

    raise RuntimeError(
        "Supabase not configured: set SUPABASE_SERVICE_KEY or "
        "SUPABASE_BOT_JWT + SUPABASE_PUBLISHABLE_KEY"
    )
