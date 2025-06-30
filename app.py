import streamlit as st
import subprocess
import os
import json
import re
from datetime import datetime
import pandas as pd
import time
import threading
import uuid
from typing import Dict, List, Optional
import requests

# Set page config
st.set_page_config(
    page_title="🎵 Lucky's Music Discovery Hub",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark theme
st.markdown(
    """
<style>
    .main > div {
        padding: 2rem;
    }
    .stButton > button {
        background: linear-gradient(45deg, #ff6b6b, #ee5a24);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
    }
    .success-box {
        background: #2d5016;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #4caf50;
        margin: 1rem 0;
    }
    .error-box {
        background: #5d1e1e;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #f44336;
        margin: 1rem 0;
    }
    .info-box {
        background: #1e3a5f;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #2196f3;
        margin: 1rem 0;
    }
    .job-status-running {
        background: #2c3e50;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border-left: 3px solid #f39c12;
        margin: 0.5rem 0;
    }
    .job-status-completed {
        background: #27ae60;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border-left: 3px solid #2ecc71;
        margin: 0.5rem 0;
    }
    .job-status-failed {
        background: #c0392b;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border-left: 3px solid #e74c3c;
        margin: 0.5rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)


class JobManager:
    """Simple job queue for background downloads"""

    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
        self.ensure_jobs_file()

    def ensure_jobs_file(self):
        if not os.path.exists(self.jobs_file):
            with open(self.jobs_file, "w") as f:
                json.dump({}, f)

    def add_job(self, job_type: str, url: str, metadata: Dict) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "type": job_type,
            "url": url,
            "metadata": metadata,
            "status": "queued",
            "created": datetime.now().isoformat(),
            "progress": 0,
            "message": "Queued for download",
        }

        jobs = self.get_all_jobs()
        jobs[job_id] = job

        with open(self.jobs_file, "w") as f:
            json.dump(jobs, f, indent=2)

        # Start download in background thread
        thread = threading.Thread(target=self._process_job, args=(job_id,))
        thread.daemon = True
        thread.start()

        return job_id

    def get_all_jobs(self) -> Dict:
        try:
            with open(self.jobs_file, "r") as f:
                return json.load(f)
        except:
            return {}

    def update_job(
        self, job_id: str, status: str, progress: int = None, message: str = None
    ):
        jobs = self.get_all_jobs()
        if job_id in jobs:
            jobs[job_id]["status"] = status
            if progress is not None:
                jobs[job_id]["progress"] = progress
            if message is not None:
                jobs[job_id]["message"] = message
            jobs[job_id]["updated"] = datetime.now().isoformat()

            with open(self.jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)

    def _process_job(self, job_id: str):
        jobs = self.get_all_jobs()
        job = jobs.get(job_id)
        if not job:
            return

        try:
            self.update_job(job_id, "running", 0, "Starting download...")

            if job["type"] == "single_song":
                success = self._download_single_song(
                    job_id, job["url"], job["metadata"]
                )
            elif job["type"] == "playlist":
                success = self._download_playlist(job_id, job["url"], job["metadata"])
            else:
                self.update_job(job_id, "failed", 0, "Unknown job type")
                return

            if success:
                self.update_job(
                    job_id, "completed", 100, "Download completed successfully!"
                )
            else:
                self.update_job(job_id, "failed", 0, "Download failed")

        except Exception as e:
            self.update_job(job_id, "failed", 0, f"Error: {str(e)}")

    def _download_single_song(self, job_id: str, url: str, metadata: Dict) -> bool:
        try:
            self.update_job(job_id, "running", 25, "Processing URL...")

            # Handle YouTube Music URLs
            if "music.youtube.com" in url:
                # Convert YouTube Music URL to regular YouTube URL
                if "watch?v=" in url:
                    video_id = url.split("watch?v=")[1].split("&")[0]
                    url = f"https://youtube.com/watch?v={video_id}"

            # Create output path
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")

            if artist and album:
                output_template = (
                    f"/music/youtube-music/{artist}/{album}/%(title)s.%(ext)s"
                )
            elif artist:
                output_template = f"/music/youtube-music/{artist}/%(title)s.%(ext)s"
            else:
                output_template = "/music/youtube-music/%(uploader)s/%(title)s.%(ext)s"

            self.update_job(job_id, "running", 50, "Downloading audio...")

            # Use Docker exec to run yt-dlp
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
                output_template,
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                self.update_job(job_id, "running", 90, "Triggering library scan...")
                # Trigger Navidrome rescan
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
                return True
            else:
                self.update_job(
                    job_id, "failed", 0, f"Download error: {result.stderr[:200]}"
                )
                return False

        except Exception as e:
            self.update_job(job_id, "failed", 0, f"Exception: {str(e)}")
            return False

    def _download_playlist(self, job_id: str, url: str, metadata: Dict) -> bool:
        try:
            self.update_job(job_id, "running", 10, "Processing playlist URL...")

            # Handle YouTube Music URLs
            if "music.youtube.com" in url:
                # Convert YouTube Music playlist URL to regular YouTube URL
                if "playlist?list=" in url:
                    playlist_id = url.split("playlist?list=")[1].split("&")[0]
                    url = f"https://youtube.com/playlist?list={playlist_id}"

            playlist_name = metadata.get("playlist_name", "Downloaded Playlist")
            output_dir = f"/music/youtube-music/{playlist_name}"

            self.update_job(job_id, "running", 30, "Starting playlist download...")

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
                "--yes-playlist",
                "--output",
                f"{output_dir}/%(uploader)s/%(playlist_title)s/%(playlist_index)02d - %(title)s.%(ext)s",
                url,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1800
            )  # 30 min timeout

            if result.returncode == 0:
                self.update_job(job_id, "running", 90, "Triggering library scan...")
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
                return True
            else:
                return False

        except Exception as e:
            return False


class SpotifyIntegration:
    """Spotify Web API integration for playlist discovery"""

    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.access_token = None

    def set_credentials(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._get_access_token()

    def _get_access_token(self):
        """Get Spotify access token using client credentials flow"""
        if not self.client_id or not self.client_secret:
            return False

        try:
            import base64

            # Encode credentials
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()

            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {"grant_type": "client_credentials"}

            response = requests.post(
                "https://accounts.spotify.com/api/token", headers=headers, data=data
            )

            if response.status_code == 200:
                self.access_token = response.json()["access_token"]
                return True
            return False
        except:
            return False

    def get_playlist_tracks(self, playlist_url: str) -> List[Dict]:
        """Get tracks from Spotify playlist"""
        if not self.access_token:
            return []

        try:
            # Extract playlist ID from URL
            playlist_id = playlist_url.split("playlist/")[1].split("?")[0]

            headers = {"Authorization": f"Bearer {self.access_token}"}

            tracks = []
            offset = 0
            limit = 50

            while True:
                url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?offset={offset}&limit={limit}"
                response = requests.get(url, headers=headers)

                if response.status_code != 200:
                    break

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                for item in items:
                    track = item.get("track", {})
                    if track and track.get("type") == "track":
                        artists = ", ".join(
                            [artist["name"] for artist in track.get("artists", [])]
                        )
                        tracks.append(
                            {
                                "name": track.get("name", ""),
                                "artists": artists,
                                "album": track.get("album", {}).get("name", ""),
                                "search_query": f"{artists} {track.get('name', '')}",
                            }
                        )

                offset += limit
                if len(items) < limit:
                    break

            return tracks
        except:
            return []


class MusicDownloader:
    def __init__(self):
        self.config_path = "/config"
        self.music_path = "/music/youtube-music"
        self.job_manager = JobManager()
        self.spotify = SpotifyIntegration()

    def validate_url(self, url):
        """Validate YouTube/YouTube Music URL"""
        patterns = [
            r"youtube\.com/watch\?v=",
            r"youtu\.be/",
            r"music\.youtube\.com/watch\?v=",
            r"music\.youtube\.com/playlist\?list=",
            r"youtube\.com/playlist\?list=",
            r"youtube\.com/channel/",
            r"music\.youtube\.com/channel/",
        ]
        return any(re.search(pattern, url) for pattern in patterns)

    def extract_video_info(self, url):
        """Extract basic info from URL without downloading"""
        try:
            # Handle YouTube Music URLs
            if "music.youtube.com" in url:
                if "watch?v=" in url:
                    video_id = url.split("watch?v=")[1].split("&")[0]
                    url = f"https://youtube.com/watch?v={video_id}"

            cmd = [
                "docker",
                "exec",
                "ytdl-sub",
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--flat-playlist",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if lines and lines[0].strip():
                    info = json.loads(lines[0])
                    return {
                        "title": info.get("title", "Unknown"),
                        "uploader": info.get("uploader", "Unknown"),
                        "duration": info.get("duration", 0),
                        "view_count": info.get("view_count", 0),
                    }
        except Exception as e:
            st.error(f"Error extracting info: {str(e)}")
        return None

    def download_single_song_background(self, url, artist=None, album=None):
        """Queue single song for background download"""
        metadata = {"artist": artist, "album": album}
        job_id = self.job_manager.add_job("single_song", url, metadata)
        return job_id

    def download_playlist_background(self, url, playlist_name=None):
        """Queue playlist for background download"""
        metadata = {"playlist_name": playlist_name or "Downloaded Playlist"}
        job_id = self.job_manager.add_job("playlist", url, metadata)
        return job_id

    def get_job_status(self, job_id):
        """Get status of background job"""
        jobs = self.job_manager.get_all_jobs()
        return jobs.get(job_id)

    def get_all_jobs(self):
        """Get all jobs for status display"""
        return self.job_manager.get_all_jobs()

    def search_youtube(self, query):
        """Search YouTube using yt-dlp"""
        try:
            cmd = [
                "docker",
                "exec",
                "ytdl-sub",
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end",
                "10",
                f"ytsearch10:{query}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                results = []

                for line in lines:
                    try:
                        if line.strip():
                            item = json.loads(line)
                            # Fix duration handling
                            duration = item.get("duration", 0)
                            if duration is None:
                                duration = 0
                            duration = int(duration) if duration else 0

                            results.append(
                                {
                                    "title": item.get("title", "Unknown"),
                                    "uploader": item.get("uploader", "Unknown"),
                                    "duration": duration,
                                    "url": f"https://youtube.com/watch?v={item.get('id', '')}",
                                }
                            )
                    except:
                        continue

                return results

        except Exception as e:
            st.error(f"Search failed: {str(e)}")

        return []


def main():
    st.title("🎵 Lucky's Music Discovery Hub")
    st.markdown("**Your Personal YouTube Music Automation Center**")

    # Initialize downloader
    downloader = MusicDownloader()

    # Sidebar for settings and Spotify integration
    with st.sidebar:
        st.header("🔧 Settings & Integration")

        # Quick stats
        st.subheader("📊 Library Stats")
        try:
            music_count_cmd = [
                "find",
                "/music",
                "-name",
                "*.mp3",
                "-o",
                "-name",
                "*.m4a",
                "-o",
                "-name",
                "*.flac",
            ]
            music_files = subprocess.run(
                music_count_cmd, capture_output=True, text=True
            )
            file_count = len([f for f in music_files.stdout.split("\n") if f.strip()])
            st.metric("Total Tracks", file_count)
        except:
            st.metric("Total Tracks", "N/A")

        st.markdown("---")

        # Spotify Integration
        st.subheader("🎵 Spotify Integration")
        with st.expander("Configure Spotify API"):
            st.markdown("**Setup Instructions:**")
            st.markdown(
                "1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)"
            )
            st.markdown("2. Create a new app")
            st.markdown("3. Copy Client ID and Client Secret")

            spotify_client_id = st.text_input("Spotify Client ID", type="password")
            spotify_client_secret = st.text_input(
                "Spotify Client Secret", type="password"
            )

            if st.button("🔗 Connect Spotify"):
                if spotify_client_id and spotify_client_secret:
                    downloader.spotify.set_credentials(
                        spotify_client_id, spotify_client_secret
                    )
                    if downloader.spotify.access_token:
                        st.success("✅ Spotify connected successfully!")
                    else:
                        st.error("❌ Failed to connect to Spotify")

        # Job Status
        st.subheader("🔄 Download Jobs")
        jobs = downloader.get_all_jobs()
        active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "running"]]
        completed_jobs = [j for j in jobs.values() if j["status"] == "completed"]
        failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]

        st.metric("Active Downloads", len(active_jobs))
        st.metric("Completed Today", len(completed_jobs))
        st.metric("Failed", len(failed_jobs))

        if st.button("🔄 Refresh Status"):
            st.rerun()

    # Main content area
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "🎵 Quick Download",
            "📋 Playlist Manager",
            "🔍 Discovery",
            "🎵 Spotify",
            "📊 Download Status",
        ]
    )

    with tab1:
        st.header("🎵 Quick Song Download")

        col1, col2 = st.columns([2, 1])

        with col1:
            url = st.text_input(
                "🔗 YouTube/YouTube Music URL:",
                placeholder="https://music.youtube.com/watch?v=dQw4w9WgXcQ",
                help="Paste any YouTube or YouTube Music URL here",
            )

            # URL validation
            if url and not downloader.validate_url(url):
                st.error(
                    "❌ Invalid URL format. Please use YouTube or YouTube Music URLs."
                )

            # Optional metadata
            col_artist, col_album = st.columns(2)
            with col_artist:
                artist_override = st.text_input(
                    "🎤 Artist (optional)", placeholder="Override artist name"
                )
            with col_album:
                album_override = st.text_input(
                    "💿 Album (optional)", placeholder="Override album name"
                )

        with col2:
            st.markdown("**🎯 Quick Actions:**")

            # Preview button
            if st.button("👁️ Preview Info", disabled=not url):
                if url:
                    with st.spinner("Fetching video info..."):
                        info = downloader.extract_video_info(url)
                        if info:
                            duration_mins = (
                                info["duration"] // 60 if info["duration"] else 0
                            )
                            duration_secs = (
                                info["duration"] % 60 if info["duration"] else 0
                            )
                            st.markdown(
                                f"""
                            <div class="info-box">
                            <strong>Title:</strong> {info['title']}<br>
                            <strong>Artist:</strong> {info['uploader']}<br>
                            <strong>Duration:</strong> {duration_mins}:{duration_secs:02d}<br>
                            <strong>Views:</strong> {info['view_count']:,}
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )

        # Download section
        st.markdown("---")

        col_download, col_status = st.columns([1, 2])

        with col_download:
            if st.button(
                "📥 Download Song (Background)", type="primary", disabled=not url
            ):
                if url:
                    job_id = downloader.download_single_song_background(
                        url, artist_override, album_override
                    )
                    st.success(f"✅ Download queued! Job ID: {job_id}")
                    st.info(
                        "💡 Download will continue in background. Check 'Download Status' tab for progress."
                    )

        with col_status:
            st.markdown(
                """
            **💡 Background Downloads:**
            - Downloads run in background
            - No need to keep page open
            - Check status in sidebar or Status tab
            - Files appear in Navidrome automatically
            """
            )

    with tab2:
        st.header("📋 Playlist & Album Manager")

        playlist_url = st.text_input(
            "🔗 Playlist/Album URL:",
            placeholder="https://music.youtube.com/playlist?list=...",
            help="YouTube Music playlists, albums, or YouTube playlists",
        )

        playlist_name = st.text_input(
            "📁 Folder Name (optional):",
            placeholder="e.g., 'Chill Vibes', 'Workout Mix'",
            help="Custom folder name for organization",
        )

        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button(
                "📥 Download Playlist (Background)",
                type="primary",
                disabled=not playlist_url,
            ):
                if playlist_url:
                    job_id = downloader.download_playlist_background(
                        playlist_url, playlist_name
                    )
                    st.success(f"✅ Playlist download queued! Job ID: {job_id}")
                    st.info(
                        "💡 Playlist download will continue in background. This may take 10-60 minutes depending on playlist size."
                    )

        with col2:
            if st.button("👁️ Preview Playlist", disabled=not playlist_url):
                if playlist_url:
                    with st.spinner("Fetching playlist info..."):
                        try:
                            # Convert YouTube Music URL if needed
                            preview_url = playlist_url
                            if (
                                "music.youtube.com" in playlist_url
                                and "playlist?list=" in playlist_url
                            ):
                                playlist_id = playlist_url.split("playlist?list=")[
                                    1
                                ].split("&")[0]
                                preview_url = (
                                    f"https://youtube.com/playlist?list={playlist_id}"
                                )

                            cmd = [
                                "docker",
                                "exec",
                                "ytdl-sub",
                                "yt-dlp",
                                "--flat-playlist",
                                "--dump-json",
                                "--playlist-end",
                                "5",
                                preview_url,
                            ]
                            result = subprocess.run(
                                cmd, capture_output=True, text=True, timeout=30
                            )
                            if result.returncode == 0:
                                lines = result.stdout.strip().split("\n")
                                tracks = []
                                for line in lines[:5]:
                                    try:
                                        if line.strip():
                                            track_info = json.loads(line)
                                            duration = (
                                                track_info.get("duration", 0) or 0
                                            )
                                            duration = int(duration)
                                            tracks.append(
                                                {
                                                    "Title": track_info.get(
                                                        "title", "Unknown"
                                                    ),
                                                    "Duration": f"{duration//60}:{duration%60:02d}",
                                                }
                                            )
                                    except:
                                        continue

                                if tracks:
                                    st.markdown("**Preview (first 5 tracks):**")
                                    df = pd.DataFrame(tracks)
                                    st.dataframe(df, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error previewing playlist: {str(e)}")

    with tab3:
        st.header("🔍 Music Discovery")

        # Search functionality
        search_query = st.text_input(
            "🔎 Search YouTube Music:", placeholder="Enter artist, song, or album name"
        )

        if st.button("🔍 Search", disabled=not search_query):
            if search_query:
                with st.spinner("Searching YouTube Music..."):
                    results = downloader.search_youtube(search_query)

                    if results:
                        st.markdown("**Search Results:**")
                        for i, result in enumerate(results):
                            col1, col2, col3 = st.columns([3, 1, 1])

                            with col1:
                                duration_str = (
                                    f"{result['duration']//60}:{result['duration']%60:02d}"
                                    if result["duration"]
                                    else "N/A"
                                )
                                st.markdown(
                                    f"""
                                **{result['title']}**  
                                By: {result['uploader']} | Duration: {duration_str}
                                """
                                )

                            with col2:
                                if st.button(
                                    f"📥",
                                    key=f"download_{i}",
                                    help="Download this song",
                                ):
                                    job_id = downloader.download_single_song_background(
                                        result["url"]
                                    )
                                    st.success(f"✅ Queued! Job: {job_id}")

                            with col3:
                                if st.button(f"📋", key=f"copy_{i}", help="Copy URL"):
                                    st.code(result["url"])

                            st.markdown("---")
                    else:
                        st.warning("No results found. Try different search terms.")

        # Quick discovery
        st.markdown("---")
        st.subheader("🔥 Quick Discovery")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🎵 Music Genres:**")
            if st.button("🎸 Rock Hits", key="rock_btn"):
                # Trigger search directly
                search_results = downloader.search_youtube("rock hits 2024")
                if search_results:
                    st.session_state.discovery_results = search_results
                    st.session_state.discovery_query = "rock hits 2024"
                    st.rerun()

            if st.button("🎤 Pop Music", key="pop_btn"):
                search_results = downloader.search_youtube("pop music hits")
                if search_results:
                    st.session_state.discovery_results = search_results
                    st.session_state.discovery_query = "pop music hits"
                    st.rerun()

        with col2:
            st.markdown("**🌍 Regional Music:**")
            if st.button("🇮🇳 Bollywood", key="bollywood_btn"):
                search_results = downloader.search_youtube("bollywood hits 2024")
                if search_results:
                    st.session_state.discovery_results = search_results
                    st.session_state.discovery_query = "bollywood hits 2024"
                    st.rerun()

            if st.button("🇰🇷 K-Pop", key="kpop_btn"):
                search_results = downloader.search_youtube("kpop hits 2024")
                if search_results:
                    st.session_state.discovery_results = search_results
                    st.session_state.discovery_query = "kpop hits 2024"
                    st.rerun()

        with col3:
            st.markdown("**📅 Time Periods:**")
            if st.button("🆕 2024 Hits", key="2024_btn"):
                search_results = downloader.search_youtube("best songs 2024")
                if search_results:
                    st.session_state.discovery_results = search_results
                    st.session_state.discovery_query = "best songs 2024"
                    st.rerun()

            if st.button("📻 90s Classics", key="90s_btn"):
                search_results = downloader.search_youtube("90s hits classics")
                if search_results:
                    st.session_state.discovery_results = search_results
                    st.session_state.discovery_query = "90s hits classics"
                    st.rerun()

        # Display discovery results
        if (
            hasattr(st.session_state, "discovery_results")
            and st.session_state.discovery_results
        ):
            st.markdown(f"**🎵 {st.session_state.discovery_query.title()} Results:**")
            for i, result in enumerate(st.session_state.discovery_results):
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    duration_str = (
                        f"{result['duration']//60}:{result['duration']%60:02d}"
                        if result["duration"]
                        else "N/A"
                    )
                    st.markdown(
                        f"""
                    **{result['title']}**  
                    By: {result['uploader']} | Duration: {duration_str}
                    """
                    )

                with col2:
                    if st.button(
                        f"📥", key=f"discovery_download_{i}", help="Download this song"
                    ):
                        job_id = downloader.download_single_song_background(
                            result["url"]
                        )
                        st.success(f"✅ Queued! Job: {job_id}")

                with col3:
                    if st.button(f"📋", key=f"discovery_copy_{i}", help="Copy URL"):
                        st.code(result["url"])

                st.markdown("---")

    with tab4:
        st.header("🎵 Spotify Integration")

        if not downloader.spotify.access_token:
            st.warning(
                "⚠️ Please configure Spotify API credentials in the sidebar first."
            )
            return

        # Spotify playlist URL input
        spotify_url = st.text_input(
            "🎵 Spotify Playlist URL:",
            placeholder="https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd",
            help="Paste a Spotify playlist URL to import songs",
        )

        if st.button("🔍 Import from Spotify", disabled=not spotify_url):
            if spotify_url:
                with st.spinner("Fetching Spotify playlist..."):
                    tracks = downloader.spotify.get_playlist_tracks(spotify_url)

                    if tracks:
                        st.success(f"✅ Found {len(tracks)} tracks in playlist!")

                        # Display tracks with download options
                        st.markdown("**Playlist Tracks:**")

                        # Bulk download option
                        if st.button(
                            f"📥 Download All {len(tracks)} Songs", type="primary"
                        ):
                            for track in tracks:
                                # Search for each track on YouTube and queue download
                                search_results = downloader.search_youtube(
                                    track["search_query"]
                                )
                                if search_results:
                                    # Download first (best) result
                                    job_id = downloader.download_single_song_background(
                                        search_results[0]["url"],
                                        track["artists"],
                                        track["album"],
                                    )
                            st.success(f"✅ Queued {len(tracks)} songs for download!")

                        # Individual track display
                        for i, track in enumerate(tracks[:20]):  # Show first 20
                            col1, col2, col3 = st.columns([3, 1, 1])

                            with col1:
                                st.markdown(
                                    f"""
                                **{track['name']}**  
                                By: {track['artists']} | Album: {track['album']}
                                """
                                )

                            with col2:
                                if st.button(
                                    f"🔍",
                                    key=f"spotify_search_{i}",
                                    help="Search on YouTube",
                                ):
                                    search_results = downloader.search_youtube(
                                        track["search_query"]
                                    )
                                    if search_results:
                                        st.session_state[f"spotify_results_{i}"] = (
                                            search_results[0]
                                        )
                                        st.rerun()

                            with col3:
                                if hasattr(st.session_state, f"spotify_results_{i}"):
                                    youtube_track = st.session_state[
                                        f"spotify_results_{i}"
                                    ]
                                    if st.button(
                                        f"📥",
                                        key=f"spotify_download_{i}",
                                        help="Download from YouTube",
                                    ):
                                        job_id = (
                                            downloader.download_single_song_background(
                                                youtube_track["url"],
                                                track["artists"],
                                                track["album"],
                                            )
                                        )
                                        st.success(f"✅ Queued!")

                            st.markdown("---")

                        if len(tracks) > 20:
                            st.info(
                                f"💡 Showing first 20 tracks. Total: {len(tracks)} tracks."
                            )
                    else:
                        st.error(
                            "❌ Could not fetch playlist. Check URL and API credentials."
                        )

        # Spotify search
        st.markdown("---")
        st.subheader("🔍 Spotify Artist/Album Search")

        spotify_search = st.text_input(
            "Search Spotify:", placeholder="Enter artist or album name"
        )

        if st.button("🔍 Search Spotify") and spotify_search:
            st.info(
                "💡 Direct Spotify search not implemented yet. Use playlist import above."
            )

    with tab5:
        st.header("📊 Download Status & Activity")

        # Refresh button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Refresh Status"):
                st.rerun()

        jobs = downloader.get_all_jobs()

        if not jobs:
            st.info("No download jobs yet. Start downloading some music!")
            return

        # Active downloads
        active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "running"]]
        if active_jobs:
            st.subheader("🔄 Active Downloads")
            for job in active_jobs:
                status_class = "job-status-running"
                status_icon = "🔄" if job["status"] == "running" else "⏳"

                st.markdown(
                    f"""
                <div class="{status_class}">
                <strong>{status_icon} {job['type'].replace('_', ' ').title()}</strong><br>
                URL: <code>{job['url'][:50]}...</code><br>
                Status: {job['message']}<br>
                Progress: {job.get('progress', 0)}%<br>
                Job ID: {job['id']}
                </div>
                """,
                    unsafe_allow_html=True,
                )

        # Recent completed downloads
        completed_jobs = sorted(
            [j for j in jobs.values() if j["status"] == "completed"],
            key=lambda x: x.get("updated", x["created"]),
            reverse=True,
        )[:10]

        if completed_jobs:
            st.subheader("✅ Recent Completed Downloads")
            for job in completed_jobs:
                completed_time = datetime.fromisoformat(
                    job.get("updated", job["created"])
                ).strftime("%Y-%m-%d %H:%M")
                st.markdown(
                    f"""
                <div class="job-status-completed">
                <strong>✅ {job['type'].replace('_', ' ').title()}</strong><br>
                URL: <code>{job['url'][:50]}...</code><br>
                Completed: {completed_time}<br>
                Job ID: {job['id']}
                </div>
                """,
                    unsafe_allow_html=True,
                )

        # Failed downloads
        failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]
        if failed_jobs:
            st.subheader("❌ Failed Downloads")
            for job in failed_jobs[-5:]:  # Show last 5 failures
                st.markdown(
                    f"""
                <div class="job-status-failed">
                <strong>❌ {job['type'].replace('_', ' ').title()}</strong><br>
                URL: <code>{job['url'][:50]}...</code><br>
                Error: {job['message']}<br>
                Job ID: {job['id']}
                </div>
                """,
                    unsafe_allow_html=True,
                )

        # Statistics
        st.markdown("---")
        st.subheader("📈 Download Statistics")

        col1, col2, col3, col4 = st.columns(4)

        total_jobs = len(jobs)
        completed_count = len([j for j in jobs.values() if j["status"] == "completed"])
        failed_count = len([j for j in jobs.values() if j["status"] == "failed"])
        success_rate = (completed_count / total_jobs * 100) if total_jobs > 0 else 0

        with col1:
            st.metric("Total Downloads", total_jobs)
        with col2:
            st.metric("Completed", completed_count)
        with col3:
            st.metric("Failed", failed_count)
        with col4:
            st.metric("Success Rate", f"{success_rate:.1f}%")

    # Footer
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; color: #666;">
    🎵 Lucky's Music Empire | Background Downloads Active | 
    <a href="https://music.luckyverma.com" target="_blank">🎧 Open Music Player</a>
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
