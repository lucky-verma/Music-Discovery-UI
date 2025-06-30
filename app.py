# File: app.py
import streamlit as st
import subprocess
import os
import json
import requests
import re
from datetime import datetime
import pandas as pd
import time

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
</style>
""",
    unsafe_allow_html=True,
)


class MusicDownloader:
    def __init__(self):
        self.config_path = "/config"
        self.music_path = "/music/youtube-music"

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
            # Use docker exec to run yt-dlp in the ytdl-sub container
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
                if lines:
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

    def download_single_song(self, url, artist=None, album=None):
        """Download single song using working yt-dlp approach"""
        try:
            # Create organized output path
            output_template = f"{self.music_path}/%(uploader)s/%(title)s.%(ext)s"
            if artist:
                output_template = f"{self.music_path}/{artist}/%(title)s.%(ext)s"

            # Use direct yt-dlp command (simpler and more reliable)
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
                # Trigger Navidrome rescan
                try:
                    subprocess.run(
                        [
                            "curl",
                            "-X",
                            "POST",
                            "http://192.168.1.31:4533/api/scanner/scan",
                        ],
                        timeout=10,
                    )
                except:
                    pass

            return result.returncode == 0, result.stdout, result.stderr

        except Exception as e:
            return False, "", str(e)

    def download_playlist(self, url, playlist_name=None):
        """Download playlist using working ytdl-sub preset approach"""
        try:
            # Use the approach that worked in your tests
            output_dir = f"{self.music_path}/{playlist_name or 'Playlists'}"

            # Working command based on your successful test
            cmd = [
                "docker",
                "exec",
                "ytdl-sub",
                "ytdl-sub",
                "dl",
                "--preset",
                "YouTube Full Albums",
                "--overrides.music_directory",
                output_dir,
                "--overrides.url",
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                # Trigger Navidrome rescan
                try:
                    subprocess.run(
                        [
                            "curl",
                            "-X",
                            "POST",
                            "http://192.168.1.31:4533/api/scanner/scan",
                        ],
                        timeout=10,
                    )
                except:
                    pass

            return result.returncode == 0, result.stdout, result.stderr

        except Exception as e:
            return False, "", str(e)

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
                "10",  # Limit to 10 results
                f"ytsearch10:{query}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                results = []

                for line in lines:
                    try:
                        item = json.loads(line)
                        results.append(
                            {
                                "title": item.get("title", "Unknown"),
                                "uploader": item.get("uploader", "Unknown"),
                                "duration": item.get("duration", 0),
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

    # Sidebar for settings and automation
    with st.sidebar:
        st.header("🔧 Settings & Automation")

        # Quick stats
        st.subheader("📊 Library Stats")
        try:
            music_files = subprocess.run(
                [
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
                ],
                capture_output=True,
                text=True,
            )
            file_count = len([f for f in music_files.stdout.split("\n") if f.strip()])
            st.metric("Total Tracks", file_count)
        except:
            st.metric("Total Tracks", "N/A")

        st.markdown("---")

        # Automation section
        st.subheader("🤖 Automation Setup")

        # YouTube Music Liked Songs
        st.markdown("**YouTube Music Integration:**")
        youtube_liked = st.text_input(
            "Liked Songs Playlist ID", placeholder="LM or your liked songs ID"
        )

        # Spotify playlists
        st.markdown("**Spotify Playlists:**")
        spotify_playlists = st.text_area(
            "Playlist URLs (one per line)",
            placeholder="https://open.spotify.com/playlist/...\nhttps://open.spotify.com/playlist/...",
        )

        # Auto-download frequency
        auto_frequency = st.selectbox(
            "Auto-download frequency",
            ["Manual only", "Every hour", "Every 3 hours", "Every 6 hours", "Daily"],
        )

        if st.button("💾 Save Automation Settings"):
            # Save automation settings to config
            automation_config = {
                "automation": {
                    "youtube_liked": youtube_liked,
                    "spotify_playlists": (
                        spotify_playlists.split("\n") if spotify_playlists else []
                    ),
                    "frequency": auto_frequency,
                }
            }

            try:
                with open("/config/automation_settings.json", "w") as f:
                    json.dump(automation_config, f)
                st.success("✅ Automation settings saved!")
            except Exception as e:
                st.error(f"❌ Error saving settings: {str(e)}")

    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🎵 Quick Download",
            "📋 Playlist Manager",
            "🔍 Discovery",
            "📊 Download History",
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
                            st.markdown(
                                f"""
                            <div class="info-box">
                            <strong>Title:</strong> {info['title']}<br>
                            <strong>Artist:</strong> {info['uploader']}<br>
                            <strong>Duration:</strong> {info['duration']//60}:{info['duration']%60:02d}<br>
                            <strong>Views:</strong> {info['view_count']:,}
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )

        # Download section
        st.markdown("---")

        col_download, col_status = st.columns([1, 2])

        with col_download:
            if st.button("📥 Download Song", type="primary", disabled=not url):
                if url:
                    with st.spinner("⏳ Downloading... This may take 2-5 minutes"):
                        success, stdout, stderr = downloader.download_single_song(
                            url, artist_override, album_override
                        )

                        if success:
                            st.markdown(
                                """
                            <div class="success-box">
                            ✅ <strong>Download completed successfully!</strong><br>
                            The song will appear in Navidrome within 15 minutes.
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )

                            # Log successful download
                            log_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "url": url,
                                "type": "single_song",
                                "status": "success",
                                "artist": artist_override,
                                "album": album_override,
                            }

                            # Save to download history
                            try:
                                history_file = "/config/download_history.json"
                                history = []
                                if os.path.exists(history_file):
                                    with open(history_file, "r") as f:
                                        history = json.load(f)
                                history.append(log_entry)
                                with open(history_file, "w") as f:
                                    json.dump(
                                        history[-100:], f
                                    )  # Keep last 100 entries
                            except:
                                pass
                        else:
                            st.markdown(
                                f"""
                            <div class="error-box">
                            ❌ <strong>Download failed!</strong><br>
                            Error: {stderr[:200]}...
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )

        with col_status:
            # Quick tips
            st.markdown(
                """
            **💡 Tips:**
            - Works with any YouTube or YouTube Music URL
            - Individual songs usually take 2-3 minutes
            - Files automatically organized by artist/album
            - Navidrome scans every 15 minutes
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
                "📥 Download Playlist", type="primary", disabled=not playlist_url
            ):
                if playlist_url:
                    with st.spinner(
                        "⏳ Downloading playlist... This may take 10-30 minutes"
                    ):
                        success, stdout, stderr = downloader.download_playlist(
                            playlist_url, playlist_name
                        )

                        if success:
                            st.success("✅ Playlist download completed successfully!")
                        else:
                            st.error(f"❌ Playlist download failed: {stderr[:200]}...")

        with col2:
            # Playlist preview button
            if st.button("👁️ Preview Playlist", disabled=not playlist_url):
                if playlist_url:
                    with st.spinner("Fetching playlist info..."):
                        # Get playlist info
                        try:
                            cmd = [
                                "yt-dlp",
                                "--flat-playlist",
                                "--dump-json",
                                playlist_url,
                            ]
                            result = subprocess.run(
                                cmd, capture_output=True, text=True, timeout=30
                            )
                            if result.returncode == 0:
                                lines = result.stdout.strip().split("\n")
                                tracks = []
                                for line in lines[:10]:  # Show first 10 tracks
                                    try:
                                        track_info = json.loads(line)
                                        tracks.append(
                                            {
                                                "Title": track_info.get(
                                                    "title", "Unknown"
                                                ),
                                                "Duration": f"{track_info.get('duration', 0)//60}:{track_info.get('duration', 0)%60:02d}",
                                            }
                                        )
                                    except:
                                        continue

                                if tracks:
                                    st.markdown("**Preview (first 10 tracks):**")
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
                    try:
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
                                        f"📥", key=f"download_{i}", help="Download this song"
                                    ):
                                        # Quick download
                                        with st.spinner("Downloading..."):
                                            success, stdout, stderr = (
                                                downloader.download_single_song(result["url"])
                                            )
                                            if success:
                                                st.success("✅ Downloaded!")
                                            else:
                                                st.error(f"❌ Failed: {stderr[:100]}...")

                                with col3:
                                    if st.button(f"📋", key=f"copy_{i}", help="Copy URL"):
                                        st.code(result["url"])

                                st.markdown("---")
                        else:
                            st.warning("No results found. Try different search terms.")

                    except Exception as e:
                        st.error(f"Search failed: {str(e)}")
        # Trending and recommendations
        st.markdown("---")
        st.subheader("🔥 Quick Access")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🎵 Music Genres:**")
            genres = [
                "Pop",
                "Rock",
                "Hip Hop",
                "Electronic",
                "Classical",
                "Jazz",
                "Country",
                "R&B",
            ]
            selected_genre = st.selectbox("Browse by genre:", genres)
            if st.button(f"🔍 Search {selected_genre}"):
                st.query_params.search = f"{selected_genre} music 2024"

        with col2:
            st.markdown("**🌍 Regional Music:**")
            regions = [
                "Bollywood",
                "K-Pop",
                "J-Pop",
                "Latin",
                "Arabic",
                "African",
                "European",
            ]
            selected_region = st.selectbox("Browse by region:", regions)
            if st.button(f"🔍 Search {selected_region}"):
                st.query_params.search = f"{selected_region} music hits"

        with col3:
            st.markdown("**📅 Time Periods:**")
            periods = ["2024", "2023", "2020s", "2010s", "2000s", "90s", "80s", "70s"]
            selected_period = st.selectbox("Browse by era:", periods)
            if st.button(f"🔍 Search {selected_period}"):
                st.query_params.search = f"best songs {selected_period}"

    with tab4:
        st.header("📊 Download History & Stats")

        # Load download history
        try:
            history_file = "/config/download_history.json"
            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history = json.load(f)

                if history:
                    # Recent downloads
                    st.subheader("🕒 Recent Downloads")
                    recent = history[-10:]  # Last 10 downloads

                    for entry in reversed(recent):
                        timestamp = datetime.fromisoformat(entry["timestamp"]).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        status_icon = "✅" if entry["status"] == "success" else "❌"

                        st.markdown(
                            f"""
                        **{status_icon} {timestamp}** - {entry['type']}  
                        URL: `{entry['url'][:50]}...`
                        """
                        )

                    # Stats
                    st.markdown("---")
                    st.subheader("📈 Statistics")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        total_downloads = len(history)
                        st.metric("Total Downloads", total_downloads)

                    with col2:
                        successful = len(
                            [h for h in history if h["status"] == "success"]
                        )
                        success_rate = (
                            (successful / total_downloads * 100)
                            if total_downloads > 0
                            else 0
                        )
                        st.metric("Success Rate", f"{success_rate:.1f}%")

                    with col3:
                        today_downloads = len(
                            [
                                h
                                for h in history
                                if h["timestamp"].startswith(
                                    datetime.now().strftime("%Y-%m-%d")
                                )
                            ]
                        )
                        st.metric("Today's Downloads", today_downloads)
                else:
                    st.info("No download history available yet.")
            else:
                st.info("No download history available yet.")
        except Exception as e:
            st.error(f"Error loading history: {str(e)}")

        # Clear history button
        if st.button("🗑️ Clear History", type="secondary"):
            try:
                if os.path.exists("/config/download_history.json"):
                    os.remove("/config/download_history.json")
                st.success("History cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing history: {str(e)}")

    # Footer
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; color: #666;">
    🎵 Lucky's Music Empire | Powered by ytdl-sub & Navidrome | 
    <a href="https://music.luckyverma.com" target="_blank">🎧 Open Music Player</a>
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
