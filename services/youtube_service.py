import subprocess
import json
import re
from typing import List, Dict, Optional


class YouTubeService:
    """Enhanced YouTube music service with metadata"""

    def __init__(self):
        self.ytdl_container = "ytdl-sub"

    def search_music(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search YouTube Music with enhanced metadata"""
        try:
            cmd = [
                "docker",
                "exec",
                self.ytdl_container,
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end",
                str(max_results),
                f"ytsearch{max_results}:{query}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                results = []
                lines = result.stdout.strip().split("\n")

                for line in lines:
                    try:
                        if line.strip():
                            item = json.loads(line)

                            # Extract metadata
                            duration = item.get("duration", 0) or 0
                            duration = int(duration) if duration else 0

                            # Try to extract album info from title
                            title = item.get("title", "")
                            uploader = item.get("uploader", "")

                            # Enhanced metadata extraction
                            track_info = {
                                "id": item.get("id", ""),
                                "title": title,
                                "artist": uploader,
                                "duration": duration,
                                "duration_str": (
                                    f"{duration//60}:{duration%60:02d}"
                                    if duration
                                    else "N/A"
                                ),
                                "view_count": item.get("view_count", 0),
                                "upload_date": item.get("upload_date", ""),
                                "url": f"https://youtube.com/watch?v={item.get('id', '')}",
                                "thumbnail": f"https://img.youtube.com/vi/{item.get('id', '')}/mqdefault.jpg",
                                "description": (
                                    item.get("description", "")[:200] + "..."
                                    if item.get("description")
                                    else ""
                                ),
                            }

                            results.append(track_info)
                    except json.JSONDecodeError:
                        continue

                return results
            else:
                return []

        except Exception as e:
            print(f"YouTube search error: {str(e)}")
            return []

    def get_video_info(self, url: str) -> Optional[Dict]:
        """Get detailed video information"""
        try:
            # Handle YouTube Music URLs
            if "music.youtube.com" in url:
                if "watch?v=" in url:
                    video_id = url.split("watch?v=")[1].split("&")[0]
                    url = f"https://youtube.com/watch?v={video_id}"

            cmd = [
                "docker",
                "exec",
                self.ytdl_container,
                "yt-dlp",
                "--dump-json",
                "--no-download",
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout.strip())

                return {
                    "title": data.get("title", "Unknown"),
                    "uploader": data.get("uploader", "Unknown"),
                    "duration": data.get("duration", 0),
                    "view_count": data.get("view_count", 0),
                    "upload_date": data.get("upload_date", ""),
                    "description": data.get("description", ""),
                    "thumbnail": data.get("thumbnail", ""),
                    "tags": data.get("tags", []),
                    "categories": data.get("categories", []),
                }
            return None

        except Exception as e:
            print(f"Error getting video info: {str(e)}")
            return None
