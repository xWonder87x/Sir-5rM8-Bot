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

## 2. Rate Notifications (Optional)

Get notified automatically when ARK official server rates change (checked every minute).

### Setup

1. Create a **channel** for rate updates (e.g. `#asa-rates` or `#announcements`)
2. Create a **role** for people who want notifications (e.g. `ASA Rates` or `Rate Watchers`)
3. Run:
   ```
   /set_rate_channel [channel] [role]
   ```
   Example: `/set_rate_channel #asa-rates @ASA Rates`

4. Members who want notifications: assign themselves the role (or have admins assign it)

### Management

| Command | Description |
|---------|-------------|
| `/rate_channel_status` | See your current channel and role setup |
| `/clear_rate_channel` | Disable rate notifications for this server |

---

## 3. Karma System

Karma rewards helpful community members. It’s **global** (shared across all servers using the bot).

### How It Works

- **Give karma:** `/karma action:add [member] [reason]` — Anyone can give 1 karma with a reason. 24-hour cooldown per person you give karma to.
- **Remove karma:** `/karma action:remove [member]` — Admins only.
- **Check balance:** `/manage_karma action:check [member]` — Omit member to check yourself.
- **View history:** `/manage_karma action:history [member]` — View your own history; admins can view anyone’s.
- **Audit log:** `/manage_karma action:audit` — Admins only. Last 10 karma removals.

### Quick Reference

| Command | Description |
|---------|-------------|
| `/karma action:add member:@User reason:Helped with taming` | Give 1 karma (reason required) |
| `/karma action:remove member:@User` | Remove 1 karma *(Admin)* |
| `/manage_karma action:check` | Your karma balance |
| `/manage_karma action:check member:@User` | Someone else’s balance |
| `/manage_karma action:history` | Your karma history |
| `/manage_karma action:history member:@User` | Their history *(Admin)* |
| `/manage_karma action:audit` | Recent removals *(Admin)* |

---

## 4. Server Status Lookup

Check ASA official server status by name or number:

```
/serverstatus server:5313
/serverstatus server:TheIsland
```

Returns IP, player count, day, ping, map, and platform.

---

## 5. Current Rates

View live official PVE rates (EXP, Harvesting, Taming, etc.):

```
/rates
```

No setup required.

---

## 6. Admin Commands

| Command | Description |
|---------|-------------|
| `/say [message]` | Repeats a message *(Admin)* |
| `/set_rate_channel [channel] [role]` | Configure rate notifications |
| `/rate_channel_status` | Show rate notification setup |
| `/clear_rate_channel` | Remove rate notifications |

---

## Quick Start Checklist

- [ ] Invite the bot
- [ ] Try `/rates` and `/serverstatus server:5313`
- [ ] *(Optional)* Set up rate notifications with `/set_rate_channel`
- [ ] Explain karma to your community — `/karma action:add` for helpful members

---

*Need help? Contact the bot developer or check the [Terms of Service](../TERMS_OF_SERVICE.md).*
