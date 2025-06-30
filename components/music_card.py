import streamlit as st
from typing import Dict, Optional


def display_music_card(
    track: Dict,
    key_suffix: str = "",
    show_download: bool = True,
    show_preview: bool = True,
):
    """Display a rich music card with album art and metadata"""

    # Card container
    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            # Album art
            if track.get("album_art") or track.get("thumbnail"):
                image_url = track.get("album_art") or track.get("thumbnail")
                st.image(image_url, width=80)
            else:
                # Placeholder for missing album art
                st.markdown(
                    """
                <div style="width: 80px; height: 80px; background: linear-gradient(45deg, #ff6b6b, #ee5a24); 
                     border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                    🎵
                </div>
                """,
                    unsafe_allow_html=True,
                )

        with col2:
            # Track information
            title = track.get("title") or track.get("name", "Unknown Title")
            artists = (
                track.get("artists", [])
                if isinstance(track.get("artists"), list)
                else [track.get("artist", "Unknown Artist")]
            )
            artist_str = (
                ", ".join(artists)
                if artists
                else track.get("uploader", "Unknown Artist")
            )

            st.markdown(
                f"""
            <div style="padding: 5px 0;">
                <div style="font-weight: bold; font-size: 16px; margin-bottom: 2px;">
                    {title[:50]}{'...' if len(title) > 50 else ''}
                </div>
                <div style="color: #888; font-size: 14px; margin-bottom: 2px;">
                    🎤 {artist_str}
                </div>
                <div style="color: #666; font-size: 12px;">
                    ⏱️ {track.get('duration_str', 'N/A')} 
                    {f"| 👀 {track.get('view_count', 0):,}" if track.get('view_count') else ""}
                    {f"| ⭐ {track.get('popularity', 0)}" if track.get('popularity') else ""}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            # Additional info for Spotify tracks
            if track.get("album"):
                st.caption(f"💿 {track['album']}")

        with col3:
            # Action buttons
            if show_preview and track.get("preview_url"):
                if st.button("🔊", key=f"preview_{key_suffix}", help="Preview"):
                    st.audio(track["preview_url"])

            if show_download:
                download_key = f"download_{key_suffix}"
                if st.button("📥", key=download_key, help="Download"):
                    return "download"

            copy_key = f"copy_{key_suffix}"
            if st.button("📋", key=copy_key, help="Copy URL"):
                url = track.get("url") or track.get("external_urls", {}).get(
                    "spotify", ""
                )
                if url:
                    st.code(url)

    st.markdown("---")
    return None


def display_compact_music_card(track: Dict, key_suffix: str = ""):
    """Display a compact music card for lists"""
    col1, col2, col3 = st.columns([2, 4, 1])

    with col1:
        if track.get("album_art") or track.get("thumbnail"):
            image_url = track.get("album_art") or track.get("thumbnail")
            st.image(image_url, width=60)

    with col2:
        title = track.get("title") or track.get("name", "Unknown")
        artist = (
            track.get("artist")
            or ", ".join(track.get("artists", []))
            or track.get("uploader", "Unknown")
        )

        st.markdown(
            f"""
        **{title[:30]}{'...' if len(title) > 30 else ''}**  
        {artist[:25]}{'...' if len(artist) > 25 else ''}
        """
        )

    with col3:
        if st.button("📥", key=f"compact_download_{key_suffix}", help="Download"):
            return "download"

    return None
