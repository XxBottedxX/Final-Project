"""
Minecraft Leaderboard Discord Bot
Reads Paper server player stats and posts leaderboards to Discord.
"""

import asyncio
import logging
import json
from pathlib import Path

import discord
from discord.ext import commands, tasks
from discord import app_commands

from config import Config
from stats_parser import StatsParser

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("mc-leaderboard")

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

cfg = Config.load()
parser = StatsParser(cfg)

# Track the last posted message ID so we edit instead of reposting
STATE_FILE = Path(__file__).parent / ".state.json"
last_message_id: int | None = None


def load_state():
    global last_message_id
    try:
        data = json.loads(STATE_FILE.read_text())
        last_message_id = data.get("message_id")
    except Exception:
        pass


def save_state():
    STATE_FILE.write_text(json.dumps({"message_id": last_message_id}))


# ── Embed builder ─────────────────────────────────────────────────────────────

MEDALS = ["🥇", "🥈", "🥉"]


def rank(i: int) -> str:
    return MEDALS[i] if i < 3 else f"**#{i + 1}**"


def build_embed(players: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️  {cfg.server_name} — Leaderboards",
        color=0x2ECC40,
    )
    embed.set_footer(text=f"Updated • {len(players)} players tracked")
    embed.timestamp = discord.utils.utcnow()

    def section(title: str, emoji: str, key: str, formatter):
        sorted_players = sorted(players, key=lambda p: p[key], reverse=True)
        top = sorted_players[: cfg.top_n]
        lines = [f"{rank(i)} **{p['name']}** — {formatter(p)}" for i, p in enumerate(top)]
        embed.add_field(
            name=f"{emoji} {title}",
            value="\n".join(lines) or "*No data*",
            inline=False,
        )

    section("Playtime",     "⏱️", "playtime_ticks",  lambda p: f"{p['playtime_ticks'] / 20 / 3600:.1f} hrs")
    section("Mob Kills",    "🗡️", "mob_kills",        lambda p: f"{p['mob_kills']:,}")
    section("Player Kills", "💀", "player_kills",     lambda p: f"{p['player_kills']:,}")
    section("Deaths",       "☠️", "deaths",           lambda p: f"{p['deaths']:,}")
    section("Blocks Mined", "⛏️", "blocks_mined",     lambda p: f"{p['blocks_mined']:,}")

    return embed


# ── Post / update leaderboard ─────────────────────────────────────────────────

async def post_leaderboard():
    global last_message_id

    channel = bot.get_channel(cfg.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cfg.channel_id)
        except discord.NotFound:
            log.error("Channel %s not found. Check channel_id in config.json.", cfg.channel_id)
            return

    try:
        players = await asyncio.to_thread(parser.build_all)
    except Exception as e:
        log.error("Failed to build leaderboards: %s", e)
        return

    embed = build_embed(players)

    # Try to edit existing message
    if last_message_id:
        try:
            msg = await channel.fetch_message(last_message_id)
            await msg.edit(embed=embed)
            log.info("Leaderboard updated (edited message).")
            return
        except discord.NotFound:
            last_message_id = None

    # Post new message
    try:
        msg = await channel.send(embed=embed)
        last_message_id = msg.id
        save_state()
        log.info("Leaderboard posted (new message id=%s).", msg.id)
    except discord.Forbidden:
        log.error("Missing permissions to send messages in channel %s.", cfg.channel_id)


# ── Scheduled task ────────────────────────────────────────────────────────────

@tasks.loop(minutes=cfg.update_interval_minutes)
async def scheduled_update():
    await post_leaderboard()


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)
    load_state()

    # Sync slash commands
    try:
        synced = await tree.sync()
        log.info("Synced %d slash command(s).", len(synced))
    except Exception as e:
        log.error("Failed to sync commands: %s", e)

    # Initial post + start loop
    await post_leaderboard()
    scheduled_update.start()
    log.info("Auto-update every %d minutes.", cfg.update_interval_minutes)


# ── Slash commands ────────────────────────────────────────────────────────────

@tree.command(name="leaderboard", description="Show the current Minecraft leaderboard")
async def cmd_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        players = await asyncio.to_thread(parser.build_all)
    except Exception as e:
        await interaction.followup.send(f"❌ Error reading stats: {e}", ephemeral=True)
        return
    embed = build_embed(players)
    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(name="lb-refresh", description="Force a leaderboard refresh (admin only)")
@app_commands.checks.has_permissions(manage_guild=True)
async def cmd_refresh(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await post_leaderboard()
    await interaction.followup.send("✅ Leaderboard refreshed!", ephemeral=True)


@cmd_refresh.error
async def cmd_refresh_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission.", ephemeral=True
        )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot.run(cfg.token, log_handler=None)
