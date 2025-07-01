import streamlit as st
import subprocess
import json
import os
import requests
import time
from datetime import datetime
import threading
import uuid
import re
from urllib.parse import urlparse, parse_qs

from services.spotify_service import SpotifyService
from services.youtube_service import YouTubeService
from services.job_service import JobManager
from utils.config import Config

# Configure page
st.set_page_config(
    page_title="🎵 Music Discovery",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modern Spotify-like CSS (Updated for 8 columns)
st.markdown(
    """
<style>
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    .stApp > header {display: none;}
    
    /* Main container */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        max-width: 100%;
    }
    
    /* Dark theme */
    .stApp {
        background: linear-gradient(135deg, #121212 0%, #1e1e1e 100%);
        color: #ffffff;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(90deg, #1DB954, #1ed760);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(29, 185, 84, 0.3);
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(90deg, #1DB954, #1ed760);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 8px 20px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #1ed760, #1DB954);
        transform: translateY(-1px);
    }
    
    /* Music card styling */
    .music-card {
        background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
        border-radius: 12px;
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #404040;
        transition: all 0.3s ease;
    }
    
    .music-card:hover {
        border-color: #1DB954;
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(29, 185, 84, 0.2);
    }
    
    /* Results container */
    .results-container {
        width: 100%;
        margin: 20px 0;
    }
    
    /* Playlist section styling */
    .playlist-section {
        background: #2a2a2a;
        border-radius: 12px;
        padding: 20px;
        margin: 20px 0;
        border: 1px solid #404040;
    }
    
    /* Spotify section styling */
    .spotify-section {
        background: linear-gradient(135deg, #1DB954, #1ed760);
        border-radius: 12px;
        padding: 20px;
        margin: 20px 0;
        color: white;
    }
</style>
""",
    unsafe_allow_html=True,
)


class EnhancedMusicApp:
    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
        self.config = Config()
        self.spotify_service = SpotifyService()
        self.youtube_service = YouTubeService()
        self.job_manager = JobManager()

        os.makedirs("/config", exist_ok=True)
        if not os.path.exists(self.jobs_file):
            with open(self.jobs_file, "w") as f:
                json.dump({}, f)

    def get_real_library_stats(self):
        """Get actual library statistics"""
        try:
            # Count music files
            cmd = [
                "find",
                "/music",
                "-type",
                "f",
                "-name",
                "*.mp3",
                "-o",
                "-name",
                "*.m4a",
                "-o",
                "-name",
                "*.flac",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            files = [f for f in result.stdout.split("\n") if f.strip()]

            # Get storage info
            storage_cmd = ["df", "-h", "/music"]
            storage_result = subprocess.run(storage_cmd, capture_output=True, text=True)

            used_size = "Unknown"
            if storage_result.returncode == 0:
                lines = storage_result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        used_size = parts[2]

            # Count artists and albums
            artists = set()
            albums = set()

            for file_path in files[:500]:  # Sample for performance
                try:
                    parts = file_path.split("/")
                    if len(parts) >= 4 and "youtube-music" in parts:
                        youtube_idx = parts.index("youtube-music")
                        if youtube_idx + 1 < len(parts):
                            artists.add(parts[youtube_idx + 1])
                        if youtube_idx + 2 < len(parts):
                            albums.add(
                                f"{parts[youtube_idx + 1]}/{parts[youtube_idx + 2]}"
                            )
                except:
                    continue

            return {
                "total_tracks": len(files),
                "artists": len(artists),
                "albums": len(albums),
                "storage_used": used_size,
            }
        except Exception as e:
            return {
                "total_tracks": 0,
                "artists": 0,
                "albums": 0,
                "storage_used": "Unknown",
            }

    def is_music_content(self, title, description="", duration=0):
        """FIXED: More lenient music filter with null checks"""
        # FIXED: Add null checks to prevent NoneType errors
        title_lower = (title or "").lower()
        desc_lower = (description or "").lower()

        # Obvious non-music indicators (be more specific)
        non_music_keywords = [
            "tutorial",
            "how to make",
            "review of",
            "reaction to",
            "unboxing",
            "gaming",
            "news report",
            "interview with",
            "movie trailer",
            "tv show",
            "podcast episode",
            "cooking recipe",
            "workout routine",
            "meditation guide",
            "documentary",
            "vlog entry",
            "comedy sketch",
        ]

        # Check for clear non-music indicators
        has_non_music = any(
            keyword in title_lower or keyword in desc_lower
            for keyword in non_music_keywords
        )

        # Duration filter (music typically 30 seconds to 20 minutes)
        reasonable_duration = 30 <= duration <= 1200  # 30 seconds to 20 minutes

        # If it has obvious non-music keywords, exclude it
        if has_non_music:
            return False

        # If duration is reasonable or unknown, include it (be more permissive)
        if reasonable_duration or duration == 0:
            return True

        # Default: include unless clearly not music
        return True

    def search_youtube_music(self, query, max_results=20, filter_music=True):
        """FIXED: Search YouTube Music with better error handling"""
        try:
            st.write(f"🔍 Searching for: '{query}' (filter_music: {filter_music})")

            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end",
                str(max_results * 2 if filter_music else max_results),
                f"ytsearch{max_results * 2 if filter_music else max_results}:{query}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

            if result.returncode != 0:
                st.error(f"❌ yt-dlp error (code {result.returncode}): {result.stderr}")
                return []

            if not result.stdout.strip():
                st.warning("⚠️ No output from yt-dlp")
                return []

            results = []
            lines = result.stdout.strip().split("\n")

            for line_num, line in enumerate(lines):
                if line.strip():
                    try:
                        item = json.loads(line)
                        duration = int(item.get("duration", 0) or 0)
                        title = (
                            item.get("title") or "Unknown"
                        )  # FIXED: Handle None titles
                        description = (
                            item.get("description") or ""
                        )  # FIXED: Handle None descriptions

                        # Apply music filter if requested
                        if filter_music and not self.is_music_content(
                            title, description, duration
                        ):
                            continue

                        results.append(
                            {
                                "id": item.get("id", ""),
                                "title": title,
                                "uploader": item.get("uploader", "Unknown"),
                                "duration": duration,
                                "duration_str": (
                                    f"{duration//60}:{duration%60:02d}"
                                    if duration
                                    else "N/A"
                                ),
                                "url": f"https://youtube.com/watch?v={item.get('id', '')}",
                                "thumbnail": f"https://img.youtube.com/vi/{item.get('id', '')}/mqdefault.jpg",
                            }
                        )

                        # Stop when we have enough results
                        if len(results) >= max_results:
                            break

                    except json.JSONDecodeError as e:
                        continue
                    except Exception as e:
                        continue

            st.write(f"✅ Found {len(results)} valid results after filtering")
            return results

        except subprocess.TimeoutExpired:
            st.error("❌ Search timeout - try a shorter query")
        except Exception as e:
            st.error(f"❌ Search failed: {str(e)}")

        return []

    def download_song(self, url, artist="", album=""):
        """Queue song for download using job manager"""
        metadata = {"artist": artist, "album": album}
        job_id = self.job_manager.add_job("single_song", url, metadata)
        return job_id

    def download_playlist(self, url, playlist_name=""):
        """Queue entire playlist for download"""
        metadata = {"playlist_name": playlist_name or "Downloaded Playlist"}
        job_id = self.job_manager.add_job("playlist", url, metadata)
        return job_id

    def check_navidrome_status(self):
        """Check if Navidrome is online"""
        try:
            # Try multiple possible endpoints
            endpoints = [
                "http://192.168.1.39:4533/ping",
                "http://localhost:4533/ping",
                "http://navidrome:4533/ping",
            ]

            for endpoint in endpoints:
                try:
                    result = subprocess.run(
                        ["curl", "-f", "--connect-timeout", "5", endpoint],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        return "🟢 Online"
                except:
                    continue

            return "🔴 Offline"
        except:
            return "🟡 Unknown"

    def trigger_navidrome_scan(self):
        """Trigger Navidrome library scan"""
        try:
            endpoints = [
                "http://192.168.1.39:4533/api/scanner/scan",
                "http://localhost:4533/api/scanner/scan",
                "http://navidrome:4533/api/scanner/scan",
            ]

            for endpoint in endpoints:
                try:
                    result = subprocess.run(
                        ["curl", "-X", "POST", "--connect-timeout", "5", endpoint],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        return True
                except:
                    continue

            # Try Docker exec as fallback
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "navidrome",
                    "curl",
                    "-X",
                    "POST",
                    "http://localhost:4533/api/scanner/scan",
                ],
                timeout=10,
                capture_output=True,
            )

            return True
        except:
            return False


def main():
    # Initialize app
    app = EnhancedMusicApp()

    # Header
    st.markdown(
        """
    <div class="main-header">
        <h1>🎵 Lucky's Music Discovery Hub</h1>
        <p>Unlimited YouTube Music Downloads • Spotify Integration • Zero Subscriptions</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Real Stats Dashboard
    stats = app.get_real_library_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tracks", stats["total_tracks"])
    with col2:
        st.metric("Artists", stats["artists"])
    with col3:
        st.metric("Albums", stats["albums"])
    with col4:
        st.metric("Storage Used", stats["storage_used"])

    # Main tabs - ADDED Spotify tab
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "🔍 **Discover & Download**",
            "🎵 **Spotify Sync**",
            "📋 **Playlist Manager**",
            "📊 **Download Status**",
            "🔧 **Library Tools**",
        ]
    )

    with tab1:
        # Search interface
        st.header("🔍 Search & Discover Music")

        search_query = st.text_input(
            "Search Music",
            placeholder="🎵 Search for songs, artists, albums... (e.g., 'Travis Scott', 'Bollywood hits')",
            key="search_input",
            label_visibility="collapsed",
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            search_button = st.button(
                "🔍 Search", type="primary", use_container_width=True
            )
        with col2:
            music_filter = st.checkbox(
                "🎵 Music Only", value=True, help="Filter out non-music content"
            )

        # Initialize session state for pagination
        if "search_results" not in st.session_state:
            st.session_state.search_results = []
        if "results_offset" not in st.session_state:
            st.session_state.results_offset = 0

        if search_query and search_button:
            with st.spinner("🎵 Searching YouTube Music..."):
                # Reset pagination on new search
                st.session_state.results_offset = 0
                results = app.search_youtube_music(
                    search_query, max_results=40, filter_music=music_filter
                )
                st.session_state.search_results = results
                st.session_state.last_search_query = search_query

        # Display search results with pagination
        if st.session_state.search_results:
            results = st.session_state.search_results
            offset = st.session_state.results_offset
            page_size = 32  # Show 32 results (4 rows of 8 columns)

            st.success(
                f"Found {len(results)} results for '{st.session_state.get('last_search_query', '')}'"
            )

            # Display current page of results - CHANGED to 8 columns
            current_page_results = results[offset : offset + page_size]

            if current_page_results:
                st.markdown('<div class="results-container">', unsafe_allow_html=True)

                # CHANGED: Display in 8 columns instead of 4
                for i in range(0, len(current_page_results), 8):
                    cols = st.columns(8)

                    for j, col in enumerate(cols):
                        if i + j < len(current_page_results):
                            track = current_page_results[i + j]
                            with col:
                                # Album art
                                if track.get("thumbnail"):
                                    st.image(
                                        track["thumbnail"], width=120
                                    )  # Smaller images for 8 columns

                                # Track info
                                title = (
                                    track["title"][:25] + "..."
                                    if len(track["title"]) > 25
                                    else track["title"]
                                )
                                uploader = (
                                    track["uploader"][:15] + "..."
                                    if len(track["uploader"]) > 15
                                    else track["uploader"]
                                )

                                st.markdown(f"**{title}**")
                                st.caption(f"🎤 {uploader}")
                                st.caption(f"⏱️ {track['duration_str']}")

                                # Download button
                                if st.button(
                                    "📥 Download",
                                    key=f"dl_{offset+i+j}",
                                    use_container_width=True,
                                ):
                                    job_id = app.download_song(track["url"])
                                    st.success(f"✅ Queued! Job: {job_id}")

                st.markdown("</div>", unsafe_allow_html=True)

                # Pagination controls - ADDED Load More and Clear Results
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if offset > 0:
                        if st.button("⬅️ Previous"):
                            st.session_state.results_offset = max(0, offset - page_size)
                            st.rerun()

                with col2:
                    current_page = (offset // page_size) + 1
                    total_pages = (len(results) - 1) // page_size + 1
                    st.markdown(
                        f"<div style='text-align: center'>Page {current_page} of {total_pages}</div>",
                        unsafe_allow_html=True,
                    )

                with col3:
                    if offset + page_size < len(results):
                        if st.button("Load More ➡️"):
                            st.session_state.results_offset = offset + page_size
                            st.rerun()

                # Clear results button
                if st.button("🗑️ Clear All Results"):
                    st.session_state.search_results = []
                    st.session_state.results_offset = 0
                    st.rerun()

        # Quick discovery - CHANGED to 8 columns
        st.header("🎭 Quick Discovery")

        genres = [
            ("🇮🇳 Bollywood Hits", "bollywood songs"),
            ("🎸 Rock Hits", "rock music"),
            ("🎤 Pop Charts", "pop songs"),
            ("🇰🇷 K-Pop", "kpop music"),
            ("🎵 Electronic", "electronic music"),
            ("🎷 Jazz", "jazz music"),
            ("🎼 Classical", "classical music"),
            ("🏴‍☠️ Old School", "90s music"),
        ]

        # Create genre buttons in 8 columns
        genre_cols = st.columns(8)
        for i, (genre_name, genre_query) in enumerate(genres):
            with genre_cols[i % 8]:
                if st.button(genre_name, key=f"genre_{i}", use_container_width=True):
                    st.session_state.genre_query = genre_query
                    st.session_state.genre_name = genre_name
                    st.rerun()

        # Display genre results if available
        if hasattr(st.session_state, "genre_query"):
            with st.spinner(f"Finding {st.session_state.genre_name} music..."):
                results = app.search_youtube_music(
                    st.session_state.genre_query, max_results=32, filter_music=False
                )

                if results:
                    st.success(
                        f"🎵 {st.session_state.genre_name} - {len(results)} tracks found"
                    )

                    st.markdown(
                        '<div class="results-container">', unsafe_allow_html=True
                    )

                    # CHANGED: Display in 8 columns
                    for j in range(0, len(results), 8):
                        result_cols = st.columns(8)

                        for k, col in enumerate(result_cols):
                            if j + k < len(results):
                                track = results[j + k]
                                with col:
                                    if track.get("thumbnail"):
                                        st.image(track["thumbnail"], width=120)

                                    title = (
                                        track["title"][:25] + "..."
                                        if len(track["title"]) > 25
                                        else track["title"]
                                    )
                                    uploader = (
                                        track["uploader"][:15] + "..."
                                        if len(track["uploader"]) > 15
                                        else track["uploader"]
                                    )

                                    st.markdown(f"**{title}**")
                                    st.caption(f"🎤 {uploader}")
                                    st.caption(f"⏱️ {track['duration_str']}")

                                    if st.button(
                                        "📥 Download",
                                        key=f"genre_dl_{j+k}",
                                        use_container_width=True,
                                    ):
                                        job_id = app.download_song(track["url"])
                                        st.success(f"✅ Queued! Job: {job_id}")

                    st.markdown("</div>", unsafe_allow_html=True)

                    # Clear results button
                    if st.button("🗑️ Clear Results"):
                        del st.session_state.genre_query
                        del st.session_state.genre_name
                        st.rerun()

    with tab2:
        # Spotify Sync Tab with OAuth
        st.header("🎵 Spotify Library Sync")

        st.markdown('<div class="spotify-section">', unsafe_allow_html=True)

        # Spotify credentials input
        col1, col2 = st.columns(2)
        with col1:
            client_id = st.text_input(
                "Spotify Client ID",
                value=app.config.get("spotify.client_id", ""),
                help="Get this from Spotify Developer Dashboard",
            )
        with col2:
            client_secret = st.text_input(
                "Spotify Client Secret",
                value=app.config.get("spotify.client_secret", ""),
                type="password",
                help="Get this from Spotify Developer Dashboard",
            )

        # Check if OAuth is completed
        oauth_completed = app.config.get("spotify.oauth_completed", False)

        if not oauth_completed:
            st.markdown("### 🔗 Connect Your Spotify Account")
            st.info("💡 **Step 1**: Enter your Client ID and Secret above")

            if client_id and client_secret:
                # Save credentials
                app.spotify_service.set_credentials(client_id, client_secret)

                st.info("💡 **Step 2**: Authorize access to your Spotify account")

                # Generate auth URL
                auth_url = app.spotify_service.get_auth_url()
                if auth_url:
                    st.markdown(
                        f"**Click here to authorize:** [🔗 Connect to Spotify]({auth_url})"
                    )
                    st.warning(
                        "⚠️ **Important**: Copy the entire URL you're redirected to and paste it below"
                    )

                    # Input for callback URL
                    callback_url = st.text_input(
                        "Paste the callback URL here:",
                        placeholder="http://localhost:8501/?code=AQC...",
                        help="After clicking the link above, copy the entire URL from your browser and paste it here",
                    )

                    if callback_url and "code=" in callback_url:
                        # Extract authorization code
                        try:
                            from urllib.parse import urlparse, parse_qs

                            parsed_url = urlparse(callback_url)
                            code = parse_qs(parsed_url.query).get("code", [None])[0]

                            if code:
                                with st.spinner("Exchanging code for token..."):
                                    if app.spotify_service.exchange_code_for_token(code):
                                        st.success("✅ Successfully connected to Spotify!")
                                        st.balloons()
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to connect. Please try again.")
                            else:
                                st.error(
                                    "❌ Invalid callback URL. Please copy the entire URL."
                                )
                        except Exception as e:
                            st.error(f"❌ Error processing callback URL: {str(e)}")
            else:
                st.warning("Please enter both Client ID and Client Secret to continue")

        else:
            # User is connected - show profile and sync options
            user_profile = app.spotify_service.get_user_profile()

            if user_profile:
                col1, col2 = st.columns([1, 3])
                with col1:
                    if user_profile.get("images") and user_profile["images"]:
                        st.image(user_profile["images"][0]["url"], width=100)
                with col2:
                    st.success(
                        f"🟢 Connected as **{user_profile.get('display_name', 'User')}**"
                    )
                    st.caption(
                        f"Followers: {user_profile.get('followers', {}).get('total', 0)}"
                    )
                    st.caption(f"Country: {user_profile.get('country', 'Unknown')}")

                    if st.button("🔄 Disconnect", type="secondary"):
                        # Clear OAuth data
                        app.config.set("spotify.oauth_completed", False)
                        app.config.set("spotify.access_token", "")
                        app.config.set("spotify.refresh_token", "")
                        st.rerun()

            st.markdown("### 📚 Your Spotify Library")

            # Sync options
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 Sync Saved Tracks", use_container_width=True):
                    with st.spinner("Fetching your saved tracks..."):
                        try:
                            # Get liked tracks from Spotify
                            liked_tracks = app.spotify_service.get_liked_tracks(limit=5000)

                            if liked_tracks:
                                st.info(
                                    f"Found **{len(liked_tracks)}** liked tracks. Queuing for download..."
                                )

                                # Queue each track for download
                                for track in liked_tracks:
                                    search_query = track["search_query"]
                                    job_id = app.job_manager.add_job(
                                        "single_song",
                                        f"ytsearch1:{search_query}",
                                        {
                                            "artist": ", ".join(track["artists"]),
                                            "album": track["album"],
                                            "spotify_track": True,
                                            "search_query": search_query,
                                        },
                                    )

                                st.success(
                                    f"✅ Queued **{len(liked_tracks)}** liked tracks for download!"
                                )
                                st.info(
                                    "📊 Check the **Download Status** tab to monitor progress."
                                )
                            else:
                                st.warning("No liked tracks found in your Spotify library.")

                        except Exception as e:
                            st.error(f"Error fetching liked tracks: {str(e)}")

            with col2:
                if st.button("📋 Sync Playlists", use_container_width=True):
                    with st.spinner("Fetching your playlists..."):
                        try:
                            # Get user playlists from Spotify
                            playlists = app.spotify_service.get_user_playlists(limit=100)

                            if playlists:
                                st.session_state.spotify_playlists = playlists
                                st.success(f"Found **{len(playlists)}** playlists!")
                                st.info("Select playlists below to sync.")
                            else:
                                st.warning("No playlists found in your Spotify account.")

                        except Exception as e:
                            st.error(f"Error fetching playlists: {str(e)}")

            # IMPROVED: Playlist selection and sync
            if (
                hasattr(st.session_state, "spotify_playlists")
                and st.session_state.spotify_playlists
            ):
                st.markdown("### 📋 Select Playlists to Sync")

                for playlist in st.session_state.spotify_playlists:
                    with st.expander(
                        f"🎶 **{playlist['name']}** ({playlist['tracks_total']} tracks)"
                    ):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.markdown(
                                f"**Description:** {playlist.get('description', 'No description')}"
                            )
                            st.markdown(f"**Owner:** {playlist['owner']}")
                            st.markdown(f"**Tracks:** {playlist['tracks_total']}")
                            st.markdown(
                                f"**Public:** {'Yes' if playlist['public'] else 'No'}"
                            )

                        with col2:
                            if playlist.get("image"):
                                st.image(playlist["image"], width=100)

                            if st.button(
                                f"📥 Sync",
                                key=f"sync_playlist_{playlist['id']}",
                                use_container_width=True,
                            ):
                                with st.spinner(
                                    f"Syncing playlist '{playlist['name']}'..."
                                ):
                                    try:
                                        # Get tracks from the playlist
                                        tracks = app.spotify_service.get_playlist_tracks(
                                            playlist["id"], limit=5000
                                        )

                                        if tracks:
                                            st.info(
                                                f"Found **{len(tracks)}** tracks. Queuing for download..."
                                            )

                                            # Queue each track for download
                                            for track in tracks:
                                                search_query = track["search_query"]
                                                job_id = app.job_manager.add_job(
                                                    "single_song",
                                                    f"ytsearch1:{search_query}",
                                                    {
                                                        "artist": ", ".join(
                                                            track["artists"]
                                                        ),
                                                        "album": track["album"],
                                                        "playlist_name": playlist["name"],
                                                        "spotify_track": True,
                                                        "search_query": search_query,
                                                    },
                                                )

                                            st.success(
                                                f"✅ Queued **{len(tracks)}** tracks from playlist **'{playlist['name']}'**!"
                                            )
                                            st.info(
                                                "📊 Check the **Download Status** tab to monitor progress."
                                            )
                                        else:
                                            st.warning(
                                                f"No tracks found in playlist '{playlist['name']}'."
                                            )

                                    except Exception as e:
                                        st.error(f"Error syncing playlist: {str(e)}")

            # Search functionality (works with OAuth)
            st.markdown("### 🔍 Search Spotify Catalog")
            spotify_query = st.text_input(
                "Search Spotify:", placeholder="Search for any music..."
            )

            if spotify_query:
                with st.spinner("Searching Spotify..."):
                    spotify_results = app.spotify_service.search_tracks(
                        spotify_query, limit=16
                    )

                    if spotify_results:
                        st.success(f"Found {len(spotify_results)} Spotify tracks")

                        # Display Spotify results in 8 columns
                        for i in range(0, len(spotify_results), 8):
                            cols = st.columns(8)

                            for j, col in enumerate(cols):
                                if i + j < len(spotify_results):
                                    track = spotify_results[i + j]
                                    with col:
                                        if track.get("album_art"):
                                            st.image(track["album_art"], width=120)

                                        st.markdown(f"**{track['name'][:25]}**")
                                        st.caption(f"🎤 {', '.join(track['artists'][:2])}")
                                        st.caption(f"💿 {track['album'][:20]}")

                                        # Download equivalent from YouTube
                                        if st.button(
                                            "📥 Download from YT",
                                            key=f"spotify_search_dl_{i+j}",
                                            use_container_width=True,
                                        ):
                                            search_query = track["search_query"]
                                            job_id = app.job_manager.add_job(
                                                "single_song",
                                                f"ytsearch1:{search_query}",
                                                {
                                                    "artist": (
                                                        track["artists"][0]
                                                        if track["artists"]
                                                        else ""
                                                    ),
                                                    "album": track["album"],
                                                    "spotify_track": True,
                                                    "search_query": search_query,
                                                },
                                            )
                                            st.success(f"✅ Queued: **{track['name']}**")

        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        # Playlist Manager Tab (existing code)
        st.header("📋 Playlist & URL Manager")

        st.markdown('<div class="playlist-section">', unsafe_allow_html=True)

        st.subheader("🔗 Add URLs or Playlists")

        url_input = st.text_area(
            "Paste URLs (one per line):",
            placeholder="https://youtube.com/watch?v=dQw4w9WgXcQ\nhttps://youtube.com/playlist?list=PLrAXtmRdnEQy3Qo2KnG...",
            height=100,
        )

        col1, col2 = st.columns(2)
        with col1:
            playlist_name = st.text_input(
                "Playlist Name (optional):", placeholder="e.g., 'My Awesome Mix'"
            )
        with col2:
            apply_filter = st.checkbox("🎵 Filter Music Only", value=True)

        if url_input and st.button("📥 **Process URLs**", type="primary"):
            urls = [url.strip() for url in url_input.split("\n") if url.strip()]

            if urls:
                processed_count = 0
                for url in urls:
                    if "playlist" in url or "list=" in url:
                        job_id = app.download_playlist(
                            url, playlist_name or "Downloaded Playlist"
                        )
                        st.success(f"📋 Playlist queued! Job: {job_id}")
                        processed_count += 1
                    elif "youtube.com/watch" in url or "music.youtube.com" in url:
                        job_id = app.download_song(url)
                        st.success(f"🎵 Song queued! Job: {job_id}")
                        processed_count += 1
                    else:
                        st.warning(f"⚠️ Unsupported URL: {url[:50]}...")

                if processed_count > 0:
                    st.success(f"✅ Processed {processed_count} URLs successfully!")

        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        # Download Status Tab - Enhanced with job manager
        st.header("📊 Download Status & History")

        if st.button("🔄 Refresh", key="refresh_status"):
            st.rerun()

        # Get stats from job manager
        stats = app.job_manager.get_stats()

        # Stats dashboard
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        with stat_col1:
            st.metric("Active Jobs", stats["active_jobs"])
        with stat_col2:
            st.metric("Total Downloads", stats["total_downloads"])
        with stat_col3:
            st.metric("Success Rate", f"{stats['success_rate']:.1f}%")
        with stat_col4:
            st.metric("Today's Downloads", stats["today_downloads"])

        # Active jobs
        jobs = app.job_manager.get_all_jobs()
        active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "running"]]

        if active_jobs:
            st.subheader("🔄 Active Downloads")
            for job in active_jobs:
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])

                    with col1:
                        status_emoji = "⏳" if job["status"] == "queued" else "⬇️"
                        job_type = (
                            "📋 Playlist"
                            if job.get("type") == "playlist"
                            else "🎵 Song"
                        )
                        st.markdown(f"**{status_emoji} {job_type} Processing...**")
                        st.caption(f"URL: {job['url'][:60]}...")
                        st.caption(f"Status: {job.get('message', 'Processing...')}")

                    with col2:
                        progress = job.get("progress", 0)
                        st.progress(progress / 100)
                        st.caption(f"{progress}%")

                    with col3:
                        st.caption(f"Job: {job['id']}")
                        if job["status"] == "queued" and st.button(
                            "❌", key=f"cancel_{job['id']}"
                        ):
                            if app.job_manager.cancel_job(job["id"]):
                                st.success("Job cancelled")
                                st.rerun()

        # Recent history
        history = app.job_manager.get_download_history()
        if history:
            st.subheader("📜 Recent Downloads")
            for item in history[-10:]:
                status_emoji = "✅" if item["status"] == "success" else "❌"
                job_type = "📋" if item["type"] == "playlist" else "🎵"
                completed_time = item.get("completed", "")[:19].replace("T", " ")
                st.markdown(
                    f"{status_emoji} {job_type} {completed_time} - {item.get('message', 'Completed')}"
                )

    with tab5:
        # Library Tools Tab - Enhanced
        st.header("🔧 Library Management Tools")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🎵 Navidrome Integration")

            # FIXED: Better Navidrome status check
            navidrome_status = app.check_navidrome_status()
            st.markdown(f"**Status:** {navidrome_status}")

            if st.button("🔄 Trigger Library Scan", use_container_width=True):
                with st.spinner("Scanning library..."):
                    if app.trigger_navidrome_scan():
                        st.success("✅ Library scan triggered!")
                    else:
                        st.warning("⚠️ Scan triggered but response unclear")

            if st.button("🧹 Clean Old Jobs", use_container_width=True):
                with st.spinner("Cleaning up old jobs..."):
                    cleaned = app.job_manager.cleanup_old_jobs(
                        24
                    )  # Remove jobs older than 24 hours
                    st.success(f"✅ Cleaned {cleaned} old jobs")

        with col2:
            st.subheader("📊 Storage & Performance")

            # Real-time storage info
            try:
                result = subprocess.run(
                    ["df", "-h", "/music"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 4:
                            st.metric("Total Space", parts[1])
                            st.metric("Used Space", parts[2])
                            st.metric("Free Space", parts[3])
                            usage_pct = parts[4] if len(parts) > 4 else "Unknown"
                            st.metric("Usage", usage_pct)
            except:
                st.info("Storage info unavailable")

        # Quick links
        st.markdown("---")
        st.subheader("🔗 Quick Access")

        link_col1, link_col2, link_col3 = st.columns(3)

        with link_col1:
            st.markdown("🎵 [**Navidrome Player**](https://music.luckyverma.com)")
            st.caption("Stream your music collection")

        with link_col2:
            st.markdown("⬇️ [**qBittorrent**](https://qbittorrent.luckyverma.com)")
            st.caption("VPN-protected downloads")

        with link_col3:
            st.markdown("🎬 [**Jellyfin**](https://jellyfin.luckyverma.com)")
            st.caption("4K media streaming")


if __name__ == "__main__":
    main()
