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

## 5. Admin Tools

| Command | Description |
|---------|-------------|
| `/say [message]` | Repeats a message *(Admin)* |

---

## Quick Start Checklist

- [ ] Invite the bot
- [ ] Try `/rates` and `/serverstatus server:5313`
- [ ] *(Optional)* Set up rate notifications with `/set_rate_channel`
- [ ] Explain karma to your community — `/karma` for helpful members

---

*Need help? Contact the bot developer or check the [Terms of Service](../TERMS_OF_SERVICE.md).*

*Sir-5rM8 is not affiliated with Studio Wildcard ![Studio Wildcard](../src/wildcard.png). ARK: Survival Evolved, ARK: Survival Ascended, and related marks are trademarks of Studio Wildcard.*
