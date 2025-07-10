# File: services/youtube_auth_service.py
import os
import json
import subprocess
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path


class YouTubeAuthManager:
    def __init__(self):
        self.cookie_file = "/config/youtube_cookies.txt"
        self.auth_status_file = "/config/youtube_auth_status.json"

    def check_auth_status(self) -> dict:
        """Check current authentication status"""
        if not os.path.exists(self.cookie_file):
            return {"status": "missing", "message": "No cookies file found"}

        # Test cookies with simple yt-dlp call
        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--cookies",
                    self.cookie_file,
                    "--no-download",
                    "--quiet",
                    "https://youtube.com/watch?v=dQw4w9WgXcQ",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return {"status": "valid", "message": "Authentication working"}
            elif "Sign in to confirm" in result.stderr:
                return {
                    "status": "expired",
                    "message": "Cookies expired - bot detection",
                }
            else:
                return {"status": "invalid", "message": "Authentication failed"}

        except Exception as e:
            return {"status": "error", "message": f"Test failed: {str(e)}"}

    def save_auth_status(self, status_data: dict):
        """Save authentication status with timestamp"""
        status_data["last_checked"] = datetime.now().isoformat()
        with open(self.auth_status_file, "w") as f:
            json.dump(status_data, f, indent=2)

    def get_cookie_info(self) -> dict:
        """Get cookie file information"""
        if not os.path.exists(self.cookie_file):
            return {"exists": False}

        stat = os.stat(self.cookie_file)
        return {
            "exists": True,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "age_days": (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days,
        }
