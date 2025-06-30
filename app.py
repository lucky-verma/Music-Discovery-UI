import streamlit as st
import sys
import os
import subprocess

# Proper path handling for all environments
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import with proper error handling
try:
    from services.spotify_service import SpotifyService
    from services.youtube_service import YouTubeService
    from services.job_service import JobManager
    from components.sidebar import render_sidebar

    # Check if pages modules exist
    pages_available = True
    try:
        from pages.discovery import render_discovery_page
        from pages.import_page import render_import_page
    except ImportError as e:
        st.error(f"Pages import error: {e}")
        pages_available = False

except ImportError as e:
    st.error(f"Critical import error: {e}")
    st.error("Please check that all module files exist and are properly configured.")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="🎵 Lucky's Music Discovery Hub",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
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
    .music-card {
        border: 1px solid #333;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: #1e1e1e;
    }
    .album-art {
        border-radius: 8px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
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


def main():
    """Main application"""

    # Initialize services with error handling
    try:
        if "spotify_service" not in st.session_state:
            st.session_state.spotify_service = SpotifyService()

        if "youtube_service" not in st.session_state:
            st.session_state.youtube_service = YouTubeService()

        if "job_manager" not in st.session_state:
            st.session_state.job_manager = JobManager()
    except Exception as e:
        st.error(f"Service initialization error: {e}")
        st.stop()

    # Header
    st.title("🎵 Lucky's Music Discovery Hub")
    st.markdown("**Your Personal Music Automation Empire**")

    # Render sidebar
    try:
        render_sidebar(st.session_state.spotify_service, st.session_state.job_manager)
    except Exception as e:
        st.error(f"Sidebar error: {e}")

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "🎵 Quick Download",
            "📋 Playlist Manager",
            "🔍 Discovery",
            "📥 Import & Manage",
            "📊 Download Status",
        ]
    )

    with tab1:
        render_quick_download_tab()

    with tab2:
        render_playlist_manager_tab()

    with tab3:
        if pages_available:
            try:
                render_discovery_page(
                    st.session_state.spotify_service,
                    st.session_state.youtube_service,
                    st.session_state.job_manager,
                )
            except Exception as e:
                st.error(f"Discovery page error: {e}")
                st.info("Discovery features temporarily unavailable.")
                # Show basic fallback content
                st.header("🔍 Music Discovery")
                st.info("Please check the application logs for import issues.")

    with tab4:
        if pages_available:
            try:
                render_import_page()
            except Exception as e:
                st.error(f"Import page error: {e}")
                st.info("Import features temporarily unavailable.")
                # Show basic fallback content
                st.header("📥 Music Import & Management")
                st.info("Please check the application logs for import issues.")

    with tab5:
        render_download_status_tab()

    # Footer
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; color: #666;">
    🎵 Lucky's Music Empire | Background Downloads Active | 
    <a href="https://music.luckyverma.com" target="_blank">🎧 Open Navidrome</a> |
    <a href="https://music-download.luckyverma.com" target="_blank">📱 Download Interface</a>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_quick_download_tab():
    """Render quick download tab"""
    st.header("🎵 Quick Song Download")

    col1, col2 = st.columns([2, 1])

    with col1:
        url = st.text_input(
            "🔗 YouTube/YouTube Music URL:",
            placeholder="https://music.youtube.com/watch?v=dQw4w9WgXcQ",
            help="Paste any YouTube or YouTube Music URL here",
        )

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

        if st.button("👁️ Preview Info", disabled=not url):
            if url:
                with st.spinner("Fetching video info..."):
                    try:
                        info = st.session_state.youtube_service.get_video_info(url)
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
                    except Exception as e:
                        st.error(f"Preview error: {e}")

    st.markdown("---")

    if st.button("📥 Download Song (Background)", type="primary", disabled=not url):
        if url:
            try:
                job_id = st.session_state.job_manager.add_job(
                    "single_song",
                    url,
                    {"artist": artist_override, "album": album_override},
                )
                st.success(f"✅ Download queued! Job ID: {job_id}")
            except Exception as e:
                st.error(f"Download error: {e}")


def render_playlist_manager_tab():
    """Render playlist manager tab"""
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

    if st.button(
        "📥 Download Playlist (Background)", type="primary", disabled=not playlist_url
    ):
        if playlist_url:
            try:
                job_id = st.session_state.job_manager.add_job(
                    "playlist",
                    playlist_url,
                    {"playlist_name": playlist_name or "Downloaded Playlist"},
                )
                st.success(f"✅ Playlist download queued! Job ID: {job_id}")
            except Exception as e:
                st.error(f"Playlist download error: {e}")


def render_download_status_tab():
    """Render download status tab"""
    st.header("📊 Download Status & Activity")

    if st.button("🔄 Refresh Status"):
        st.rerun()

    try:
        jobs = st.session_state.job_manager.get_all_jobs()
    except Exception as e:
        st.error(f"Error loading jobs: {e}")
        jobs = {}

    if not jobs:
        st.info("No download jobs yet. Start downloading some music!")
        return

    # Active downloads
    active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "running"]]
    if active_jobs:
        st.subheader("🔄 Active Downloads")
        for job in active_jobs:
            status_icon = "🔄" if job["status"] == "running" else "⏳"

            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.markdown(
                        f"""
                    **{status_icon} {job['type'].replace('_', ' ').title()}**  
                    URL: `{job['url'][:50]}...`  
                    Status: {job['message']}
                    """
                    )

                with col2:
                    progress = job.get("progress", 0)
                    st.progress(progress / 100)
                    st.caption(f"{progress}%")

                with col3:
                    st.caption(f"Job: {job['id']}")

    # Recent completed downloads
    completed_jobs = sorted(
        [j for j in jobs.values() if j["status"] == "completed"],
        key=lambda x: x.get("updated", x["created"]),
        reverse=True,
    )[:10]

    if completed_jobs:
        st.subheader("✅ Recent Completed Downloads")
        for job in completed_jobs:
            completed_time = job.get("updated", job["created"])[:19].replace("T", " ")
            st.success(f"✅ {job['type'].replace('_', ' ').title()} - {completed_time}")


if __name__ == "__main__":
    main()
