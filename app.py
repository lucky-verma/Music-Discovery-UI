import streamlit as st
import subprocess
import json
import os
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
import threading
import uuid
import hashlib

# Configure page
st.set_page_config(
    page_title="🎵 Music Discovery",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modern Spotify-like CSS
st.markdown(
    """
<style>
    /* Hide Streamlit branding */
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
    
    /* Dark Spotify theme */
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
    
    /* Search styling */
    .stTextInput > div > div > input {
        background-color: #2a2a2a;
        border: 2px solid #404040;
        border-radius: 25px;
        color: white;
        padding: 12px 20px;
        font-size: 16px;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #1DB954;
        box-shadow: 0 0 10px rgba(29, 185, 84, 0.3);
    }
    
    /* Music card styling */
    .music-card {
        background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
        border-radius: 12px;
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #404040;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .music-card:hover {
        border-color: #1DB954;
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(29, 185, 84, 0.2);
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
        border: none !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #1ed760, #1DB954);
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(29, 185, 84, 0.4);
    }
    
    /* Metrics styling */
    .metric-card {
        background: linear-gradient(135deg, #2a2a2a, #333);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #404040;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    /* Genre buttons */
    .genre-btn {
        background: linear-gradient(135deg, #333, #444);
        border: 1px solid #555;
        border-radius: 20px;
        padding: 10px 20px;
        margin: 5px;
        color: #fff;
        transition: all 0.3s ease;
    }
    
    .genre-btn:hover {
        background: linear-gradient(135deg, #1DB954, #1ed760);
        transform: translateY(-2px);
    }
    
    /* Album art styling */
    .album-art {
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        transition: transform 0.3s ease;
    }
    
    .album-art:hover {
        transform: scale(1.05);
    }
    
    /* Progress bars */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #1DB954, #1ed760);
    }
    
    /* Status indicators */
    .status-good { color: #1DB954; font-weight: bold; }
    .status-warning { color: #FFA500; font-weight: bold; }
    .status-error { color: #FF6B6B; font-weight: bold; }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #2a2a2a;
        border-radius: 8px;
        color: white;
        font-weight: 600;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #1DB954;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #1DB954 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


class SimpleMusicApp:
    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
        self.ensure_config()

    def ensure_config(self):
        """Ensure config directory exists"""
        os.makedirs("/config", exist_ok=True)
        if not os.path.exists(self.jobs_file):
            with open(self.jobs_file, "w") as f:
                json.dump({}, f)

    def get_real_library_stats(self):
        """Get actual library statistics from your system"""
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

            total_size = "Unknown"
            used_size = "Unknown"
            free_size = "Unknown"

            if storage_result.returncode == 0:
                lines = storage_result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        total_size = parts[1]
                        used_size = parts[2]
                        free_size = parts[3]

            # Count unique artists and albums from file paths
            artists = set()
            albums = set()

            for file_path in files[:500]:  # Sample for performance
                try:
                    # Extract from path structure: /music/youtube-music/Artist/Album/Song
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
                "storage_total": total_size,
                "storage_used": used_size,
                "storage_free": free_size,
            }
        except Exception as e:
            st.error(f"Error getting stats: {e}")
            return {
                "total_tracks": 0,
                "artists": 0,
                "albums": 0,
                "storage_total": "Unknown",
                "storage_used": "Unknown",
                "storage_free": "Unknown",
            }

    def search_youtube_music(self, query: str, max_results: int = 12) -> List[Dict]:
        """Search YouTube Music using yt-dlp"""
        try:
            cmd = [
                "docker",
                "exec",
                "ytdl-sub",
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
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            item = json.loads(line)
                            duration = item.get("duration", 0) or 0
                            duration = int(duration) if duration else 0

                            results.append(
                                {
                                    "id": item.get("id", ""),
                                    "title": item.get("title", "Unknown"),
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
                        except:
                            continue

                return results
        except Exception as e:
            st.error(f"Search failed: {str(e)}")

        return []

    def download_song(self, url: str, artist: str = "", album: str = "") -> str:
        """Queue song for download"""
        job_id = str(uuid.uuid4())[:8]

        job = {
            "id": job_id,
            "url": url,
            "artist": artist,
            "album": album,
            "status": "queued",
            "created": datetime.now().isoformat(),
            "progress": 0,
            "message": "Queued for download",
        }

        # Save job
        jobs = self.get_all_jobs()
        jobs[job_id] = job
        self.save_jobs(jobs)

        # Start download in background
        threading.Thread(
            target=self._process_download, args=(job_id,), daemon=True
        ).start()

        return job_id

    def _process_download(self, job_id: str):
        """Process download in background"""
        try:
            jobs = self.get_all_jobs()
            job = jobs.get(job_id)
            if not job:
                return

            # Update status
            job["status"] = "downloading"
            job["progress"] = 10
            job["message"] = "Starting download..."
            self.save_jobs(jobs)

            # Convert YouTube Music URL if needed
            url = job["url"]
            if "music.youtube.com" in url and "watch?v=" in url:
                video_id = url.split("watch?v=")[1].split("&")[0]
                url = f"https://youtube.com/watch?v={video_id}"

            # Update progress
            job["progress"] = 30
            job["message"] = "Downloading audio..."
            self.save_jobs(jobs)

            # Download using ytdl-sub
            cmd = [
                "docker",
                "exec",
                "ytdl-sub",
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "320K",
                "--embed-thumbnail",
                "--add-metadata",
                "--no-playlist",
                "--output",
                "/music/youtube-music/%(uploader)s/%(title)s.%(ext)s",
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                job["status"] = "completed"
                job["progress"] = 90
                job["message"] = "Triggering library scan..."
                self.save_jobs(jobs)

                # Trigger Navidrome scan
                try:
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
                    )
                except:
                    pass

                job["status"] = "completed"
                job["progress"] = 100
                job["message"] = "Download completed!"
            else:
                job["status"] = "failed"
                job["progress"] = 0
                job["message"] = (
                    f"Download failed: {result.stderr[:100] if result.stderr else 'Unknown error'}"
                )

            self.save_jobs(jobs)

        except Exception as e:
            jobs = self.get_all_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["progress"] = 0
                jobs[job_id]["message"] = f"Error: {str(e)}"
                self.save_jobs(jobs)

    def get_all_jobs(self) -> Dict:
        """Get all download jobs"""
        try:
            with open(self.jobs_file, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_jobs(self, jobs: Dict):
        """Save jobs to file"""
        try:
            with open(self.jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)
        except:
            pass

    def cleanup_duplicates(self):
        """Simple duplicate cleanup for Navidrome"""
        try:
            # Trigger Navidrome cleanup scan
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "navidrome",
                    "curl",
                    "-X",
                    "POST",
                    "http://localhost:4533/api/scanner/scan",
                ],
                timeout=30,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except:
            return False


def main():
    app = SimpleMusicApp()

    # Header
    st.markdown(
        """
    <div class="main-header">
        <h1>🎵 Lucky's Music Discovery Hub</h1>
        <p>Unlimited YouTube Music Downloads • Spotify-Style Discovery • Zero Subscriptions</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Real Stats Dashboard
    stats = app.get_real_library_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
        <div class="metric-card">
            <h2 style="color: #1DB954; margin: 0;">🎵 {stats['total_tracks']:,}</h2>
            <p style="margin: 5px 0 0 0; color: #ccc;">Total Tracks</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
        <div class="metric-card">
            <h2 style="color: #1DB954; margin: 0;">🎤 {stats['artists']:,}</h2>
            <p style="margin: 5px 0 0 0; color: #ccc;">Artists</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
        <div class="metric-card">
            <h2 style="color: #1DB954; margin: 0;">💿 {stats['albums']:,}</h2>
            <p style="margin: 5px 0 0 0; color: #ccc;">Albums</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
        <div class="metric-card">
            <h2 style="color: #1DB954; margin: 0;">💾 {stats['storage_used']}</h2>
            <p style="margin: 5px 0 0 0; color: #ccc;">Storage Used</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Main interface
    tab1, tab2, tab3 = st.tabs(
        ["🔍 **Discover & Download**", "📊 **Download Status**", "🔧 **Library Tools**"]
    )

    with tab1:
        render_discovery_tab(app)

    with tab2:
        render_downloads_tab(app)

    with tab3:
        render_tools_tab(app)


def render_discovery_tab(app):
    """Render the main discovery interface"""

    # Search section
    st.markdown("### 🔍 **Search & Discover Music**")

    search_col1, search_col2 = st.columns([4, 1])

    with search_col1:
        search_query = st.text_input(
            "",
            placeholder="🎵 Search for songs, artists, albums... (e.g., 'Arijit Singh', 'Bollywood hits', 'rock music')",
            key="main_search",
        )

    with search_col2:
        search_button = st.button(
            "🔍 **Search**", type="primary", use_container_width=True
        )

    # Quick genre discovery
    st.markdown("### 🎭 **Quick Discovery**")

    # Popular genres with direct search
    genres = [
        ("🇮🇳 Bollywood Hits", "bollywood hits 2024"),
        ("🎸 Rock Classics", "rock music hits"),
        ("🎤 Pop Charts", "pop music 2024"),
        ("🇰🇷 K-Pop", "kpop hits 2024"),
        ("🎵 Electronic", "electronic music"),
        ("🎷 Jazz", "jazz classics"),
        ("🎼 Classical", "classical music"),
        ("🏴‍☠️ Old School", "90s hits"),
    ]

    genre_cols = st.columns(4)
    for i, (genre_name, genre_query) in enumerate(genres):
        with genre_cols[i % 4]:
            if st.button(genre_name, key=f"genre_{i}", use_container_width=True):
                st.session_state.main_search = genre_query
                st.rerun()

    # Search results
    if search_button or search_query:
        if search_query:
            with st.spinner("🎵 Searching YouTube Music..."):
                results = app.search_youtube_music(search_query)

                if results:
                    st.markdown(
                        f"### 🎵 **Found {len(results)} results for '{search_query}'**"
                    )

                    # Display results in compact grid (3 columns)
                    for i in range(0, len(results), 3):
                        cols = st.columns(3)

                        for j, col in enumerate(cols):
                            if i + j < len(results):
                                track = results[i + j]
                                with col:
                                    render_compact_track_card(
                                        track, f"result_{i+j}", app
                                    )
                else:
                    st.warning(
                        "😔 No results found. Try different keywords or check spelling."
                    )


def render_compact_track_card(track, key_suffix, app):
    """Render a compact track card with album art"""

    with st.container():
        # Album art
        if track.get("thumbnail"):
            st.image(track["thumbnail"], width=150)
        else:
            st.markdown(
                """
            <div style="width: 150px; height: 100px; background: linear-gradient(45deg, #1DB954, #1ed760); 
                 border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 2em; margin-bottom: 10px;">
                🎵
            </div>
            """,
                unsafe_allow_html=True,
            )

        # Track info
        title = (
            track["title"][:35] + "..." if len(track["title"]) > 35 else track["title"]
        )
        uploader = (
            track["uploader"][:25] + "..."
            if len(track["uploader"]) > 25
            else track["uploader"]
        )

        st.markdown(
            f"""
        <div style="padding: 5px 0;">
            <div style="font-weight: bold; font-size: 14px; margin-bottom: 3px; color: #fff;">
                {title}
            </div>
            <div style="color: #1DB954; font-size: 12px; margin-bottom: 3px;">
                🎤 {uploader}
            </div>
            <div style="color: #888; font-size: 11px;">
                ⏱️ {track['duration_str']}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Download button
        if st.button(
            "📥 **Download**", key=f"download_{key_suffix}", use_container_width=True
        ):
            job_id = app.download_song(track["url"])
            st.success(f"✅ Download started! Job: {job_id}")
            time.sleep(1)
            st.rerun()


def render_downloads_tab(app):
    """Render downloads status tab"""

    st.markdown("### 📊 **Download Status & History**")

    if st.button("🔄 **Refresh Status**", type="secondary"):
        st.rerun()

    jobs = app.get_all_jobs()

    if not jobs:
        st.info(
            "🎵 No downloads yet. Go to the Discover tab to start downloading music!"
        )
        return

    # Active downloads
    active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "downloading"]]

    if active_jobs:
        st.markdown("#### 🔄 **Active Downloads**")

        for job in active_jobs:
            with st.container():
                col1, col2, col3 = st.columns([4, 1, 1])

                with col1:
                    status_emoji = "⏳" if job["status"] == "queued" else "⬇️"
                    st.markdown(f"**{status_emoji} Downloading...**")
                    st.caption(f"URL: {job['url'][:60]}...")
                    st.caption(f"Status: {job.get('message', 'Processing...')}")

                with col2:
                    progress = job.get("progress", 0)
                    st.progress(progress / 100)
                    st.caption(f"{progress}%")

                with col3:
                    st.caption(f"Job: {job['id']}")

    # Recent downloads (completed and failed)
    completed_jobs = [j for j in jobs.values() if j["status"] == "completed"]
    failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]

    col1, col2 = st.columns(2)

    with col1:
        if completed_jobs:
            st.markdown("#### ✅ **Recent Completed**")
            for job in completed_jobs[-5:]:  # Show last 5
                created_time = job.get("created", "")[:19].replace("T", " ")
                st.success(f"✅ Download completed - {created_time}")

    with col2:
        if failed_jobs:
            st.markdown("#### ❌ **Recent Failed**")
            for job in failed_jobs[-3:]:  # Show last 3
                st.error(f"❌ {job.get('message', 'Download failed')}")


def render_tools_tab(app):
    """Render library management tools"""

    st.markdown("### 🔧 **Library Management Tools**")

    # Navidrome integration
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🎵 **Navidrome Integration**")

        if st.button("🔄 **Trigger Library Scan**", use_container_width=True):
            with st.spinner("Scanning library..."):
                try:
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            "navidrome",
                            "curl",
                            "-X",
                            "POST",
                            "http://localhost:4533/api/scanner/scan",
                        ],
                        timeout=30,
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode == 0:
                        st.success("✅ Library scan triggered!")
                    else:
                        st.error("❌ Failed to trigger scan")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

        if st.button("🧹 **Clean Duplicates**", use_container_width=True):
            with st.spinner("Cleaning duplicates..."):
                if app.cleanup_duplicates():
                    st.success("✅ Duplicate cleanup completed!")
                else:
                    st.error("❌ Cleanup failed")

    with col2:
        st.markdown("#### 📊 **Storage Information**")

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

                        # Usage percentage
                        usage_pct = parts[4] if len(parts) > 4 else "Unknown"
                        st.metric("Usage", usage_pct)
        except:
            st.info("Storage info unavailable")

    # Quick links
    st.markdown("---")
    st.markdown("### 🔗 **Quick Access**")

    link_col1, link_col2, link_col3 = st.columns(3)

    with link_col1:
        st.markdown("🎵 [**Navidrome Player**](https://music.luckyverma.com)")

    with link_col2:
        st.markdown("⬇️ [**qBittorrent**](https://qbittorrent.luckyverma.com)")

    with link_col3:
        st.markdown("🎬 [**Jellyfin**](https://jellyfin.luckyverma.com)")

    # Footer info
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; color: #666; padding: 20px;">
        🎵 <strong>Lucky's Music Empire</strong> | Zero Subscriptions • Unlimited Downloads • Complete Ownership<br>
        🏠 <a href="https://music.luckyverma.com" target="_blank" style="color: #1DB954;">Stream Your Music</a> | 
        📱 Access from anywhere via HTTPS
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
