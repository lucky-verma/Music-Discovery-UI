import requests
import base64
import time
import urllib.parse
import streamlit as st
from utils.config import Config
import secrets
import hashlib


class SpotifyService:
    """Enhanced Spotify Web API service with OAuth support"""

    def __init__(self):
        self.config = Config()
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"
        self.authorize_url = "https://accounts.spotify.com/authorize"
        self.redirect_uri = "https://music-discovery.luckyverma.com"

    def set_credentials(self, client_id: str, client_secret: str):
        """Set and save Spotify credentials"""
        self.config.set("spotify.client_id", client_id)
        self.config.set("spotify.client_secret", client_secret)
        return self._get_access_token()

    def get_auth_url(self):
        """Generate simple Spotify authorization URL (no PKCE)"""
        client_id = self.config.get("spotify.client_id")
        if not client_id:
            return None

        # Required scopes for accessing user data
        scopes = [
            "user-library-read",  # Access liked tracks
            "playlist-read-private",  # Access private playlists
            "playlist-read-collaborative",  # Access collaborative playlists
            "user-read-private",  # Access user profile
            "user-read-email",  # Access user email
        ]

        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": secrets.token_urlsafe(16),  # CSRF protection only
        }

        return f"{self.authorize_url}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, authorization_code: str):
        """Exchange authorization code for access token (simplified)"""
        client_id = self.config.get("spotify.client_id")
        client_secret = self.config.get("spotify.client_secret")

        if not all([client_id, client_secret]):
            return False

        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": self.redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            response = requests.post(self.auth_url, headers=headers, data=data)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data["expires_in"]

                # Save tokens
                self.config.set("spotify.access_token", access_token)
                self.config.set("spotify.refresh_token", refresh_token)
                self.config.set("spotify.token_expires", time.time() + expires_in - 300)
                self.config.set("spotify.oauth_completed", True)

                return True
            else:
                st.error(
                    f"Token exchange failed: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            st.error(f"Token exchange error: {str(e)}")
            return False

    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        refresh_token = self.config.get("spotify.refresh_token")
        client_id = self.config.get("spotify.client_id")
        client_secret = self.config.get("spotify.client_secret")

        if not all([refresh_token, client_id, client_secret]):
            return False

        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            response = requests.post(self.auth_url, headers=headers, data=data)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                expires_in = token_data["expires_in"]

                # Update access token
                self.config.set("spotify.access_token", access_token)
                self.config.set("spotify.token_expires", time.time() + expires_in - 300)

                # Update refresh token if provided
                if "refresh_token" in token_data:
                    self.config.set(
                        "spotify.refresh_token", token_data["refresh_token"]
                    )

                return True
            else:
                return False

        except Exception as e:
            return False

    def _get_access_token(self):
        """Check if we have a valid access token (for backward compatibility)"""
        # Check if OAuth is completed
        if self.config.get("spotify.oauth_completed"):
            current_token = self.config.get("spotify.access_token")
            token_expires = self.config.get("spotify.token_expires", 0)

            if current_token and time.time() < token_expires:
                return True
            elif self.config.get("spotify.refresh_token"):
                return self.refresh_access_token()

        return False

    def _get_headers(self):
        """Get authorization headers for API calls"""
        access_token = self.config.get("spotify.access_token")

        if not access_token:
            return None

        # Check if token is expired and refresh if needed
        token_expires = self.config.get("spotify.token_expires", 0)
        if time.time() >= token_expires:
            if not self.refresh_access_token():
                return None
            access_token = self.config.get("spotify.access_token")

        return {"Authorization": f"Bearer {access_token}"}

    def get_liked_tracks(self, limit=None):
        """Fetch user's liked (saved) tracks from Spotify - ALL tracks if no limit"""
        headers = self._get_headers()
        if not headers:
            return []

        tracks = []
        offset = 0

        try:
            while True:  # Continue until no more tracks
                # Get 50 tracks per request (Spotify API limit)
                params = {"limit": 50, "offset": offset, "market": "US"}

                response = requests.get(
                    f"{self.base_url}/me/tracks", headers=headers, params=params
                )

                if response.status_code != 200:
                    break

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break  # No more tracks

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
                            "added_at": item["added_at"],
                        }
                    )

                offset += 50

                # If limit is specified and reached, break
                if limit and len(tracks) >= limit:
                    tracks = tracks[:limit]  # Trim to exact limit
                    break

                # If we got fewer than 50 items, we've reached the end
                if len(items) < 50:
                    break

        except Exception as e:
            st.error(f"Error fetching liked tracks: {str(e)}")

        return tracks

    def get_user_playlists(self, limit=100):
        """Fetch user's playlists from Spotify"""
        headers = self._get_headers()
        if not headers:
            return []

        playlists = []
        offset = 0

        try:
            while len(playlists) < limit:
                params = {"limit": min(50, limit - len(playlists)), "offset": offset}

                response = requests.get(
                    f"{self.base_url}/me/playlists", headers=headers, params=params
                )

                if response.status_code != 200:
                    if response.status_code == 401:
                        st.error("Spotify authentication expired. Please reconnect.")
                    else:
                        st.error(f"Failed to fetch playlists: {response.status_code}")
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
                            "public": item["public"],
                            "owner": item["owner"]["display_name"],
                        }
                    )

                if len(items) < 50:
                    break

                offset += 50

        except Exception as e:
            st.error(f"Error fetching playlists: {str(e)}")

        return playlists

    def get_user_profile(self):
        """Get user profile information"""
        headers = self._get_headers()
        if not headers:
            return None

        try:
            response = requests.get(f"{self.base_url}/me", headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            st.error(f"Error fetching user profile: {str(e)}")
            return None

    # Keep existing methods for backward compatibility
    def search_tracks(self, query: str, limit: int = 20):
        """Search for tracks with rich metadata (works with both OAuth and Client Credentials)"""
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

    def get_playlist_tracks(self, playlist_id: str, limit=5000):
        """Fetch tracks from a specific playlist"""
        headers = self._get_headers()
        if not headers:
            return []

        tracks = []
        offset = 0

        try:
            while len(tracks) < limit:
                params = {
                    "limit": min(100, limit - len(tracks)),
                    "offset": offset,
                    "market": "US",
                }

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
                        tracks.append(
                            {
                                "id": track["id"],
                                "name": track["name"],
                                "artists": [
                                    a["name"] for a in track.get("artists", [])
                                ],
                                "album": track.get("album", {}).get("name", ""),
                                "album_art": (
                                    track.get("album", {})
                                    .get("images", [{}])[0]
                                    .get("url")
                                    if track.get("album", {}).get("images")
                                    else None
                                ),
                                "duration_ms": track.get("duration_ms", 0),
                                "popularity": track.get("popularity", 0),
                                "preview_url": track.get("preview_url"),
                                "search_query": f"{', '.join([a['name'] for a in track.get('artists', [])])} {track['name']}",
                            }
                        )

                if len(items) < 100:
                    break

                offset += 100

        except Exception as e:
            st.error(f"Error fetching playlist tracks: {str(e)}")

        return tracks
