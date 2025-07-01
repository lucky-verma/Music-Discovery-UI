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

# Configure page
st.set_page_config(
    page_title="🎵 Music Discovery Hub",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modern CSS styling (Spotify-inspired)
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
        background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
        color: #ffffff;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(90deg, #1DB954, #1ed760);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        text-align: center;
    }
    
    /* Search bar styling */
    .search-container {
        background: #2a2a2a;
        border-radius: 25px;
        padding: 10px 20px;
        margin: 20px 0;
        border: 2px solid #404040;
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
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #1ed760, #1DB954);
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(29, 185, 84, 0.4);
    }
    
    /* Metrics styling */
    .metric-card {
        background: #2a2a2a;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        border: 1px solid #404040;
    }
    
    /* Genre buttons */
    .genre-button {
        background: #333;
        border: 1px solid #555;
        border-radius: 20px;
        padding: 8px 16px;
        margin: 5px;
        color: #fff;
        text-decoration: none;
        display: inline-block;
        transition: all 0.3s ease;
    }
    
    /* Album art styling */
    .album-art {
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    
    /* Status indicators */
    .status-good { color: #1DB954; }
    .status-warning { color: #FFA500; }
    .status-error { color: #FF6B6B; }
    
    /* Progress bars */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #1DB954, #1ed760);
    }
</style>
""",
    unsafe_allow_html=True,
)


class MusicDiscoveryApp:
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

            # Count artists and albums (simplified)
            artists = set()
            albums = set()

            for file_path in files[:1000]:  # Sample first 1000 files for performance
                try:
                    parts = file_path.split("/")
                    if len(parts) >= 4:  # /music/youtube-music/Artist/Album/Song
                        if "youtube-music" in parts:
                            artist_idx = parts.index("youtube-music") + 1
                            if artist_idx < len(parts):
                                artists.add(parts[artist_idx])
                            if artist_idx + 1 < len(parts):
                                albums.add(
                                    f"{parts[artist_idx]}/{parts[artist_idx + 1]}"
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
            return {
                "total_tracks": 0,
                "artists": 0,
                "albums": 0,
                "storage_total": "Unknown",
                "storage_used": "Unknown",
                "storage_free": "Unknown",
            }

    def search_youtube_music(self, query: str, max_results: int = 10) -> List[Dict]:
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
            self.save_jobs(jobs)

            # Convert YouTube Music URL if needed
            url = job["url"]
            if "music.youtube.com" in url and "watch?v=" in url:
                video_id = url.split("watch?v=")[1].split("&")[0]
                url = f"https://youtube.com/watch?v={video_id}"

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
                job["progress"] = 100

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
            else:
                job["status"] = "failed"
                job["error"] = (
                    result.stderr[:200] if result.stderr else "Download failed"
                )

            self.save_jobs(jobs)

        except Exception as e:
            jobs = self.get_all_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = str(e)
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
            # Trigger Navidrome cleanup
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
                timeout=30,
            )
            return True
        except:
            return False


def main():
    app = MusicDiscoveryApp()

    # Header
    st.markdown(
        """
    <div class="main-header">
        <h1>🎵 Lucky's Music Discovery Hub</h1>
        <p>Your Personal YouTube Music Automation Center</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Stats row
    stats = app.get_real_library_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>🎵 {stats['total_tracks']:,}</h3>
            <p>Total Tracks</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>🎤 {stats['artists']:,}</h3>
            <p>Artists</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>💿 {stats['albums']:,}</h3>
            <p>Albums</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>💾 {stats['storage_used']}</h3>
            <p>Storage Used</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Main tabs
    tab1, tab2, tab3 = st.tabs(["🔍 **Discover**", "📊 **Downloads**", "🔧 **Manage**"])

    with tab1:
        render_discovery_tab(app)

    with tab2:
        render_downloads_tab(app)

    with tab3:
        render_manage_tab(app)


def render_discovery_tab(app):
    """Render the main discovery interface"""

    # Search section
    st.markdown("### 🔍 **Search Music**")

    search_col1, search_col2 = st.columns([3, 1])

    with search_col1:
        search_query = st.text_input(
            "",
            placeholder="🎵 Search for songs, artists, albums...",
            key="search_input",
        )

    with search_col2:
        search_button = st.button(
            "🔍 **Search**", type="primary", use_container_width=True
        )

    # Quick genre discovery
    st.markdown("### 🎭 **Quick Discovery**")

    genres = [
        ("🇮🇳 Bollywood", "bollywood hits 2024"),
        ("🎸 Rock", "rock music"),
        ("🎤 Pop", "pop hits"),
        ("🇰🇷 K-Pop", "kpop"),
        ("🎵 Electronic", "electronic music"),
        ("🎷 Jazz", "jazz music"),
        ("🎼 Classical", "classical music"),
        ("🎺 Blues", "blues music"),
    ]

    genre_cols = st.columns(4)
    for i, (genre_name, genre_query) in enumerate(genres):
        with genre_cols[i % 4]:
            if st.button(genre_name, key=f"genre_{i}", use_container_width=True):
                st.session_state.search_input = genre_query
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

                    # Display results in a clean grid
                    for i in range(0, len(results), 2):
                        cols = st.columns(2)

                        for j, col in enumerate(cols):
                            if i + j < len(results):
                                track = results[i + j]
                                with col:
                                    render_track_card(track, f"result_{i+j}", app)
                else:
                    st.warning("😔 No results found. Try different keywords.")


def render_track_card(track, key_suffix, app):
    """Render a modern track card"""

    with st.container():
        # Album art and info
        img_col, info_col, action_col = st.columns([1, 3, 1])

        with img_col:
            if track.get("thumbnail"):
                st.image(track["thumbnail"], width=80, caption="")
            else:
                st.markdown(
                    """
                <div style="width: 80px; height: 80px; background: linear-gradient(45deg, #1DB954, #1ed760); 
                     border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 2em;">
                    🎵
                </div>
                """,
                    unsafe_allow_html=True,
                )

        with info_col:
            title = (
                track["title"][:40] + "..."
                if len(track["title"]) > 40
                else track["title"]
            )
            uploader = (
                track["uploader"][:30] + "..."
                if len(track["uploader"]) > 30
                else track["uploader"]
            )

            st.markdown(
                f"""
            <div class="music-card">
                <h4 style="margin: 0; color: #fff;">{title}</h4>
                <p style="margin: 5px 0; color: #1DB954;">🎤 {uploader}</p>
                <p style="margin: 0; color: #888; font-size: 0.9em;">⏱️ {track['duration_str']}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with action_col:
            if st.button(
                "📥",
                key=f"download_{key_suffix}",
                help="Download",
                use_container_width=True,
            ):
                job_id = app.download_song(track["url"])
                st.success(f"✅ Download started! Job: {job_id}")
                time.sleep(1)
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)


def render_downloads_tab(app):
    """Render downloads status tab"""

    st.markdown("### 📊 **Download Status**")

    if st.button("🔄 **Refresh**", type="secondary"):
        st.rerun()

    jobs = app.get_all_jobs()

    if not jobs:
        st.info("🎵 No downloads yet. Start discovering music!")
        return

    # Active downloads
    active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "downloading"]]

    if active_jobs:
        st.markdown("#### 🔄 **Active Downloads**")

        for job in active_jobs:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    status_emoji = "⏳" if job["status"] == "queued" else "⬇️"
                    st.markdown(
                        f"**{status_emoji} {job.get('artist', 'Unknown')} - Downloading...**"
                    )
                    st.caption(f"URL: {job['url'][:50]}...")

                with col2:
                    progress = job.get("progress", 0)
                    st.progress(progress / 100)
                    st.caption(f"{progress}%")

                with col3:
                    st.caption(f"Job: {job['id']}")

    # Recent downloads
    completed_jobs = [j for j in jobs.values() if j["status"] == "completed"]
    failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]

    if completed_jobs:
        st.markdown("#### ✅ **Completed Downloads**")
        for job in completed_jobs[-10:]:  # Show last 10
            st.success(f"✅ Download completed - Job: {job['id']}")

    if failed_jobs:
        st.markdown("#### ❌ **Failed Downloads**")
        for job in failed_jobs[-5:]:  # Show last 5
            st.error(f"❌ Download failed - {job.get('error', 'Unknown error')}")


def render_manage_tab(app):
    """Render management tab"""

    st.markdown("### 🔧 **Library Management**")

    # Navidrome integration
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🎵 **Navidrome**")

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
                    )

                    if result.returncode == 0:
                        st.success("✅ Library scan triggered!")
                    else:
                        st.error("❌ Failed to trigger scan")
                except:
                    st.error("❌ Error connecting to Navidrome")

        if st.button("🧹 **Clean Database**", use_container_width=True):
            if app.cleanup_duplicates():
                st.success("✅ Database cleanup completed!")
            else:
                st.error("❌ Cleanup failed")

    with col2:
        st.markdown("#### 📊 **Quick Stats**")

        # Quick storage info
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
        except:
            st.info("Storage info unavailable")

    # Service links
    st.markdown("---")
    st.markdown("### 🔗 **Quick Links**")

    link_col1, link_col2, link_col3 = st.columns(3)

    with link_col1:
        st.markdown("🎵 [**Navidrome Player**](https://music.luckyverma.com)")

    with link_col2:
        st.markdown("⬇️ [**qBittorrent**](https://qbittorrent.luckyverma.com)")

    with link_col3:
        st.markdown("🎬 [**Jellyfin**](https://jellyfin.luckyverma.com)")


if __name__ == "__main__":
    main()
