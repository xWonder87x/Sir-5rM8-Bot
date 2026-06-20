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

### *Making the community better, one command at a time.*

*A feature-rich Discord bot for your ARK: Survival Ascended discord community.*

---

## Add to Your Server

**Invite Sir-5rM8 to your Discord server** — no setup required. Just add the bot and start using it.

[**Add Sir-5rM8 to Discord**](https://discord.com/oauth2/authorize?client_id=1236457243222868010)

**[📖 Server Setup Guide](docs/SERVER_SETUP_GUIDE.md)** — For server owners: configure rate notifications, karma, and more.

---

## ✨ Features

### ASA Official PVE Rate Fetch & Dynamic Rate Monitoring

| Command | Description |
|---------|-------------|
| `/rates` | Live server rates: EXP, Harvesting, Taming, Mating, Egg Hatch, Baby Mature, Imprint & Cuddle |
| `/set_rate_channel [channel] [role]` | Set channel for automatic rate updates *(Admin only)*|
| `/rate_channel_status` | Show current rate notification setup *(Admin only)*|
| `/clear_rate_channel` | Remove rate notifications for this server *(Admin only)*|

### Server Status

| Command | Description |
|---------|-------------|
| `/serverstatus [server]` | Check ASA official server by name or number (e.g. 5313, TheIsland) |

### Karma System

| Command | Description |
|---------|-------------|
| `/karma [member] [reason]` | Give 1 karma (24h cooldown per person) |
| `/manage_karma action:check [member]` | Check karma balance |
| `/manage_karma action:history [member]` | View karma history |
| `/manage_karma action:remove [member]` | Remove 1 karma *(Admin only)* |
| `/manage_karma action:audit` | Recent removals *(Admin only)* |

### Admin Tools

| Command | Description |
|---------|-------------|
| `/say [message]` | Repeats a message |
| `/servers` | List every server the bot is in *(Admin only)* |

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

Optional Supabase storage: see [docs/SUPABASE.md](docs/SUPABASE.md). Copy [`.env.example`](.env.example) to `.env` and fill in your values.

**Developer:** After code changes without a full restart, bot owner or admins can run `!reload` in Discord to reload cogs and re-sync slash commands.

---

## 📄 License

This project is licensed under the GNU GPL v3 — see the [LICENSE](LICENSE) file for details.

---

**Built with** ❤ *for ARK Discord communities*. *Sir-5rM8 is not affiliated with Studio Wildcard.*

[Terms of Service](TERMS_OF_SERVICE.md) · [Privacy Policy](PRIVACY_POLICY.md)

<a href="https://www.buymeacoffee.com/xwonder87x" target="_blank" rel="noopener noreferrer" aria-label="Buy me a coffee"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" width="150" /></a>