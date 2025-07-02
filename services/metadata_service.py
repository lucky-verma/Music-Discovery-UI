import requests
import json
import time
import os
from typing import Dict, List, Optional
import streamlit as st
from utils.config import Config


class MetadataService:
    """Enhanced metadata and album art service with multiple sources"""

    def __init__(self):
        self.config = Config()

        # API endpoints
        self.musicbrainz_base = "https://musicbrainz.org/ws/2"
        self.lastfm_base = "http://ws.audioscrobbler.com/2.0/"
        self.coverart_base = "https://coverartarchive.org"
        self.lyrics_base = "https://api.lyrics.ovh/v1"
        self.genius_base = "https://api.genius.com"

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests

    def _rate_limit(self):
        """Ensure we don't hit API rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    def get_enhanced_metadata(self, artist: str, track: str, album: str = "") -> Dict:
        """Get enhanced metadata from multiple sources"""
        metadata = {
            "artist": artist,
            "track": track,
            "album": album,
            "album_art_urls": [],
            "lyrics": "",
            "musicbrainz_id": "",
            "lastfm_data": {},
            "additional_info": {},
        }

        try:
            # Get MusicBrainz data
            mb_data = self._get_musicbrainz_metadata(artist, track, album)
            if mb_data:
                metadata.update(mb_data)

            # Get Last.fm data
            lastfm_data = self._get_lastfm_metadata(artist, track, album)
            if lastfm_data:
                metadata["lastfm_data"] = lastfm_data
                if lastfm_data.get("album_art"):
                    metadata["album_art_urls"].append(lastfm_data["album_art"])

            # Get lyrics
            lyrics = self._get_lyrics(artist, track)
            if lyrics:
                metadata["lyrics"] = lyrics

        except Exception as e:
            st.warning(f"Error fetching enhanced metadata: {str(e)}")

        return metadata

    def _get_musicbrainz_metadata(
        self, artist: str, track: str, album: str = ""
    ) -> Optional[Dict]:
        """Get metadata from MusicBrainz"""
        try:
            self._rate_limit()

            # Search for recording
            query = f'artist:"{artist}" AND recording:"{track}"'
            if album:
                query += f' AND release:"{album}"'

            params = {"query": query, "limit": 1, "fmt": "json"}

            response = requests.get(
                f"{self.musicbrainz_base}/recording/",
                params=params,
                headers={"User-Agent": "MusicDiscoveryApp/1.0"},
            )

            if response.status_code == 200:
                data = response.json()
                recordings = data.get("recordings", [])

                if recordings:
                    recording = recordings[0]
                    result = {
                        "musicbrainz_id": recording.get("id", ""),
                        "title_mb": recording.get("title", ""),
                        "length_mb": recording.get("length", 0),
                        "additional_info": {
                            "disambiguation": recording.get("disambiguation", ""),
                            "tags": [
                                tag["name"] for tag in recording.get("tags", [])[:5]
                            ],
                        },
                    }

                    # Get album art from Cover Art Archive
                    if recording.get("releases"):
                        release_id = recording["releases"][0]["id"]
                        album_art = self._get_coverart_archive(release_id)
                        if album_art:
                            result["album_art_urls"] = album_art

                    return result

        except Exception as e:
            st.warning(f"MusicBrainz API error: {str(e)}")

        return None

    def _get_coverart_archive(self, release_id: str) -> List[str]:
        """Get album art from Cover Art Archive"""
        try:
            self._rate_limit()

            response = requests.get(
                f"{self.coverart_base}/release/{release_id}",
                headers={"User-Agent": "MusicDiscoveryApp/1.0"},
            )

            if response.status_code == 200:
                data = response.json()
                images = data.get("images", [])

                # Get different sizes
                art_urls = []
                for image in images[:3]:  # Max 3 images
                    if image.get("front", False):  # Prefer front covers
                        if "thumbnails" in image:
                            # Add different sizes
                            for size in ["large", "small"]:
                                if size in image["thumbnails"]:
                                    art_urls.append(image["thumbnails"][size])
                        art_urls.append(image["image"])

                return art_urls

        except Exception as e:
            st.warning(f"Cover Art Archive error: {str(e)}")

        return []

    def _get_lastfm_metadata(
        self, artist: str, track: str, album: str = ""
    ) -> Optional[Dict]:
        """Get metadata from Last.fm"""
        api_key = self.config.get("lastfm.api_key")
        if not api_key:
            return None

        try:
            self._rate_limit()

            params = {
                "method": "track.getInfo",
                "api_key": api_key,
                "artist": artist,
                "track": track,
                "format": "json",
            }

            response = requests.get(self.lastfm_base, params=params)

            if response.status_code == 200:
                data = response.json()
                track_info = data.get("track", {})

                result = {
                    "listeners": track_info.get("listeners", 0),
                    "playcount": track_info.get("playcount", 0),
                    "tags": [
                        tag["name"]
                        for tag in track_info.get("toptags", {}).get("tag", [])[:5]
                    ],
                    "similar_artists": [],
                    "album_art": "",
                }

                # Get album art from Last.fm
                album_info = track_info.get("album", {})
                if album_info and "image" in album_info:
                    for image in album_info["image"]:
                        if image.get("size") == "extralarge":
                            result["album_art"] = image.get("#text", "")
                            break

                # Get similar artists
                similar_params = {
                    "method": "artist.getSimilar",
                    "api_key": api_key,
                    "artist": artist,
                    "format": "json",
                    "limit": 5,
                }

                similar_response = requests.get(self.lastfm_base, params=similar_params)
                if similar_response.status_code == 200:
                    similar_data = similar_response.json()
                    similar_artists = similar_data.get("similarartists", {}).get(
                        "artist", []
                    )
                    result["similar_artists"] = [
                        a.get("name", "") for a in similar_artists[:5]
                    ]

                return result

        except Exception as e:
            st.warning(f"Last.fm API error: {str(e)}")

        return None

    def _get_lyrics(self, artist: str, track: str) -> str:
        """Get lyrics from multiple free sources"""
        # Try Lyrics.ovh first (free, no API key needed)
        try:
            self._rate_limit()

            response = requests.get(f"{self.lyrics_base}/{artist}/{track}")
            if response.status_code == 200:
                data = response.json()
                return data.get("lyrics", "")
        except:
            pass

        # Try other free sources here if needed
        return ""

    def download_album_art(self, art_url: str, output_path: str) -> bool:
        """Download album art to specified path"""
        try:
            response = requests.get(art_url, timeout=10)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
        except Exception as e:
            st.warning(f"Error downloading album art: {str(e)}")
        return False
