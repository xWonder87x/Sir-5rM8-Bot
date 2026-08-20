"""Shared Postgres REST client factory for per-bot JWT auth."""
from __future__ import annotations

from typing import Any

from db._base import (
    get_postgrest_anon_key,
    get_postgrest_jwt,
    get_postgrest_key,
    get_postgrest_url,
)


def create_bot_postgrest_client() -> Any:
    from supabase import ClientOptions, create_client

    url = get_postgrest_url()
    if not url:
        raise RuntimeError("POSTGREST_URL is not set")

    api_key = get_postgrest_key()
    bot_jwt = get_postgrest_jwt()
    publishable = get_postgrest_anon_key()

    if bot_jwt and publishable:
        opts = ClientOptions(headers={"Authorization": f"Bearer {bot_jwt}"})
        return create_client(url, publishable, opts)

    if api_key:
        return create_client(url, api_key)

    raise RuntimeError(
        "Postgres REST is not configured: set POSTGREST_KEY or "
        "POSTGREST_JWT + POSTGREST_ANON_KEY"
    )
