from __future__ import annotations

from types import SimpleNamespace

from commands.core.guild_list import EMBED_TITLE_PREFIX, build_guild_list_embed


def test_guild_list_embed_sorts_and_counts():
    guilds = [
        SimpleNamespace(name="Zeta", id=3),
        SimpleNamespace(name="Alpha", id=1),
        SimpleNamespace(name="beta", id=2),
    ]
    embed = build_guild_list_embed(guilds)
    assert embed.title == "Servers (3)"
    assert embed.title.startswith(EMBED_TITLE_PREFIX)
    assert embed.description is not None
    assert embed.description.index("Alpha") < embed.description.index("beta")
    assert embed.description.index("beta") < embed.description.index("Zeta")
    assert "`1`" in embed.description
    assert "`2`" in embed.description
    assert "`3`" in embed.description


def test_guild_list_embed_empty():
    embed = build_guild_list_embed([])
    assert embed.title == "Servers (0)"
    assert embed.description == "No servers."


def test_guild_list_embed_truncates_long_list():
    guilds = [
        SimpleNamespace(name=f"Guild {i:04d} " + ("x" * 80), id=i)
        for i in range(200)
    ]
    embed = build_guild_list_embed(guilds)
    assert embed.title == "Servers (200)"
    assert embed.description is not None
    assert len(embed.description) <= 4096
    assert "more" in embed.description
