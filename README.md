```
  ███████╗██╗██████╗ 
  ██╔════╝██║██╔══██╗
  ███████╗██║██████╔╝
  ╚════██║██║██╔══██╗
  ███████║██║██║  ██║
  ╚══════╝╚═╝╚═╝  ╚═╝
     5rM8 · Discord Bot
```

# **Sir-5rM8**

**Version:** 1.2.0

### *Making the community better, one command at a time.*

*A feature-rich Discord bot for your ARK: Survival Ascended discord community.*

---

## Add to Your Server

**Invite Sir-5rM8 to your Discord server** — no setup required. Just add the bot and start using it.

[**Add Sir-5rM8 to Discord**](https://discord.com/oauth2/authorize?client_id=1236457243222868010)

**[📖 Server Setup Guide](docs/SERVER_SETUP_GUIDE.md)** — For server owners: configure rate notifications, in-game ARK notices, karma, and more.

---

## ✨ Features

### ASA Official PVE Rate Fetch & Dynamic Rate Monitoring

| Command | Description |
|---------|-------------|
| `/rates` | Live server rates: EXP, Harvesting, Taming, Mating, Egg Hatch, Baby Mature, Imprint & Cuddle. **Subscribe** / **Unsubscribe** for the alert role |
| `/set_rate_channel [channel] [role]` | Set channel for automatic rate updates *(Admin only)*|
| `/rate_channel_status` | Show current rate notification setup *(Admin only)*|
| `/clear_rate_channel` | Remove rate notifications for this server *(Admin only)*|

### Server Status

| Command | Description |
|---------|-------------|
| `/serverstatus [server]` | Check ASA official server from Wildcard's list; occupancy bar + optional BattleMetrics uptime graph. If the server is down, tap **Notify me when it's up** or **Report Outage** |

### Official in-game notifications

| Command | Description |
|---------|-------------|
| `/arknotifications` | Pick a channel for the same notices Wildcard posts inside ASA *(Admin only)*. Includes a **Disable** button |

### Karma System

| Command | Description |
|---------|-------------|
| `/karma [member] [reason]` | Give 1 karma (24h cooldown per person) |
| `/manage_karma action:check [member]` | Check karma balance |
| `/manage_karma action:history [member]` | View karma history |
| `/manage_karma action:remove [member]` | Remove 1 karma *(Admin only)* |
| `/manage_karma action:audit` | Recent removals *(Admin only)* |

### Bothunter (spam trap)

Catch mass-spam bots by monitoring a dedicated trap channel. Anyone who posts there is softbanned (default) or banned. Commands renamed from the upstream [honeypot](https://github.com/RiskyMH/honeypot) bot.

| Command | Description |
|---------|-------------|
| `/bothunter` | Configure trap channel, log channel, action, and options *(Admin)* |
| `/bothunter-messages` | Customize warning / DM / log messages *(Admin)* |

**Setup tips:** place the trap near the top of your channel list, keep the bot’s role above member roles, and ensure it has **Ban Members**. Softban bans then unbans so Discord deletes recent messages.

### Admin Tools

| Command | Description |
|---------|-------------|
| `/say [message]` | Repeats a message |

### Coming soon features

- **XP Leaderboard & Giveaway**
- **Auto Partner Index**
- **Auction Monitoring**

---

## Self-hosting

**Requirements:** Python **3.10+**, a Discord bot token in `.env` (`TOKEN=...`).

```bash
pip install -r requirements.txt
python main.py
```

Optional storage: **Postgres** (`DATABASE_URL`) preferred, else Postgres REST — see [postgres/README.md](postgres/README.md) and [docs/DATABASE.md](docs/DATABASE.md).

**Developer:** After code changes without a full restart, bot owner or admins can run `!reload` in Discord to reload cogs and re-sync slash commands.

---

## 📄 License

This project is licensed under the GNU GPL v3 — see the [LICENSE](LICENSE) file for details.

---

**Built with** ❤ *for ARK Discord communities*. *Sir-5rM8 is not affiliated with Studio Wildcard.*

[Terms of Service](TERMS_OF_SERVICE.md) · [Privacy Policy](PRIVACY_POLICY.md)

<a href="https://www.buymeacoffee.com/xwonder87x" target="_blank" rel="noopener noreferrer" aria-label="Buy me a coffee"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" width="150" /></a>