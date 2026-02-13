# Chat Log — Session Summary

## Overview

Summary of changes and decisions from recent development sessions.

---

## Karma System

### Simplified `/karma` command
- **Removed** add/remove action choice — karma is now add-by-default
- **`/karma member reason`** — Give 1 karma (reason required, 24h cooldown per person)
- **`/manage_karma action:remove member`** — Remove karma moved here (Admin only)

### Karma audit
- **`/manage_karma action:audit`** — Shows last 10 karma removals (Admin only)
- Reads from `data/karma_history.jsonl`, filters `action: "remove"` events
- Still useful: logs removals from `/manage_karma action:remove`

---

## Help & Documentation

### `/help` command
- New slash command with multiple embeds
- Sections: ASA Rates, Server Status, Karma System, Admin Tools
- Quick Start checklist included

### Feature structure (by creation order)
1. **ASA Official PVE Rate Fetch & Dynamic Rate Monitoring** — `/rates`, `/set_rate_channel`, `/rate_channel_status`, `/clear_rate_channel`
2. **Server Status** — `/serverstatus`
3. **Karma System** — `/karma`, `/manage_karma` (check, history, remove, audit)
4. **Admin Tools** — `/say`

### Files updated
- `commands/help.py` — Help embeds
- `README.md` — Feature list, command reference
- `docs/SERVER_SETUP_GUIDE.md` — Setup guide for server owners

---

## Server Setup

### Custom bash startup (`start.sh`)
- Runs after git pull and package installs
- Upgrades pip, then runs `python main.py`
- Set in host panel as custom bash file

---

## Command sync
- Discord caches command definitions — restart bot after changes to sync
- Local: 9 commands | Server: 8 commands → deploy latest code for parity

---

## Clean shutdown
- Added `try/except (KeyboardInterrupt, asyncio.CancelledError)` in `main.py`
- Prints "Shutting down..." instead of full traceback on Ctrl+C or server stop

---

## Command count (9 total)
- `/help`
- `/serverstatus`
- `/rates`
- `/karma`
- `/manage_karma`
- `/say`
- `/set_rate_channel`
- `/rate_channel_status`
- `/clear_rate_channel`
