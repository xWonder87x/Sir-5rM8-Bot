from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from functions.owner_notify import build_guild_join_embed


class _User:
    def __init__(self, user_id: int, name: str) -> None:
        self.id = user_id
        self._name = name

    def __str__(self) -> str:
        return self._name


def test_guild_join_embed_includes_core_fields():
    created = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    guild = SimpleNamespace(
        id=111,
        name="Ark Tribe",
        member_count=42,
        owner_id=222,
        owner=None,
        created_at=created,
        description="PVE cluster",
        icon=SimpleNamespace(url="https://example.com/icon.png"),
        vanity_url_code="arktribe",
        premium_tier=2,
        premium_subscription_count=7,
        preferred_locale="en-US",
        verification_level=SimpleNamespace(name="medium"),
        text_channels=[1, 2, 3],
        voice_channels=[1],
        features=["COMMUNITY", "NEWS"],
    )
    embed = build_guild_join_embed(
        guild,
        owner=_User(222, "Owner#0001"),
        added_by=_User(333, "Admin#0002"),
        bot_guild_count=5,
    )
    fields = {f.name: f.value for f in embed.fields}
    assert embed.title == "Added to a Discord server"
    assert embed.description == "Ark Tribe"
    assert fields["Server ID"] == "`111`"
    assert fields["Members"] == "42"
    assert "Level 2" in fields["Boosts"]
    assert "Owner#0001" in fields["Owner"]
    assert "`222`" in fields["Owner"]
    assert "Admin#0002" in fields["Added by"]
    assert "<t:1705320000:F>" in fields["Created"]
    assert fields["Description"] == "PVE cluster"
    assert "discord.gg/arktribe" in fields["Vanity URL"]
    assert "Medium" in fields["Locale · verification · channels"]
    assert embed.footer.text == "Now in 5 servers"
    assert embed.thumbnail.url == "https://example.com/icon.png"
