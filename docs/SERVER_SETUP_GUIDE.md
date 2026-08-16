# Server Setup Guide

Welcome! This guide helps you get the most out of Sir-5rM8 after adding it to your Discord server.

---

## 1. Invite the Bot

Add Sir-5rM8 to your server using the [invite link](https://discord.com/oauth2/authorize?client_id=1236457243222868010). The bot will request the permissions it needs. Ensure your bot has:

- **Send Messages** — Post in channels
- **Embed Links** — Rich embeds for rates and server status
- **Read Message History** — For slash commands
- **Use Application Commands** — Required for slash commands

---

## 2. ASA Official PVE Rate Fetch & Dynamic Rate Monitoring

**`/rates`** — View live official PVE rates (EXP, Harvesting, Taming, etc.). No setup required.

**Rate notifications** — Get notified automatically when rates change (checked every minute).

### Setup

1. Create a **channel** for rate updates (e.g. `#asa-rates` or `#announcements`)
2. Create a **role** for people who want notifications (e.g. `ASA Rates` or `Rate Watchers`)
3. Run: `/set_rate_channel [channel] [role]` (e.g. `/set_rate_channel #asa-rates @ASA Rates`)
4. Members who want notifications: assign themselves the role

### Management

| Command | Description |
|---------|-------------|
| `/rate_channel_status` | See your current channel and role setup |
| `/clear_rate_channel` | Disable rate notifications for this server |

---

## 3. Server Status

**`/serverstatus [server]`** — Check ASA official server by name or number.

Example: `/serverstatus server:5313` or `/serverstatus server:TheIsland`

Includes an occupancy bar and a player-count history graph (history builds after the first lookup as the bot samples every few minutes).

Returns IP, player count, day, ping, map, and platform.

---

## 4. Karma System

Karma rewards helpful community members. It's **global** (shared across all servers using the bot).

### Commands

| Command | Description |
|---------|-------------|
| `/karma [member] [reason]` | Give 1 karma (reason required; 24h cooldown per person) |
| `/manage_karma action:check [member]` | Check balance (omit member for yourself) |
| `/manage_karma action:history [member]` | View history (admins can view anyone's) |
| `/manage_karma action:remove [member]` | Remove 1 karma *(Admin)* |
| `/manage_karma action:audit` | Recent removals *(Admin)* |

---

## 5. Bothunter (spam trap)

Catch mass-spam bots with a dedicated trap channel. Anyone who posts there is softbanned (default) or banned. Softban bans then unbans so Discord deletes their recent messages.

### Setup

1. Create a channel near the **top** of your channel list (e.g. `#pls-dont-chat-here`) — spam bots often hit the first few channels
2. Ensure Sir-5rM8 has **Ban Members** and its role sits **above** normal member roles
3. Run: `/bothunter channel:#pls-dont-chat-here log_channel:#mod-log action:Softban`
4. Optional experiments: `reinvite`, `timeout_first`, `no_dm`, `no_warning_msg`, `only_recent_delete`
5. Customize copy with `/bothunter-messages` if desired

Run `/bothunter` with no options to see current status. Use `clear:True` to remove the config.

---

## 6. Admin Tools

| Command | Description |
|---------|-------------|
| `/say [message]` | Repeats a message *(Admin)* |

---

## Quick Start Checklist

- [ ] Invite the bot
- [ ] Try `/rates` and `/serverstatus server:5313`
- [ ] *(Optional)* Set up rate notifications with `/set_rate_channel`
- [ ] *(Optional)* Set up bothunter with `/bothunter`
- [ ] Explain karma to your community — `/karma` for helpful members

---

*Need help? Contact the bot developer or check the [Terms of Service](../TERMS_OF_SERVICE.md).*

*Sir-5rM8 is not affiliated with Studio Wildcard <img src="../src/wildcard.png" alt="Studio Wildcard" width="24" height="24" />.*
