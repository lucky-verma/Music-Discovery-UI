import streamlit as st
import subprocess
import os
import json
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
        self.music_path = "/music/youtube-music"  # FIXED: Specific subfolder

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
            # FIXED: Use docker exec to run yt-dlp in the ytdl-sub container
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

    def download_single_song(self, url, artist=None, album=None):
        """Download single song using direct yt-dlp"""
        try:
            # Create organized output path
            if artist and album:
                output_template = (
                    f"{self.music_path}/{artist}/{album}/%(title)s.%(ext)s"
                )
            elif artist:
                output_template = f"{self.music_path}/{artist}/%(title)s.%(ext)s"
            else:
                output_template = f"{self.music_path}/%(uploader)s/%(title)s.%(ext)s"

            # FIXED: Use direct yt-dlp command via docker exec
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
                self.trigger_navidrome_scan()

            return result.returncode == 0, result.stdout, result.stderr

        except Exception as e:
            return False, "", str(e)

    def download_playlist(self, url, playlist_name=None):
        """Download playlist using direct yt-dlp"""
        try:
            output_dir = f"{self.music_path}/{playlist_name or 'Playlists'}"

            # FIXED: Use direct yt-dlp for playlist downloads
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

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                self.trigger_navidrome_scan()

            return result.returncode == 0, result.stdout, result.stderr

        except Exception as e:
            return False, "", str(e)

    def trigger_navidrome_scan(self):
        """Trigger Navidrome to scan for new files"""
        try:
            # Try to trigger scan via API
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
            pass  # Scan trigger is optional

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

    # Sidebar for stats and info
    with st.sidebar:
        st.header("🔧 Music Library")

        # Quick stats
        st.subheader("📊 Library Stats")
        try:
            # Count music files
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

        # Quick links
        st.subheader("🎧 Quick Access")
        st.markdown("**Music Player:**")
        st.markdown("[🎵 Open Navidrome](https://music.luckyverma.com)")

        st.markdown("**Download Folders:**")
        st.code("/music/youtube-music/")
        st.code("/music/library/")
        st.code("/music/playlists/")

    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🎵 Quick Download", "📋 Playlist Manager", "🔍 Discovery", "📊 Activity"]
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
            if st.button("👁️ Preview Playlist", disabled=not playlist_url):
                if playlist_url:
                    with st.spinner("Fetching playlist info..."):
                        # Get basic playlist info
                        try:
                            cmd = [
                                "docker",
                                "exec",
                                "ytdl-sub",
                                "yt-dlp",
                                "--flat-playlist",
                                "--dump-json",
                                "--playlist-end",
                                "5",
                                playlist_url,
                            ]
                            result = subprocess.run(
                                cmd, capture_output=True, text=True, timeout=30
                            )
                            if result.returncode == 0:
                                lines = result.stdout.strip().split("\n")
                                tracks = []
                                for line in lines[:5]:  # Show first 5 tracks
                                    try:
                                        if line.strip():
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
                                    with st.spinner("Downloading..."):
                                        success, stdout, stderr = (
                                            downloader.download_single_song(
                                                result["url"]
                                            )
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

        # Quick genre/region search
        st.markdown("---")
        st.subheader("🔥 Quick Discovery")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🎵 Music Genres:**")
            if st.button("🎸 Rock Hits"):
                st.query_params.search = "rock hits 2024"
            if st.button("🎤 Pop Music"):
                st.query_params.search = "pop music hits"
            if st.button("🎧 Electronic"):
                st.query_params.search = "electronic music"

        with col2:
            st.markdown("**🌍 Regional Music:**")
            if st.button("🇮🇳 Bollywood"):
                st.query_params.search = "bollywood hits"
            if st.button("🇰🇷 K-Pop"):
                st.query_params.search = "kpop hits"
            if st.button("🇯🇵 J-Pop"):
                st.query_params.search = "jpop hits"

        with col3:
            st.markdown("**📅 Time Periods:**")
            if st.button("🆕 2024 Hits"):
                st.query_params.search = "best songs 2024"
            if st.button("📻 90s Classics"):
                st.query_params.search = "90s hits"
            if st.button("🎶 80s Music"):
                st.query_params.search = "80s classics"

    with tab4:
        st.header("📊 Download Activity")

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

    # Footer
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; color: #666;">
    🎵 Lucky's Music Empire | Powered by yt-dlp & Navidrome | 
    <a href="https://music.luckyverma.com" target="_blank">🎧 Open Music Player</a>
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
