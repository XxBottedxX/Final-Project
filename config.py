"""
config.py
Loads and validates configuration from config.json.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
REQUIRED_FIELDS = ("token", "channel_id", "server_path")


@dataclass
class Config:
    token: str
    channel_id: int
    server_path: str
    server_name: str = "My Minecraft Server"
    update_interval_minutes: int = 30
    top_n: int = 10

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        if not path.exists():
            print(f"[ERROR] config.json not found at {path}")
            print("Copy config.example.json to config.json and fill in your values.")
            sys.exit(1)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[ERROR] config.json is not valid JSON: {e}")
            sys.exit(1)

        # Validate required fields
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                print(f"[ERROR] Missing required config field: '{field}'")
                sys.exit(1)

        # Warn if token looks like it hasn't been replaced
        if data["token"] == "YOUR_DISCORD_BOT_TOKEN":
            print("[ERROR] Replace 'YOUR_DISCORD_BOT_TOKEN' in config.json with your real token.")
            sys.exit(1)

        return cls(
            token=data["token"],
            channel_id=int(data["channel_id"]),
            server_path=data["server_path"],
            server_name=data.get("server_name", "My Minecraft Server"),
            update_interval_minutes=int(data.get("update_interval_minutes", 30)),
            top_n=int(data.get("top_n", 10)),
        )
