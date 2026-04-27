"""
stats_parser.py
Reads Minecraft Paper/vanilla player stats from disk and resolves usernames.
Supports Minecraft 1.13+ stat JSON format.
"""

import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

log = logging.getLogger("mc-leaderboard.parser")


class StatsParser:
    def __init__(self, cfg):
        self.cfg = cfg
        self._name_cache: dict[str, str] = {}

    # ── Paths ──────────────────────────────────────────────────────────────

    @property
    def stats_dir(self) -> Path:
        return Path(self.cfg.server_path) / "world" / "stats"

    @property
    def playerdata_dir(self) -> Path:
        return Path(self.cfg.server_path) / "world" / "playerdata"

    @property
    def usercache_path(self) -> Path:
        return Path(self.cfg.server_path) / "usercache.json"

    # ── Username resolution ────────────────────────────────────────────────

    def _load_usercache(self) -> dict[str, str]:
        """Returns a dict of uuid -> name from the server's usercache.json."""
        mapping: dict[str, str] = {}
        if not self.usercache_path.exists():
            return mapping
        try:
            entries = json.loads(self.usercache_path.read_text(encoding="utf-8"))
            for entry in entries:
                if "uuid" in entry and "name" in entry:
                    mapping[entry["uuid"]] = entry["name"]
        except Exception as e:
            log.warning("Could not read usercache.json: %s", e)
        return mapping

    def _mojang_lookup(self, uuid: str) -> Optional[str]:
        """Query Mojang's session server for a player name. Returns None on failure."""
        clean = uuid.replace("-", "")
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{clean}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mc-leaderboard-bot/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return data.get("name")
        except Exception:
            return None

    def resolve_username(self, uuid: str) -> str:
        if uuid in self._name_cache:
            return self._name_cache[uuid]

        # Try usercache first (fast, offline-friendly)
        usercache = self._load_usercache()
        if uuid in usercache:
            self._name_cache[uuid] = usercache[uuid]
            return usercache[uuid]

        # Mojang API fallback
        name = self._mojang_lookup(uuid)
        if name:
            self._name_cache[uuid] = name
            return name

        # Last resort: truncated UUID
        short = uuid[:8] + "…"
        self._name_cache[uuid] = short
        return short

    # ── Stat reading ───────────────────────────────────────────────────────

    def read_stats_json(self, uuid: str) -> dict:
        """
        Reads world/stats/<uuid>.json.
        Returns the top-level 'stats' dict, e.g.:
          { "minecraft:custom": {...}, "minecraft:mined": {...}, ... }
        """
        path = self.stats_dir / f"{uuid}.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("stats", {})
        except Exception as e:
            log.warning("Could not read stats for %s: %s", uuid, e)
            return {}

    @staticmethod
    def get_custom(stats: dict, stat: str) -> int:
        """Get a value from minecraft:custom, e.g. 'minecraft:play_time'."""
        return stats.get("minecraft:custom", {}).get(stat, 0)

    @staticmethod
    def sum_mined(stats: dict) -> int:
        """Sum all block counts under minecraft:mined."""
        return sum(stats.get("minecraft:mined", {}).values())

    @staticmethod
    def get_playtime_ticks(stats: dict) -> int:
        """
        Paper/vanilla tracks playtime under minecraft:custom.
        Key changed from 'minecraft:play_one_minute' (< 1.17) to
        'minecraft:play_time' (>= 1.17). Try both.
        """
        custom = stats.get("minecraft:custom", {})
        return (
            custom.get("minecraft:play_time")
            or custom.get("minecraft:play_one_minute")
            or 0
        )

    # ── Build full player list ─────────────────────────────────────────────

    def build_all(self) -> list[dict]:
        """
        Scans world/stats/ and returns a list of player stat dicts.
        Raises FileNotFoundError if stats dir is missing.
        """
        if not self.stats_dir.exists():
            raise FileNotFoundError(
                f"Stats directory not found: {self.stats_dir}\n"
                "Check 'server_path' in config.json."
            )

        stat_files = list(self.stats_dir.glob("*.json"))
        if not stat_files:
            raise ValueError("No player stat files found in stats directory.")

        players = []
        for f in stat_files:
            uuid = f.stem
            stats = self.read_stats_json(uuid)

            players.append({
                "uuid":           uuid,
                "name":           self.resolve_username(uuid),
                "playtime_ticks": self.get_playtime_ticks(stats),
                "mob_kills":      self.get_custom(stats, "minecraft:mob_kills"),
                "player_kills":   self.get_custom(stats, "minecraft:player_kills"),
                "deaths":         self.get_custom(stats, "minecraft:deaths"),
                "blocks_mined":   self.sum_mined(stats),
            })

        log.info("Parsed stats for %d player(s).", len(players))
        return players
