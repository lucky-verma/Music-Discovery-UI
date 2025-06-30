import streamlit as st
import subprocess
from services.spotify_service import SpotifyService
from utils.config import Config


def render_sidebar(spotify_service: SpotifyService, job_manager):
    """Render the enhanced sidebar with all controls"""

    with st.sidebar:
        st.header("🔧 Settings & Integration")

        # Library stats
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

            # Storage info
            storage_cmd = ["df", "-h", "/music"]
            storage_info = subprocess.run(storage_cmd, capture_output=True, text=True)
            if storage_info.returncode == 0:
                lines = storage_info.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        st.metric("Storage Used", parts[2])
                        st.metric("Storage Free", parts[3])
        except:
            st.metric("Total Tracks", "N/A")

        st.markdown("---")

        # Spotify Integration
        st.subheader("🎵 Spotify Integration")

        config = Config()
        current_client_id = config.get("spotify.client_id", "")

        if current_client_id:
            st.success(f"✅ Connected (ID: {current_client_id[:8]}...)")

            if st.button("🔄 Refresh Token"):
                if spotify_service._get_access_token():
                    st.success("Token refreshed!")
                    st.rerun()
                else:
                    st.error("Failed to refresh token")
        else:
            with st.expander("🔗 Configure Spotify API", expanded=True):
                st.markdown(
                    """
                **Quick Setup:**
                1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
                2. Create app with these settings:
                   - **App name**: `Navidrome Music Discovery`
                   - **App description**: `Personal music discovery`
                   - **Redirect URI**: `http://127.0.0.1:8501`
                   - **API**: Select `Web API`
                3. Copy Client ID and Secret below
                """
                )

                spotify_client_id = st.text_input("Client ID", type="password")
                spotify_client_secret = st.text_input("Client Secret", type="password")

                if st.button("🔗 Connect Spotify"):
                    if spotify_client_id and spotify_client_secret:
                        if spotify_service.set_credentials(
                            spotify_client_id, spotify_client_secret
                        ):
                            st.success("✅ Spotify connected successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to connect. Check credentials.")
                    else:
                        st.error("Please enter both Client ID and Secret")

        st.markdown("---")

        # Job Status
        st.subheader("🔄 Download Jobs")
        jobs = job_manager.get_all_jobs()

        if jobs:
            active_jobs = [
                j for j in jobs.values() if j["status"] in ["queued", "running"]
            ]
            completed_jobs = [j for j in jobs.values() if j["status"] == "completed"]
            failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Active", len(active_jobs))
                st.metric("Completed", len(completed_jobs))
            with col2:
                st.metric("Failed", len(failed_jobs))
                total = len(jobs)
                success_rate = (len(completed_jobs) / total * 100) if total > 0 else 0
                st.metric("Success Rate", f"{success_rate:.0f}%")

            if st.button("🔄 Refresh Jobs"):
                st.rerun()
        else:
            st.info("No download jobs yet")

        st.markdown("---")

        # Quick Links
        st.subheader("🎧 Quick Access")
        st.markdown("**Music Services:**")
        st.markdown("🎵 [Navidrome Player](https://music.luckyverma.com)")
        st.markdown("📱 [Download Status](https://music-download.luckyverma.com)")

        st.markdown("**Library Paths:**")
        st.code("/music/youtube-music/")
        st.code("/music/library/")
