import os
import json
from pathlib import Path


class Config:
    """Configuration management for the music discovery app"""

    def __init__(self):
        self.config_file = "/config/app_config.json"
        self.ensure_config_file()

    def ensure_config_file(self):
        """Ensure config file exists with defaults"""
        if not os.path.exists(self.config_file):
            default_config = {
                "spotify": {
                    "client_id": "",
                    "client_secret": "",
                    "access_token": "",
                    "token_expires": 0,
                },
                "paths": {
                    "music_library": "/music/library",
                    "youtube_downloads": "/music/youtube-music",
                    "import_staging": "/music/import-staging",
                },
                "features": {
                    "auto_deduplication": True,
                    "metadata_cleanup": True,
                    "album_art_download": True,
                },
            }

            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(default_config, f, indent=2)

    def get(self, key_path: str, default=None):
        """Get config value using dot notation (e.g., 'spotify.client_id')"""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)

            keys = key_path.split(".")
            value = config
            for key in keys:
                value = value.get(key, {})

            return value if value != {} else default
        except:
            return default

    def set(self, key_path: str, value):
        """Set config value using dot notation"""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
        except:
            config = {}

        keys = key_path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
