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

# IMPROVED: Modern Spotify-like CSS with all enhancements
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
    
    /* Dark theme with better contrast */
    .stApp {
        background: linear-gradient(135deg, #121212 0%, #1e1e1e 100%);
        color: #ffffff;
    }
    
    /* FIXED: Better text colors for metrics */
    .metric-container {
        background: rgba(29, 185, 84, 0.1);
        border-radius: 8px;
        padding: 15px;
        border: 1px solid rgba(29, 185, 84, 0.2);
    }
    
    /* Force white text for metrics */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
        border: 1px solid #404040;
        border-radius: 12px;
        padding: 20px;
    }
    
    [data-testid="metric-container"] > div {
        color: #ffffff !important;
    }
    
    [data-testid="metric-container"] [data-testid="metric-label"] {
        color: #b3b3b3 !important;
        font-weight: 600;
    }
    
    [data-testid="metric-container"] [data-testid="metric-value"] {
        color: #1DB954 !important;
        font-weight: 700;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(90deg, #1DB954, #1ed760);
        padding: 25px;
        border-radius: 12px;
        margin-bottom: 25px;
        text-align: center;
        box-shadow: 0 6px 25px rgba(29, 185, 84, 0.3);
    }
    
    /* IMPROVED: Subtle download button styling */
    .stButton > button {
        background: linear-gradient(135deg, #333333, #404040);
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 20px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 13px;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #1DB954, #1ed760);
        border-color: #1DB954;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(29, 185, 84, 0.3);
        color: #ffffff;
    }
    
    .stButton > button:active {
        transform: translateY(0px);
        box-shadow: 0 2px 6px rgba(29, 185, 84, 0.2);
    }
    
    /* IMPROVED: Music card styling with better spacing */
    .music-card {
        background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
        border-radius: 12px;
        padding: 12px;
        margin: 8px 0;
        border: 1px solid #404040;
        transition: all 0.3s ease;
        min-height: 280px;
        display: flex;
        flex-direction: column;
    }
    
    .music-card:hover {
        border-color: #1DB954;
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(29, 185, 84, 0.2);
    }
    
    /* IMPROVED: Results container with better spacing */
    .results-container {
        width: 100%;
        margin: 20px 0;
    }
    
    /* Better image container for 8 columns */
    .stImage > img {
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
        transition: transform 0.2s ease !important;
    }
    
    .stImage:hover > img {
        transform: scale(1.02) !important;
    }
    
    /* Playlist section styling */
    .playlist-section {
        background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
        border-radius: 12px;
        padding: 25px;
        margin: 20px 0;
        border: 1px solid #404040;
    }
    
    /* IMPROVED: Better text colors */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ffffff !important;
    }
    
    .stMarkdown p {
        color: #e0e0e0 !important;
    }
    
    .stCaption {
        color: #b3b3b3 !important;
    }
    
    /* SUCCESS/ERROR messages styling */
    .stSuccess {
        background: rgba(29, 185, 84, 0.15) !important;
        border: 1px solid rgba(29, 185, 84, 0.3) !important;
        color: #1DB954 !important;
    }
    
    /* SMOOTH: Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
        border-radius: 8px;
        border: 1px solid #404040;
        color: #ffffff;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: linear-gradient(135deg, #1DB954, #1ed760);
        border-color: #1DB954;
    }
    
    /* Loading spinner custom color */
    .stSpinner > div {
        border-color: #1DB954 !important;
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


# IMPROVED: Instant download handler with session state
def handle_download(app, track_url, track_title, key_suffix=""):
    """Handle download without causing app rerun"""
    if f"downloaded_{key_suffix}" not in st.session_state:
        st.session_state[f"downloaded_{key_suffix}"] = False

    # Check if already downloaded
    if st.session_state[f"downloaded_{key_suffix}"]:
        return st.button(
            "✅ Queued", key=f"dl_{key_suffix}", disabled=True, use_container_width=True
        )

    # Download button
    if st.button("📥 Download", key=f"dl_{key_suffix}", use_container_width=True):
        # Immediately mark as downloaded to prevent lag
        st.session_state[f"downloaded_{key_suffix}"] = True

        # Queue download in background
        job_id = app.download_song(track_url)

        # Use toast instead of st.success to avoid rerun
        st.toast(f"🎵 Queued: {track_title[:30]}...", icon="✅")

        # Return True to indicate download was initiated
        return True

    return False


def main():
    # Initialize app
    app = EnhancedMusicApp()

    # IMPROVED: Initialize session state for smooth UX
    if "download_queue" not in st.session_state:
        st.session_state.download_queue = set()

    if "last_search" not in st.session_state:
        st.session_state.last_search = ""

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

    # IMPROVED: Better metrics display
    stats = app.get_real_library_stats()

    st.markdown('<div class="metrics-row">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tracks", f"{stats['total_tracks']:,}")
    with col2:
        st.metric("Artists", f"{stats['artists']:,}")
    with col3:
        st.metric("Albums", f"{stats['albums']:,}")
    with col4:
        st.metric("Storage Used", stats["storage_used"])
    st.markdown("</div>", unsafe_allow_html=True)

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
                                # IMPROVED: Larger album art for 8 columns
                                if track.get("thumbnail"):
                                    st.image(
                                        track["thumbnail"], width=140
                                    )  # Increased from 120 to 140

                                # Track info with better spacing
                                title = (
                                    track["title"][:22] + "..."
                                    if len(track["title"]) > 22
                                    else track["title"]
                                )
                                uploader = (
                                    track["uploader"][:18] + "..."
                                    if len(track["uploader"]) > 18
                                    else track["uploader"]
                                )

                                st.markdown(f"**{title}**")
                                st.caption(f"🎤 {uploader}")
                                st.caption(f"⏱️ {track['duration_str']}")

                                # IMPROVED: Instant download
                                handle_download(
                                    app, track["url"], track["title"], f"{offset+i+j}"
                                )

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

        # Quick discovery - KEEPING YOUR CHANGED GENRES
        st.header("🎭 Quick Discovery")
        genres = [
            (" 🎥 Bollywood Hits", "latest bollywood songs"),
            (" 🎶 Punjabi Hits", "famous punjabi songs"),
            (" 🎤 Hindi Rap", "latest hindi rap songs"),
            (" 💃 Hip Hop", "latest hip hop & pop songs"),
            (" 🕺 EDM", "latest edm songs"),
            (" 🎶 Bollywood Remix", "latest bollywood remix songs"),
            (" 🎤 Arijit Singh", "latest arijit singh songs"),
            (" 🎧 Bollywood 2000s", "best Bollywood 2000s songs"),
        ]

        # IMPROVED: Create genre buttons in 8 columns
        genre_cols = st.columns(8)
        for i, (genre_name, genre_query) in enumerate(genres):
            with genre_cols[i % 8]:
                if st.button(
                    genre_name,
                    key=f"genre_{i}",
                    use_container_width=True,
                    help=f"Discover {genre_name.lower()} music",
                ):
                    # Use session state to prevent lag
                    st.session_state.genre_query = genre_query
                    st.session_state.genre_name = genre_name
                    st.toast(f"🎵 Loading {genre_name}...", icon="🔍")
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
                                        st.image(track["thumbnail"], width=150)

                                    title = (
                                        track["title"][:22] + "..."
                                        if len(track["title"]) > 22
                                        else track["title"]
                                    )
                                    uploader = (
                                        track["uploader"][:18] + "..."
                                        if len(track["uploader"]) > 18
                                        else track["uploader"]
                                    )

                                    st.markdown(f"**{title}**")
                                    st.caption(f"🎤 {uploader}")
                                    st.caption(f"⏱️ {track['duration_str']}")

                                    # IMPROVED: Instant download for genre results
                                    handle_download(
                                        app,
                                        track["url"],
                                        track["title"],
                                        f"genre_{j+k}",
                                    )

                    st.markdown("</div>", unsafe_allow_html=True)

                    # Clear results button
                    if st.button("🗑️ Clear Results"):
                        del st.session_state.genre_query
                        del st.session_state.genre_name
                        st.rerun()

    with tab2:
        # IMPLEMENTED: Spotify Sync Tab (placeholder for now, can be enhanced later)
        st.header("🎵 Spotify Library Sync")

        st.markdown('<div class="spotify-section">', unsafe_allow_html=True)

        st.markdown("### 🔗 Connect Your Spotify Account")
        st.info(
            "💡 Connect your Spotify account to automatically download your saved tracks and playlists using yt-dlp"
        )

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

        if st.button("🔗 Connect Spotify", type="primary"):
            if client_id and client_secret:
                with st.spinner("Connecting to Spotify..."):
                    if app.spotify_service.set_credentials(client_id, client_secret):
                        st.success("✅ Successfully connected to Spotify!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to connect. Check your credentials.")
            else:
                st.error("Please enter both Client ID and Client Secret")

        # Check if Spotify is connected
        if app.config.get("spotify.access_token"):
            st.success("🟢 Spotify Connected!")

            st.markdown("### 📚 Your Spotify Library")

            # Sync options
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 Sync Saved Tracks", use_container_width=True):
                    with st.spinner("Fetching your saved tracks..."):
                        st.info("Feature coming soon! Will sync your liked songs.")

            with col2:
                if st.button("📋 Sync Playlists", use_container_width=True):
                    with st.spinner("Fetching your playlists..."):
                        st.info("Feature coming soon! Will sync your playlists.")

            # Search Spotify library
            st.markdown("### 🔍 Search Your Spotify Library")
            spotify_query = st.text_input(
                "Search your Spotify tracks:", placeholder="Search your saved music..."
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
                                            st.image(track["album_art"], width=140)

                                        st.markdown(f"**{track['name'][:22]}**")
                                        st.caption(
                                            f"🎤 {', '.join(track['artists'][:2])}"
                                        )
                                        st.caption(f"💿 {track['album'][:18]}")

                                        # Download equivalent from YouTube
                                        if st.button(
                                            "📥 Download from YT",
                                            key=f"spotify_dl_{i+j}",
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
                                            st.toast(f"✅ Queued: {track['name']}")

        else:
            st.warning("🔗 Connect your Spotify account to access sync features")

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
                        st.toast(f"📋 Playlist queued! Job: {job_id}")
                        processed_count += 1
                    elif "youtube.com/watch" in url or "music.youtube.com" in url:
                        job_id = app.download_song(url)
                        st.toast(f"🎵 Song queued! Job: {job_id}")
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
