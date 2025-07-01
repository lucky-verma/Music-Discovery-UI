import requests
import base64
import time
import streamlit as st
from utils.config import Config


class SpotifyService:
    """Enhanced Spotify Web API service"""

    def __init__(self):
        self.config = Config()
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"

    def set_credentials(self, client_id: str, client_secret: str):
        """Set and save Spotify credentials"""
        self.config.set("spotify.client_id", client_id)
        self.config.set("spotify.client_secret", client_secret)
        return self._get_access_token()

    def _get_access_token(self):
        """Get access token using client credentials flow"""
        client_id = self.config.get("spotify.client_id")
        client_secret = self.config.get("spotify.client_secret")

        if not client_id or not client_secret:
            return False

        # Check if current token is still valid
        current_token = self.config.get("spotify.access_token")
        token_expires = self.config.get("spotify.token_expires", 0)

        if current_token and time.time() < token_expires:
            return True

        try:
            # Encode credentials
            credentials = base64.b64encode(
                f"{client_id}:{client_secret}".encode()
            ).decode()

            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {"grant_type": "client_credentials"}

            response = requests.post(self.auth_url, headers=headers, data=data)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                expires_in = token_data["expires_in"]

                # Save token with expiration time
                self.config.set("spotify.access_token", access_token)
                self.config.set(
                    "spotify.token_expires", time.time() + expires_in - 300
                )  # 5 min buffer

                return True
            else:
                st.error(f"Spotify auth failed: {response.status_code}")
                return False
        except Exception as e:
            st.error(f"Spotify auth error: {str(e)}")
            return False

    def _get_headers(self):
        """Get authorization headers for API calls"""
        access_token = self.config.get("spotify.access_token")
        if not access_token:
            if not self._get_access_token():
                return None
            access_token = self.config.get("spotify.access_token")

        return {"Authorization": f"Bearer {access_token}"}

    def search_tracks(self, query: str, limit: int = 20):
        """Search for tracks with rich metadata"""
        headers = self._get_headers()
        if not headers:
            return []

        try:
            params = {"q": query, "type": "track", "limit": limit, "market": "US"}

            response = requests.get(
                f"{self.base_url}/search", headers=headers, params=params
            )

            if response.status_code == 200:
                data = response.json()
                tracks = []

                for item in data.get("tracks", {}).get("items", []):
                    track = {
                        "id": item["id"],
                        "name": item["name"],
                        "artists": [artist["name"] for artist in item["artists"]],
                        "album": item["album"]["name"],
                        "album_art": (
                            item["album"]["images"][0]["url"]
                            if item["album"]["images"]
                            else None
                        ),
                        "release_date": item["album"]["release_date"],
                        "duration_ms": item["duration_ms"],
                        "popularity": item["popularity"],
                        "preview_url": item["preview_url"],
                        "external_urls": item["external_urls"],
                        "search_query": f"{', '.join([artist['name'] for artist in item['artists']])} {item['name']}",
                    }
                    tracks.append(track)

                return tracks
            else:
                st.error(f"Spotify search failed: {response.status_code}")
                return []

        except Exception as e:
            st.error(f"Spotify search error: {str(e)}")
            return []

    def get_featured_playlists(self, limit: int = 10):
        """Get featured playlists for landing page"""
        headers = self._get_headers()
        if not headers:
            return []

        try:
            params = {"limit": limit, "country": "US"}
            response = requests.get(
                f"{self.base_url}/browse/featured-playlists",
                headers=headers,
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                playlists = []

                for item in data.get("playlists", {}).get("items", []):
                    playlist = {
                        "id": item["id"],
                        "name": item["name"],
                        "description": item["description"],
                        "image": item["images"][0]["url"] if item["images"] else None,
                        "tracks_total": item["tracks"]["total"],
                        "external_urls": item["external_urls"],
                    }
                    playlists.append(playlist)

                return playlists
            return []

        except Exception as e:
            st.error(f"Error fetching featured playlists: {str(e)}")
            return []

    def get_playlist_tracks(self, playlist_id: str):
        """Get tracks from a specific playlist"""
        headers = self._get_headers()
        if not headers:
            return []

        try:
            tracks = []
            offset = 0
            limit = 50

            while True:
                params = {"offset": offset, "limit": limit, "market": "US"}
                response = requests.get(
                    f"{self.base_url}/playlists/{playlist_id}/tracks",
                    headers=headers,
                    params=params,
                )

                if response.status_code != 200:
                    break

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                for item in items:
                    track = item.get("track", {})
                    if track and track.get("type") == "track":
                        track_info = {
                            "id": track["id"],
                            "name": track["name"],
                            "artists": [
                                artist["name"] for artist in track.get("artists", [])
                            ],
                            "album": track.get("album", {}).get("name", ""),
                            "album_art": (
                                track.get("album", {}).get("images", [{}])[0].get("url")
                                if track.get("album", {}).get("images")
                                else None
                            ),
                            "duration_ms": track.get("duration_ms", 0),
                            "popularity": track.get("popularity", 0),
                            "preview_url": track.get("preview_url"),
                            "search_query": f"{', '.join([artist['name'] for artist in track.get('artists', [])])} {track['name']}",
                        }
                        tracks.append(track_info)

                offset += limit
                if len(items) < limit:
                    break

            return tracks

        except Exception as e:
            st.error(f"Error fetching playlist tracks: {str(e)}")
            return []

    def get_recommendations(self, seed_tracks=None, seed_artists=None, limit=20):
        """Get music recommendations based on seeds"""
        headers = self._get_headers()
        if not headers:
            return []

        try:
            params = {"limit": limit, "market": "US"}

            if seed_tracks:
                params["seed_tracks"] = ",".join(seed_tracks[:5])  # Max 5 seeds
            if seed_artists:
                params["seed_artists"] = ",".join(seed_artists[:5])  # Max 5 seeds

            response = requests.get(
                f"{self.base_url}/recommendations", headers=headers, params=params
            )

            if response.status_code == 200:
                data = response.json()
                tracks = []

                for item in data.get("tracks", []):
                    track = {
                        "id": item["id"],
                        "name": item["name"],
                        "artists": [artist["name"] for artist in item["artists"]],
                        "album": item["album"]["name"],
                        "album_art": (
                            item["album"]["images"][0]["url"]
                            if item["album"]["images"]
                            else None
                        ),
                        "popularity": item["popularity"],
                        "preview_url": item["preview_url"],
                        "search_query": f"{', '.join([artist['name'] for artist in item['artists']])} {item['name']}",
                    }
                    tracks.append(track)

                return tracks
            return []

        except Exception as e:
            st.error(f"Error fetching recommendations: {str(e)}")
            return []

    def get_liked_tracks(self, limit=100):
        """Fetch user's liked (saved) tracks from Spotify"""
        headers = self._get_headers()
        if not headers:
            return []

        tracks = []
        offset = 0

        while len(tracks) < limit:
            params = {
                "limit": min(50, limit - len(tracks)),
                "offset": offset,
                "market": "US",
            }

            try:
                response = requests.get(
                    f"{self.base_url}/me/tracks", headers=headers, params=params
                )

                if response.status_code != 200:
                    break

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                for item in items:
                    track = item["track"]
                    tracks.append(
                        {
                            "id": track["id"],
                            "name": track["name"],
                            "artists": [a["name"] for a in track["artists"]],
                            "album": track["album"]["name"],
                            "album_art": (
                                track["album"]["images"][0]["url"]
                                if track["album"]["images"]
                                else None
                            ),
                            "search_query": f"{', '.join([a['name'] for a in track['artists']])} {track['name']}",
                        }
                    )

                if len(items) < 50:
                    break

                offset += 50

            except Exception as e:
                st.error(f"Error fetching liked tracks: {str(e)}")
                break

        return tracks

    def get_user_playlists(self, limit=20):
        """Fetch user's playlists from Spotify"""
        headers = self._get_headers()
        if not headers:
            return []

        playlists = []
        offset = 0

        while len(playlists) < limit:
            params = {"limit": min(50, limit - len(playlists)), "offset": offset}

            try:
                response = requests.get(
                    f"{self.base_url}/me/playlists", headers=headers, params=params
                )

                if response.status_code != 200:
                    break

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                for item in items:
                    playlists.append(
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "description": item["description"],
                            "image": (
                                item["images"][0]["url"] if item["images"] else None
                            ),
                            "tracks_total": item["tracks"]["total"],
                        }
                    )

                if len(items) < 50:
                    break

                offset += 50

            except Exception as e:
                st.error(f"Error fetching playlists: {str(e)}")
                break

        return playlists
