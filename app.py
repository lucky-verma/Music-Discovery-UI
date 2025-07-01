import streamlit as st
import subprocess
import json
import os
import requests
import time
from datetime import datetime
import threading
import uuid

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
    }
</style>
""",
    unsafe_allow_html=True,
)


class SimpleMusicApp:
    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
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

    def search_youtube_music(self, query, max_results=12):
        """Search YouTube Music"""
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
                lines = result.stdout.strip().split("\n")

                for line in lines:
                    if line.strip():
                        try:
                            item = json.loads(line)
                            duration = int(item.get("duration", 0) or 0)

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

    def download_song(self, url, artist="", album=""):
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

    def _process_download(self, job_id):
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
                job["url"],
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

    def get_all_jobs(self):
        """Get all download jobs"""
        try:
            with open(self.jobs_file, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_jobs(self, jobs):
        """Save jobs to file"""
        try:
            with open(self.jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)
        except:
            pass

    def fix_navidrome_duplicates(self):
        """Fix greyed out tracks in Navidrome"""
        try:
            # Trigger Navidrome scan to clean up database
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
    # Initialize app
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
        st.metric("Total Tracks", stats["total_tracks"])
    with col2:
        st.metric("Artists", stats["artists"])
    with col3:
        st.metric("Albums", stats["albums"])
    with col4:
        st.metric("Storage Used", stats["storage_used"])

    # Main tabs
    tab1, tab2, tab3 = st.tabs(
        ["🔍 **Discover & Download**", "📊 **Download Status**", "🔧 **Library Tools**"]
    )

    with tab1:
        # Search interface
        st.header("🔍 Search & Discover Music")

        # FIXED: Don't manipulate session state directly - use form and key properly
        search_query = st.text_input(
            "",
            placeholder="🎵 Search for songs, artists, albums... (e.g., 'Arijit Singh', 'Bollywood hits', 'rock music')",
            key="search_input",
        )

        if search_query and st.button("🔍 Search", type="primary"):
            with st.spinner("🎵 Searching YouTube Music..."):
                results = app.search_youtube_music(search_query)

                if results:
                    st.success(f"Found {len(results)} results for '{search_query}'")

                    # Display results in card grid
                    for i in range(0, len(results), 3):
                        cols = st.columns(3)

                        for j, col in enumerate(cols):
                            if i + j < len(results):
                                track = results[i + j]
                                with col:
                                    # Album art
                                    if track.get("thumbnail"):
                                        st.image(track["thumbnail"], width=150)

                                    # Track info
                                    title = (
                                        track["title"][:35] + "..."
                                        if len(track["title"]) > 35
                                        else track["title"]
                                    )
                                    uploader = (
                                        track["uploader"][:25] + "..."
                                        if len(track["uploader"]) > 25
                                        else track["uploader"]
                                    )

                                    st.markdown(f"**{title}**")
                                    st.caption(
                                        f"🎤 {uploader} | ⏱️ {track['duration_str']}"
                                    )

                                    # Download button
                                    if st.button("📥 Download", key=f"dl_{i+j}"):
                                        job_id = app.download_song(track["url"])
                                        st.success(
                                            f"✅ Download started! Job: {job_id}"
                                        )
                else:
                    st.warning("No results found. Try different keywords.")

        # Quick discovery
        st.header("🎭 Quick Discovery")

        # Define genre buttons - FIXED: No direct session state modification
        genres = [
            ("🇮🇳 Bollywood Hits", "bollywood hits 2024"),
            ("🎸 Rock Hits", "rock music hits"),
            ("🎤 Pop Charts", "pop music 2024"),
            ("🇰🇷 K-Pop", "kpop hits 2024"),
            ("🎵 Electronic", "electronic music"),
            ("🎷 Jazz", "jazz classics"),
            ("🎼 Classical", "classical music"),
            ("🏴‍☠️ Old School", "90s hits"),
        ]

        # Create genre buttons in 4 columns
        genre_cols = st.columns(4)
        for i, (genre_name, genre_query) in enumerate(genres):
            with genre_cols[i % 4]:
                # FIXED: Use button click to trigger search directly, not session state
                if st.button(genre_name, key=f"genre_{i}", use_container_width=True):
                    # Search directly when button is clicked instead of modifying session state
                    with st.spinner(f"Finding {genre_name} music..."):
                        results = app.search_youtube_music(genre_query, max_results=12)

                        if results:
                            st.success(f"Found {len(results)} {genre_name} tracks")

                            # Display results in a clean grid
                            for j in range(0, len(results), 3):
                                result_cols = st.columns(3)

                                for k, col in enumerate(result_cols):
                                    if j + k < len(results):
                                        track = results[j + k]
                                        with col:
                                            # Album art
                                            if track.get("thumbnail"):
                                                st.image(track["thumbnail"], width=150)

                                            # Track info
                                            title = (
                                                track["title"][:35] + "..."
                                                if len(track["title"]) > 35
                                                else track["title"]
                                            )
                                            uploader = (
                                                track["uploader"][:25] + "..."
                                                if len(track["uploader"]) > 25
                                                else track["uploader"]
                                            )

                                            st.markdown(f"**{title}**")
                                            st.caption(
                                                f"🎤 {uploader} | ⏱️ {track['duration_str']}"
                                            )

                                            # Download button
                                            if st.button(
                                                "📥 Download", key=f"genre_dl_{j+k}"
                                            ):
                                                job_id = app.download_song(track["url"])
                                                st.success(
                                                    f"✅ Download started! Job: {job_id}"
                                                )
                        else:
                            st.warning(f"No {genre_name} results found.")

    with tab2:
        # Download status tab
        st.header("📊 Download Status & History")

        if st.button("🔄 Refresh", key="refresh_status"):
            st.rerun()

        jobs = app.get_all_jobs()

        if not jobs:
            st.info("No downloads yet. Search for music to start downloading!")
            return

        # Active downloads
        active_jobs = [
            j for j in jobs.values() if j["status"] in ["queued", "downloading"]
        ]

        if active_jobs:
            st.subheader("🔄 Active Downloads")

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

        # Completed downloads
        completed_jobs = [j for j in jobs.values() if j["status"] == "completed"]
        if completed_jobs:
            st.subheader("✅ Completed Downloads")
            for job in completed_jobs[-10:]:  # Last 10
                created_time = job.get("created", "")[:19].replace("T", " ")
                st.success(
                    f"✅ {created_time} - {job['url'].split('/')[-1].split('=')[-1]}"
                )

        # Failed downloads
        failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]
        if failed_jobs:
            st.subheader("❌ Failed Downloads")
            for job in failed_jobs[-5:]:  # Last 5
                st.error(f"❌ {job.get('message', 'Download failed')}")

    with tab3:
        # Library tools tab
        st.header("🔧 Library Management")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🎵 Navidrome Integration")

            if st.button("🔄 Trigger Library Scan", use_container_width=True):
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
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            if st.button("🧹 Fix Duplicates/Greyed Out", use_container_width=True):
                with st.spinner("Fixing database issues..."):
                    if app.fix_navidrome_duplicates():
                        st.success("✅ Cleanup process completed!")
                    else:
                        st.error("❌ Cleanup failed")

        with col2:
            st.subheader("🔗 Quick Links")

            st.markdown("🎵 **Music Services:**")
            st.markdown("🎧 [Navidrome Player](https://music.luckyverma.com)")
            st.markdown(
                "📱 [Download Interface](https://music-download.luckyverma.com)"
            )

            st.markdown("**Library Paths:**")
            st.code("/music/youtube-music/")
            st.code("/music/library/")

        # Storage info
        try:
            result = subprocess.run(
                ["df", "-h", "/music"], capture_output=True, text=True
            )
            if result.returncode == 0:
                st.subheader("💾 Storage Information")
                st.code(result.stdout)
        except:
            pass

        # Footer info
        st.markdown("---")
        st.markdown(
            """
        <div style="text-align: center; color: #666; font-size: 0.8em;">
            🎵 Lucky's Music Empire | Built with Streamlit | Powered by ytdl-sub
        </div>
        """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
