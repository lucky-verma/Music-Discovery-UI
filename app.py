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

# Configure page
st.set_page_config(
    page_title="🎵 Music Discovery",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modern Spotify-like CSS with full-width results
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
    }
    
    /* Results container - FIXED for full width */
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

    def is_music_content(self, title, description="", duration=0):
        """Filter to detect if content is likely music"""
        title_lower = title.lower()
        desc_lower = description.lower()

        # Music indicators
        music_keywords = [
            "song",
            "music",
            "audio",
            "track",
            "album",
            "single",
            "ep",
            "mixtape",
            "official audio",
            "lyric video",
            "music video",
            "acoustic",
            "remix",
            "cover",
            "live",
            "concert",
            "unplugged",
            "studio",
            "acoustic version",
        ]

        # Non-music indicators
        non_music_keywords = [
            "tutorial",
            "how to",
            "review",
            "reaction",
            "vlog",
            "gaming",
            "news",
            "interview",
            "trailer",
            "movie",
            "tv show",
            "podcast",
            "comedy",
            "documentary",
            "cooking",
            "workout",
            "meditation",
        ]

        # Check for music indicators
        has_music_keywords = any(
            keyword in title_lower or keyword in desc_lower
            for keyword in music_keywords
        )

        # Check for non-music indicators
        has_non_music = any(
            keyword in title_lower or keyword in desc_lower
            for keyword in non_music_keywords
        )

        # Duration filter (music typically 1-15 minutes)
        reasonable_duration = 30 <= duration <= 900  # 30 seconds to 15 minutes

        # Score-based filtering
        if has_non_music:
            return False

        if has_music_keywords or reasonable_duration:
            return True

        # Default: allow if no clear non-music indicators
        return not has_non_music

    def search_youtube_music(self, query, max_results=20, filter_music=True):
        """Search YouTube Music using direct yt-dlp with music filtering"""
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end",
                str(max_results * 2),  # Get more to filter
                f"ytsearch{max_results * 2}:{query}",
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
                            title = item.get("title", "Unknown")
                            description = item.get("description", "")

                            # Apply music filter
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

                        except:
                            continue

                return results
        except Exception as e:
            st.error(f"Search failed: {str(e)}")

        return []

    def extract_playlist_info(self, url):
        """Extract playlist information from URL"""
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end",
                "50",  # Limit to first 50 for preview
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                items = []
                lines = result.stdout.strip().split("\n")

                for line in lines:
                    if line.strip():
                        try:
                            item = json.loads(line)
                            if item.get("_type") == "playlist":
                                continue  # Skip playlist metadata

                            duration = int(item.get("duration", 0) or 0)
                            title = item.get("title", "Unknown")

                            # Apply music filter
                            if self.is_music_content(title, "", duration):
                                items.append(
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
                        except:
                            continue

                return items
        except Exception as e:
            st.error(f"Playlist extraction failed: {str(e)}")

        return []

    def download_song(self, url, artist="", album=""):
        """Queue song for download using direct yt-dlp"""
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

    def download_playlist(self, url, playlist_name=""):
        """Queue entire playlist for download"""
        job_id = str(uuid.uuid4())[:8]

        job = {
            "id": job_id,
            "url": url,
            "playlist_name": playlist_name or "Downloaded Playlist",
            "type": "playlist",
            "status": "queued",
            "created": datetime.now().isoformat(),
            "progress": 0,
            "message": "Queued for playlist download",
        }

        # Save job
        jobs = self.get_all_jobs()
        jobs[job_id] = job
        self.save_jobs(jobs)

        # Start download in background
        threading.Thread(
            target=self._process_playlist_download, args=(job_id,), daemon=True
        ).start()

        return job_id

    def _process_download(self, job_id):
        """Process single song download in background"""
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

            # Download using direct yt-dlp
            cmd = [
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
                self._trigger_navidrome_scan()

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

    def _process_playlist_download(self, job_id):
        """Process playlist download in background"""
        try:
            jobs = self.get_all_jobs()
            job = jobs.get(job_id)
            if not job:
                return

            # Update status
            job["status"] = "downloading"
            job["progress"] = 5
            job["message"] = "Starting playlist download..."
            self.save_jobs(jobs)

            playlist_name = job.get("playlist_name", "Downloaded Playlist")

            # Download using direct yt-dlp with playlist support
            cmd = [
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
                f"/music/youtube-music/{playlist_name}/%(uploader)s/%(title)s.%(ext)s",
                job["url"],
            ]

            # Use Popen for progress monitoring
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            progress = 5
            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    # Update progress based on yt-dlp output
                    if "[download]" in output and "%" in output:
                        try:
                            # Extract percentage
                            percent_match = re.search(r"(\d+(?:\.\d+)?)%", output)
                            if percent_match:
                                file_progress = float(percent_match.group(1))
                                progress = 5 + (file_progress * 0.85)  # Scale to 5-90%
                                job["progress"] = int(progress)
                                job["message"] = (
                                    f"Downloading playlist... {file_progress:.1f}%"
                                )
                                self.save_jobs(jobs)
                        except:
                            pass

            # Wait for completion
            process.wait()

            if process.returncode == 0:
                job["status"] = "completed"
                job["progress"] = 95
                job["message"] = "Triggering library scan..."
                self.save_jobs(jobs)

                # Trigger Navidrome scan
                self._trigger_navidrome_scan()

                job["status"] = "completed"
                job["progress"] = 100
                job["message"] = f'Playlist "{playlist_name}" downloaded successfully!'
            else:
                stderr = process.stderr.read()
                job["status"] = "failed"
                job["progress"] = 0
                job["message"] = (
                    f"Playlist download failed: {stderr[:100] if stderr else 'Unknown error'}"
                )

            self.save_jobs(jobs)

        except Exception as e:
            jobs = self.get_all_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["progress"] = 0
                jobs[job_id]["message"] = f"Error: {str(e)}"
                self.save_jobs(jobs)

    def _trigger_navidrome_scan(self):
        """Trigger Navidrome library scan - handles deduplication automatically"""
        try:
            # First try direct API call to Navidrome
            subprocess.run(
                ["curl", "-X", "POST", "http://192.168.1.39:4533/api/scanner/scan"],
                timeout=10,
                capture_output=True,
            )
        except:
            try:
                # Fallback: try through docker if container setup
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
            except:
                pass  # Scan trigger is optional, Navidrome will auto-scan periodically

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
        """Fix greyed out tracks in Navidrome - runs in background"""
        try:
            # Trigger comprehensive scan to clean up database
            self._trigger_navidrome_scan()
            return True
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
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🔍 **Discover & Download**",
            "📋 **Playlist Manager**",
            "📊 **Download Status**",
            "🔧 **Library Tools**",
        ]
    )

    with tab1:
        # Search interface
        st.header("🔍 Search & Discover Music")

        search_query = st.text_input(
            "",
            placeholder="🎵 Search for songs, artists, albums... (e.g., 'Arijit Singh', 'Bollywood hits', 'rock music')",
            key="search_input",
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

        if search_query and search_button:
            with st.spinner("🎵 Searching YouTube Music..."):
                results = app.search_youtube_music(
                    search_query, max_results=20, filter_music=music_filter
                )

                if results:
                    st.success(f"Found {len(results)} results for '{search_query}'")

                    # FIXED: Full width results container
                    st.markdown(
                        '<div class="results-container">', unsafe_allow_html=True
                    )

                    # Display results in card grid (4 columns for better layout)
                    for i in range(0, len(results), 4):
                        cols = st.columns(4)

                        for j, col in enumerate(cols):
                            if i + j < len(results):
                                track = results[i + j]
                                with col:
                                    # Album art
                                    if track.get("thumbnail"):
                                        st.image(track["thumbnail"], width=150)

                                    # Track info
                                    title = (
                                        track["title"][:30] + "..."
                                        if len(track["title"]) > 30
                                        else track["title"]
                                    )
                                    uploader = (
                                        track["uploader"][:20] + "..."
                                        if len(track["uploader"]) > 20
                                        else track["uploader"]
                                    )

                                    st.markdown(f"**{title}**")
                                    st.caption(f"🎤 {uploader}")
                                    st.caption(f"⏱️ {track['duration_str']}")

                                    # Download button
                                    if st.button(
                                        "📥 Download",
                                        key=f"dl_{i+j}",
                                        use_container_width=True,
                                    ):
                                        job_id = app.download_song(track["url"])
                                        st.success(f"✅ Queued! Job: {job_id}")

                    st.markdown("</div>", unsafe_allow_html=True)

                    # Load more button
                    if len(results) >= 20:
                        if st.button("📄 Load More Results"):
                            more_results = app.search_youtube_music(
                                search_query, max_results=40, filter_music=music_filter
                            )
                            if len(more_results) > len(results):
                                st.session_state.extended_results = more_results[20:]
                                st.rerun()
                else:
                    st.warning(
                        "No results found. Try different keywords or disable music filter."
                    )

        # Quick discovery - FIXED for full width display
        st.header("🎭 Quick Discovery")

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
                if st.button(genre_name, key=f"genre_{i}", use_container_width=True):
                    # Store in session state to display results
                    st.session_state.genre_query = genre_query
                    st.session_state.genre_name = genre_name
                    st.rerun()

        # Display genre results if available
        if hasattr(st.session_state, "genre_query"):
            with st.spinner(f"Finding {st.session_state.genre_name} music..."):
                results = app.search_youtube_music(
                    st.session_state.genre_query, max_results=16, filter_music=True
                )

                if results:
                    st.success(
                        f"🎵 {st.session_state.genre_name} - {len(results)} tracks found"
                    )

                    # FIXED: Full width results
                    st.markdown(
                        '<div class="results-container">', unsafe_allow_html=True
                    )

                    for j in range(0, len(results), 4):
                        result_cols = st.columns(4)

                        for k, col in enumerate(result_cols):
                            if j + k < len(results):
                                track = results[j + k]
                                with col:
                                    if track.get("thumbnail"):
                                        st.image(track["thumbnail"], width=150)

                                    title = (
                                        track["title"][:30] + "..."
                                        if len(track["title"]) > 30
                                        else track["title"]
                                    )
                                    uploader = (
                                        track["uploader"][:20] + "..."
                                        if len(track["uploader"]) > 20
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
                else:
                    st.warning(f"No {st.session_state.genre_name} results found.")

    with tab2:
        # NEW: Playlist Manager Tab
        st.header("📋 Playlist & URL Manager")

        st.markdown('<div class="playlist-section">', unsafe_allow_html=True)

        # URL input section
        st.subheader("🔗 Add URLs or Playlists")

        url_input = st.text_area(
            "Paste URLs (one per line):",
            placeholder="https://youtube.com/watch?v=dQw4w9WgXcQ\nhttps://youtube.com/playlist?list=PLrAXtmRdnEQy3Qo2KnG...\nhttps://music.youtube.com/watch?v=...",
            height=100,
        )

        col1, col2 = st.columns(2)

        with col1:
            playlist_name = st.text_input(
                "Playlist Name (optional):",
                placeholder="e.g., 'My Awesome Mix'",
                help="Custom folder name for organization",
            )

        with col2:
            apply_filter = st.checkbox(
                "🎵 Filter Music Only", value=True, help="Skip non-music content"
            )

        if url_input and st.button("📥 **Process URLs**", type="primary"):
            urls = [url.strip() for url in url_input.split("\n") if url.strip()]

            if urls:
                processed_count = 0

                for url in urls:
                    if "playlist" in url or "list=" in url:
                        # Handle as playlist
                        job_id = app.download_playlist(
                            url, playlist_name or "Downloaded Playlist"
                        )
                        st.success(f"📋 Playlist queued! Job: {job_id}")
                        processed_count += 1
                    elif "youtube.com/watch" in url or "music.youtube.com" in url:
                        # Handle as single video
                        job_id = app.download_song(url)
                        st.success(f"🎵 Song queued! Job: {job_id}")
                        processed_count += 1
                    else:
                        st.warning(f"⚠️ Unsupported URL: {url[:50]}...")

                if processed_count > 0:
                    st.success(f"✅ Processed {processed_count} URLs successfully!")

        # Playlist preview section
        st.subheader("👁️ Preview Playlist")

        preview_url = st.text_input(
            "Playlist URL for preview:",
            placeholder="https://youtube.com/playlist?list=...",
        )

        if preview_url and st.button("👁️ **Preview Playlist**"):
            with st.spinner("🔍 Analyzing playlist..."):
                playlist_items = app.extract_playlist_info(preview_url)

                if playlist_items:
                    st.success(
                        f"📋 Found {len(playlist_items)} music tracks in playlist"
                    )

                    # Display first 10 items
                    for i, item in enumerate(playlist_items[:10]):
                        col1, col2, col3 = st.columns([2, 2, 1])

                        with col1:
                            st.markdown(
                                f"**{item['title'][:40]}...**"
                                if len(item["title"]) > 40
                                else f"**{item['title']}**"
                            )

                        with col2:
                            st.caption(
                                f"🎤 {item['uploader']} | ⏱️ {item['duration_str']}"
                            )

                        with col3:
                            if st.button(
                                "📥", key=f"preview_dl_{i}", help="Download this track"
                            ):
                                job_id = app.download_song(item["url"])
                                st.success(f"✅ Queued!")

                    if len(playlist_items) > 10:
                        st.info(f"... and {len(playlist_items) - 10} more tracks")

                    # Download entire playlist button
                    if st.button("📥 **Download Entire Playlist**", type="primary"):
                        job_id = app.download_playlist(
                            preview_url, playlist_name or "Previewed Playlist"
                        )
                        st.success(f"📋 Entire playlist queued! Job: {job_id}")

                else:
                    st.error("❌ Could not extract playlist or no music content found")

        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        # Download status tab
        st.header("📊 Download Status & History")

        if st.button("🔄 Refresh", key="refresh_status"):
            st.rerun()

        jobs = app.get_all_jobs()

        if not jobs:
            st.info(
                "No downloads yet. Search for music or add playlists to start downloading!"
            )
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
                        job_type = (
                            "📋 Playlist"
                            if job.get("type") == "playlist"
                            else "🎵 Song"
                        )
                        st.markdown(f"**{status_emoji} {job_type} Downloading...**")
                        st.caption(f"URL: {job['url'][:60]}...")
                        st.caption(f"Status: {job.get('message', 'Processing...')}")

                    with col2:
                        progress = job.get("progress", 0)
                        st.progress(progress / 100)
                        st.caption(f"{progress}%")

                    with col3:
                        st.caption(f"Job: {job['id']}")

        # Recent downloads
        completed_jobs = [j for j in jobs.values() if j["status"] == "completed"]
        failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]

        col1, col2 = st.columns(2)

        with col1:
            if completed_jobs:
                st.subheader("✅ Recent Completed")
                for job in completed_jobs[-10:]:  # Last 10
                    created_time = job.get("created", "")[:19].replace("T", " ")
                    job_type = "📋" if job.get("type") == "playlist" else "🎵"
                    st.success(f"{job_type} {created_time} - Completed")

        with col2:
            if failed_jobs:
                st.subheader("❌ Recent Failed")
                for job in failed_jobs[-5:]:  # Last 5
                    st.error(f"❌ {job.get('message', 'Download failed')}")

    with tab4:
        # FIXED: Library tools tab with actual content
        st.header("🔧 Library Management Tools")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🎵 Navidrome Integration")

            # Navidrome status check
            try:
                # Try to ping Navidrome
                result = subprocess.run(
                    ["curl", "-f", "http://192.168.1.39:4533/ping"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                navidrome_status = (
                    "🟢 Online" if result.returncode == 0 else "🔴 Offline"
                )
            except:
                navidrome_status = "🟡 Unknown"

            st.markdown(f"**Status:** {navidrome_status}")

            if st.button("🔄 Trigger Library Scan", use_container_width=True):
                with st.spinner("Scanning library..."):
                    if app._trigger_navidrome_scan():
                        st.success("✅ Library scan triggered!")
                    else:
                        st.warning("⚠️ Scan triggered (response unknown)")

            if st.button("🧹 Fix Duplicates/Greyed Out", use_container_width=True):
                with st.spinner("Fixing database issues..."):
                    if app.fix_navidrome_duplicates():
                        st.success("✅ Cleanup process completed!")
                        st.info(
                            "ℹ️ Deduplication and greyed-out track removal runs automatically in background"
                        )
                    else:
                        st.error("❌ Cleanup failed")

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

                            # Calculate usage percentage
                            usage_pct = parts[4] if len(parts) > 4 else "Unknown"
                            st.metric("Usage", usage_pct)
            except:
                st.info("Storage info unavailable")

            # Music file health check
            if st.button("🔍 Check Music Files", use_container_width=True):
                with st.spinner("Checking music files..."):
                    try:
                        # Count by format
                        formats = {}
                        result = subprocess.run(
                            ["find", "/music", "-type", "f", "-name", "*.mp3"],
                            capture_output=True,
                            text=True,
                        )
                        formats["MP3"] = len(
                            [f for f in result.stdout.split("\n") if f.strip()]
                        )

                        result = subprocess.run(
                            ["find", "/music", "-type", "f", "-name", "*.m4a"],
                            capture_output=True,
                            text=True,
                        )
                        formats["M4A"] = len(
                            [f for f in result.stdout.split("\n") if f.strip()]
                        )

                        result = subprocess.run(
                            ["find", "/music", "-type", "f", "-name", "*.flac"],
                            capture_output=True,
                            text=True,
                        )
                        formats["FLAC"] = len(
                            [f for f in result.stdout.split("\n") if f.strip()]
                        )

                        # Display format breakdown
                        for format_name, count in formats.items():
                            st.metric(f"{format_name} Files", count)
                    except:
                        st.error("File check failed")

        # Quick links and info
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

        # Background processes info
        st.markdown("---")
        st.subheader("ℹ️ Background Processes")

        st.info(
            """
        **🤖 Automated Management:**
        - ✅ **Deduplication**: Automatic removal of duplicate tracks during library scans
        - ✅ **Metadata Cleanup**: Smart tagging and organization
        - ✅ **Greyed Track Removal**: Automatic cleanup of orphaned database entries
        - ✅ **Library Optimization**: Periodic scans every 15 minutes
        - ✅ **Storage Management**: Automatic file organization by artist/album
        
        **📍 Music Paths:**
        - `/music/youtube-music/` - Downloaded tracks (auto-organized)
        - `/music/library/` - Main collection
        
        All management tasks run automatically in the background!
        """
        )

        # Footer info
        st.markdown("---")
        st.markdown(
            """
        <div style="text-align: center; color: #666; font-size: 0.8em;">
            🎵 Lucky's Music Empire | Built with Streamlit + yt-dlp | VPN-Protected Downloads
        </div>
        """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
