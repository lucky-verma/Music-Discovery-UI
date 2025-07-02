import os
import requests
import re
import time
from typing import Optional
import streamlit as st


class LyricsService:
    """Free lyrics fetching service with multiple sources"""

    def __init__(self):
        self.sources = [
            self._get_lyrics_ovh,
            self._get_lyrics_musixmatch_free,
        ]

    def get_lyrics(self, artist: str, track: str) -> Optional[str]:
        """Get lyrics from multiple free sources"""
        clean_artist = self._clean_query(artist)
        clean_track = self._clean_query(track)

        for source_func in self.sources:
            try:
                lyrics = source_func(clean_artist, clean_track)
                if (
                    lyrics and len(lyrics.strip()) > 50
                ):  # Valid lyrics should be substantial
                    return lyrics.strip()
            except Exception as e:
                continue

        return None

    def _clean_query(self, text: str) -> str:
        """Clean artist/track name for API queries"""
        # Remove featuring, remix, etc.
        text = re.sub(r"\(.*?\)", "", text)
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(r"feat\..*|ft\..*|featuring.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"remix.*|extended.*|radio edit.*", "", text, flags=re.IGNORECASE)
        return text.strip()

    def _get_lyrics_ovh(self, artist: str, track: str) -> Optional[str]:
        """Get lyrics from Lyrics.ovh (free, no API key)"""
        try:
            url = f"https://api.lyrics.ovh/v1/{artist}/{track}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("lyrics", "")
        except:
            pass
        return None

    def _get_lyrics_musixmatch_free(self, artist: str, track: str) -> Optional[str]:
        """Get lyrics from Musixmatch free tier (if API key available)"""
        # This would require a free Musixmatch API key
        # Users can sign up at https://developer.musixmatch.com/
        return None


class LyricsManager:
    """Manage lyrics storage and display"""

    def __init__(self):
        self.lyrics_service = LyricsService()

    def get_and_cache_lyrics(
        self, artist: str, track: str, cache_path: str = None
    ) -> Optional[str]:
        """Get lyrics and optionally cache them"""
        lyrics = self.lyrics_service.get_lyrics(artist, track)

        if lyrics and cache_path:
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(lyrics)
            except:
                pass

        return lyrics

    def format_lyrics_for_display(self, lyrics: str) -> str:
        """Format lyrics for better display"""
        if not lyrics:
            return "No lyrics available"

        # Clean up lyrics
        lyrics = lyrics.replace("\r\n", "\n").replace("\r", "\n")
        lines = lyrics.split("\n")

        # Remove empty lines at start/end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        return "\n".join(lines)
