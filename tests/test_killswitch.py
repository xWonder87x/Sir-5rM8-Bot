from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.core.killswitch import (
    KillswitchActive,
    KillswitchCog,
    interaction_command_name,
    killswitch_owner_user_id,
)


def test_interaction_command_name() -> None:
    interaction = SimpleNamespace(data={"name": "help", "type": 1})
    assert interaction_command_name(interaction) == "help"  # type: ignore[arg-type]
    assert interaction_command_name(SimpleNamespace(data=None)) is None  # type: ignore[arg-type]


def test_killswitch_owner_from_restart_notify() -> None:
    owner = killswitch_owner_user_id()
    assert owner is not None
    assert owner > 0


@pytest.mark.asyncio
async def test_killswitch_blocks_other_commands_when_on() -> None:
    bot = MagicMock()
    cog = KillswitchCog(bot)
    cog._enabled = True

    other = MagicMock()
    other.data = {"name": "help"}
    with pytest.raises(KillswitchActive):
        await cog._killswitch_interaction_check(other)

    ks = MagicMock()
    ks.data = {"name": "killswitch"}
    assert await cog._killswitch_interaction_check(ks) is True


@pytest.mark.asyncio
async def test_killswitch_allows_all_when_off() -> None:
    bot = MagicMock()
    cog = KillswitchCog(bot)
    cog._enabled = False
    interaction = MagicMock()
    interaction.data = {"name": "help"}
    assert await cog._killswitch_interaction_check(interaction) is True


@pytest.mark.asyncio
async def test_killswitch_command_owner_only_and_toggles() -> None:
    bot = MagicMock()
    cog = KillswitchCog(bot)
    cog._enabled = False
    owner_id = killswitch_owner_user_id()
    assert owner_id is not None

    owner = MagicMock()
    owner.user = MagicMock()
    owner.user.id = owner_id
    owner.response = AsyncMock()
    mode = MagicMock()
    mode.value = "on"

    with patch.object(cog, "_persist", new_callable=AsyncMock) as persist:
        await cog.killswitch.callback(cog, owner, mode)
        persist.assert_awaited_once_with(True)
        owner.response.send_message.assert_awaited()

    stranger = MagicMock()
    stranger.user = MagicMock()
    stranger.user.id = 1
    stranger.response = AsyncMock()
    with patch.object(cog, "_persist", new_callable=AsyncMock) as persist:
        await cog.killswitch.callback(cog, stranger, mode)
        persist.assert_not_awaited()
        stranger.response.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_killswitch_on_fails_when_persist_fails() -> None:
    bot = MagicMock()
    cog = KillswitchCog(bot)
    cog._enabled = False
    owner_id = killswitch_owner_user_id()
    assert owner_id is not None

    owner = MagicMock()
    owner.user = MagicMock()
    owner.user.id = owner_id
    owner.response = AsyncMock()
    mode = MagicMock()
    mode.value = "on"

    with patch.object(cog, "_persist", new_callable=AsyncMock, return_value=False):
        await cog.killswitch.callback(cog, owner, mode)
        owner.response.send_message.assert_awaited()
        assert cog._enabled is False
        msg = owner.response.send_message.await_args.args[0]
        assert "off" in msg.lower()
