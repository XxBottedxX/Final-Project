# ⚔️ Minecraft Leaderboard Discord Bot (Python)

Posts auto-updating leaderboards for **Playtime, Mob Kills, Player Kills, Deaths,** and **Blocks Mined** to your Discord server. Built for Paper (and vanilla) Java Edition servers.

## Requirements
- Python 3.11+
- A Discord bot token
- Read access to your Paper server directory

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Edit config.json with your token, channel_id, and server_path
python bot.py
```

## Config Fields

| Key | Description |
|-----|-------------|
| `token` | Discord bot token |
| `channel_id` | Channel to post leaderboard in |
| `server_name` | Shown in the embed title |
| `server_path` | Absolute path to Paper server root |
| `update_interval_minutes` | Refresh interval (default 30) |
| `top_n` | Players per category (default 10) |

## Slash Commands
- `/leaderboard` — Show leaderboard (private reply)
- `/lb-refresh` — Force refresh (requires Manage Server)


## How It Works
- Reads `world/stats/<uuid>.json` directly from your Paper server
- Sums all `minecraft:mined` block types for total blocks mined
- Resolves usernames from `usercache.json`, falls back to Mojang API
- Edits the same Discord message each refresh (no channel spam)

See README_FULL.md for full setup instructions including Discord bot creation steps.

## Final Product

<img width="222" height="842" alt="image" src="https://github.com/user-attachments/assets/63ddf258-6034-4c40-83e8-06f3982079d8" />


