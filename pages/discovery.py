import streamlit as st
import requests
import json
from typing import List, Dict
import pandas as pd
from datetime import datetime
import base64


def render_discovery_page(spotify_service, youtube_service, job_manager):
    """Render the enhanced discovery page with rich Spotify integration"""

    st.header("🔍 Enhanced Music Discovery")

    # Check Spotify connection status
    access_token = spotify_service.config.get("spotify.access_token")
    spotify_connected = bool(access_token)

    # Connection status indicator
    if spotify_connected:
        st.success("🎵 **Spotify Connected** - Full discovery features available!")
    else:
        st.warning("⚠️ **Spotify Not Connected** - Limited to YouTube search only")
        st.info(
            "💡 Configure Spotify API in the sidebar for enhanced discovery features"
        )

    # Landing page with featured content
    render_landing_section(
        spotify_service, youtube_service, job_manager, spotify_connected
    )

    st.markdown("---")

    # Enhanced search section
    render_enhanced_search(
        spotify_service, youtube_service, job_manager, spotify_connected
    )

    st.markdown("---")

    # Genre and mood-based discovery
    render_genre_discovery(
        spotify_service, youtube_service, job_manager, spotify_connected
    )

    st.markdown("---")

    # Trending and charts
    render_trending_section(
        spotify_service, youtube_service, job_manager, spotify_connected
    )


def render_landing_section(
    spotify_service, youtube_service, job_manager, spotify_connected
):
    """Render the landing section with featured content"""

    st.subheader("🌟 Welcome to Your Music Universe")

    if spotify_connected:
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔥 **Today's Hits**", use_container_width=True):
                with st.spinner("🎵 Fetching today's hottest tracks..."):
                    results = spotify_service.search_tracks("today hits 2024", limit=10)
                    if results:
                        st.session_state.discovery_results = results
                        st.session_state.discovery_title = "🔥 Today's Hits"
                        st.session_state.discovery_source = "spotify"
                        st.rerun()

        with col2:
            if st.button("🎯 **Recommended for You**", use_container_width=True):
                with st.spinner("🎵 Getting personalized recommendations..."):
                    recommendations = spotify_service.get_recommendations(limit=10)
                    if recommendations:
                        st.session_state.discovery_results = recommendations
                        st.session_state.discovery_title = "🎯 Recommended for You"
                        st.session_state.discovery_source = "spotify"
                        st.rerun()

        with col3:
            if st.button("📻 **Featured Playlists**", use_container_width=True):
                with st.spinner("🎵 Loading featured playlists..."):
                    playlists = spotify_service.get_featured_playlists(limit=6)
                    if playlists:
                        st.session_state.featured_playlists = playlists
                        st.rerun()

        # Display featured playlists
        if hasattr(st.session_state, "featured_playlists"):
            st.markdown("### 📻 **Featured Playlists**")

            playlist_cols = st.columns(3)
            for i, playlist in enumerate(st.session_state.featured_playlists):
                with playlist_cols[i % 3]:
                    # Playlist card with image
                    if playlist.get("image"):
                        st.image(playlist["image"], width=200, caption=playlist["name"])

                    st.markdown(
                        f"""
                    <div style="background: #1e1e1e; padding: 1rem; border-radius: 10px; margin: 0.5rem 0;">
                        <h4>{playlist['name']}</h4>
                        <p style="color: #888; font-size: 0.9em;">{playlist['description'][:100]}...</p>
                        <p style="color: #4CAF50;">🎵 {playlist['tracks_total']} tracks</p>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

                    if st.button(f"📥 **Import Playlist**", key=f"import_pl_{i}"):
                        with st.spinner(f"Importing {playlist['name']}..."):
                            tracks = spotify_service.get_playlist_tracks(playlist["id"])
                            if tracks:
                                # Queue multiple downloads
                                for track in tracks[:20]:  # Limit to first 20 tracks
                                    youtube_results = youtube_service.search_music(
                                        track["search_query"], max_results=1
                                    )
                                    if youtube_results:
                                        job_id = job_manager.add_job(
                                            "single_song",
                                            youtube_results[0]["url"],
                                            {
                                                "artist": ", ".join(track["artists"]),
                                                "album": track["album"],
                                            },
                                        )
                                st.success(
                                    f"✅ Queued {len(tracks[:20])} songs from {playlist['name']}!"
                                )

    else:
        # Fallback for no Spotify connection
        st.info(
            "🎵 **Quick YouTube Discovery** (Spotify connection recommended for full features)"
        )

        quick_searches = [
            "🎸 Rock Hits 2024",
            "🎤 Pop Charts",
            "🎵 Indie Vibes",
            "🇮🇳 Bollywood Hits",
            "🇰🇷 K-Pop Trending",
            "🎶 Classical Favorites",
        ]

        search_cols = st.columns(3)
        for i, search_term in enumerate(quick_searches):
            with search_cols[i % 3]:
                if st.button(search_term, key=f"quick_{i}"):
                    query = search_term.split(" ", 1)[1].lower()
                    results = youtube_service.search_music(query, max_results=8)
                    if results:
                        st.session_state.discovery_results = results
                        st.session_state.discovery_title = search_term
                        st.session_state.discovery_source = "youtube"
                        st.rerun()


def render_enhanced_search(
    spotify_service, youtube_service, job_manager, spotify_connected
):
    """Render enhanced search with multiple sources and filters"""

    st.subheader("🔍 **Advanced Music Search**")

    # Search interface
    search_col1, search_col2, search_col3 = st.columns([3, 1, 1])

    with search_col1:
        search_query = st.text_input(
            "🎵 **Search for music:**",
            placeholder="Artist, song, album, or mood (e.g., 'chill electronic', 'arijit singh romantic')",
            help="Search across multiple sources for the best results",
        )

    with search_col2:
        search_source = st.selectbox(
            "Source:",
            (
                ["🎵 Spotify (Best)", "▶️ YouTube", "🔄 Both"]
                if spotify_connected
                else ["▶️ YouTube"]
            ),
        )

    with search_col3:
        max_results = st.selectbox("Results:", [5, 10, 15, 20], index=1)

    # Advanced filters (only for Spotify)
    if spotify_connected and search_source != "▶️ YouTube":
        with st.expander("🎛️ **Advanced Filters**"):
            filter_col1, filter_col2, filter_col3 = st.columns(3)

            with filter_col1:
                min_popularity = st.slider("Minimum Popularity", 0, 100, 30)
                explicit_filter = st.checkbox("Include Explicit Content", value=True)

            with filter_col2:
                release_year = st.selectbox(
                    "Release Year",
                    ["Any", "2024", "2023", "2020s", "2010s", "2000s", "90s"],
                )
                audio_features = st.multiselect(
                    "Mood/Style",
                    [
                        "High Energy",
                        "Danceable",
                        "Acoustic",
                        "Instrumental",
                        "Live Recording",
                    ],
                )

            with filter_col3:
                duration_range = st.select_slider(
                    "Song Duration",
                    options=["Any", "Short (<3min)", "Medium (3-5min)", "Long (>5min)"],
                    value="Any",
                )

    # Search execution
    if st.button("🔍 **Search Music**", disabled=not search_query, type="primary"):
        if search_query:
            search_results = []

            with st.spinner(
                f"🎵 Searching {search_source.split(' ')[1] if ' ' in search_source else search_source}..."
            ):

                if search_source == "🎵 Spotify (Best)" and spotify_connected:
                    search_results = spotify_service.search_tracks(
                        search_query, limit=max_results
                    )
                    source = "spotify"

                elif search_source == "▶️ YouTube":
                    search_results = youtube_service.search_music(
                        search_query, max_results=max_results
                    )
                    source = "youtube"

                elif search_source == "🔄 Both" and spotify_connected:
                    # Search both sources and merge results
                    spotify_results = spotify_service.search_tracks(
                        search_query, limit=max_results // 2
                    )
                    youtube_results = youtube_service.search_music(
                        search_query, max_results=max_results // 2
                    )

                    # Tag results with source
                    for result in spotify_results:
                        result["_source"] = "spotify"
                    for result in youtube_results:
                        result["_source"] = "youtube"

                    search_results = spotify_results + youtube_results
                    source = "both"

                if search_results:
                    st.session_state.search_results = search_results
                    st.session_state.search_query = search_query
                    st.session_state.search_source = source
                    st.success(f"🎵 Found {len(search_results)} results!")
                    st.rerun()
                else:
                    st.warning(
                        "😔 No results found. Try different search terms or check your spelling."
                    )

    # Display search results with rich cards
    display_search_results(spotify_service, youtube_service, job_manager)


def display_search_results(spotify_service, youtube_service, job_manager):
    """Display search results with rich music cards"""

    if hasattr(st.session_state, "search_results") and st.session_state.search_results:
        st.markdown(f"### 🎵 **Search Results for '{st.session_state.search_query}'**")

        # Results view toggle
        view_col1, view_col2 = st.columns([1, 4])
        with view_col1:
            view_mode = st.radio("View:", ["🎴 Cards", "📋 List"], horizontal=True)

        if view_mode == "🎴 Cards":
            # Card view with album art
            for i in range(0, len(st.session_state.search_results), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    if i + j < len(st.session_state.search_results):
                        track = st.session_state.search_results[i + j]
                        with col:
                            render_music_card(
                                track,
                                f"search_{i+j}",
                                spotify_service,
                                youtube_service,
                                job_manager,
                            )
        else:
            # List view
            for i, track in enumerate(st.session_state.search_results):
                render_music_list_item(
                    track,
                    f"search_list_{i}",
                    spotify_service,
                    youtube_service,
                    job_manager,
                )


def render_music_card(track, key_suffix, spotify_service, youtube_service, job_manager):
    """Render a rich music card with album art and metadata"""

    # Determine source and get appropriate data
    source = track.get("_source", st.session_state.get("search_source", "unknown"))

    if source == "spotify":
        title = track.get("name", "Unknown Title")
        artists = ", ".join(track.get("artists", ["Unknown Artist"]))
        album = track.get("album", "Unknown Album")
        image_url = track.get("album_art")
        duration_ms = track.get("duration_ms", 0)
        duration_str = (
            f"{duration_ms//60000}:{(duration_ms//1000)%60:02d}"
            if duration_ms
            else "N/A"
        )
        popularity = track.get("popularity", 0)
        preview_url = track.get("preview_url")
        source_icon = "🎵"
    else:  # YouTube
        title = track.get("title", "Unknown Title")
        artists = track.get("artist", "Unknown Artist")
        album = "YouTube"
        image_url = track.get("thumbnail")
        duration_str = track.get("duration_str", "N/A")
        popularity = 0
        preview_url = None
        source_icon = "▶️"

    # Card container
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
        border: 1px solid #333;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: transform 0.2s ease;
    ">
    """

    st.markdown(card_html, unsafe_allow_html=True)

    # Album art and info
    art_col, info_col, action_col = st.columns([1, 2, 1])

    with art_col:
        if image_url:
            st.image(image_url, width=120)
        else:
            st.markdown(
                """
            <div style="
                width: 120px; height: 120px; 
                background: linear-gradient(45deg, #ff6b6b, #ee5a24); 
                border-radius: 10px; 
                display: flex; align-items: center; justify-content: center; 
                color: white; font-size: 2em; font-weight: bold;
            ">🎵</div>
            """,
                unsafe_allow_html=True,
            )

    with info_col:
        st.markdown(
            f"""
        <div style="padding: 0.5rem 0;">
            <h3 style="margin: 0; color: #fff; font-size: 1.2em;">
                {source_icon} {title[:40]}{'...' if len(title) > 40 else ''}
            </h3>
            <p style="margin: 0.2rem 0; color: #4CAF50; font-size: 1em; font-weight: 500;">
                🎤 {artists[:35]}{'...' if len(artists) > 35 else ''}
            </p>
            <p style="margin: 0.2rem 0; color: #888; font-size: 0.9em;">
                💿 {album[:30]}{'...' if len(album) > 30 else ''}
            </p>
            <div style="margin-top: 0.5rem;">
                <span style="color: #666; font-size: 0.8em;">
                    ⏱️ {duration_str}
                    {f" | ⭐ {popularity}" if popularity > 0 else ""}
                    {f" | 👀 {track.get('view_count', 0):,}" if track.get('view_count') else ""}
                </span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with action_col:
        # Preview button (Spotify only)
        if preview_url:
            if st.button("🔊", key=f"preview_{key_suffix}", help="Preview"):
                st.audio(preview_url)

        # Download button
        if st.button(
            "📥", key=f"download_{key_suffix}", help="Download", type="primary"
        ):
            if source == "spotify":
                # Convert Spotify to YouTube and download
                youtube_results = youtube_service.search_music(
                    track["search_query"], max_results=1
                )
                if youtube_results:
                    job_id = job_manager.add_job(
                        "single_song",
                        youtube_results[0]["url"],
                        {"artist": artists, "album": album},
                    )
                    st.success(f"✅ Queued for download! Job: {job_id}")
                else:
                    st.error("❌ Could not find YouTube version")
            else:
                # Direct YouTube download
                job_id = job_manager.add_job("single_song", track["url"], {})
                st.success(f"✅ Queued for download! Job: {job_id}")

        # Copy URL button
        if st.button("📋", key=f"copy_{key_suffix}", help="Copy URL"):
            if source == "spotify":
                st.code(track.get("external_urls", {}).get("spotify", "No URL"))
            else:
                st.code(track.get("url", "No URL"))

    st.markdown("</div>", unsafe_allow_html=True)


def render_music_list_item(
    track, key_suffix, spotify_service, youtube_service, job_manager
):
    """Render a compact list item for music"""

    source = track.get("_source", st.session_state.get("search_source", "unknown"))

    if source == "spotify":
        title = track.get("name", "Unknown Title")
        artists = ", ".join(track.get("artists", ["Unknown Artist"]))
        album = track.get("album", "Unknown Album")
        duration_ms = track.get("duration_ms", 0)
        duration_str = (
            f"{duration_ms//60000}:{(duration_ms//1000)%60:02d}"
            if duration_ms
            else "N/A"
        )
        source_icon = "🎵"
    else:
        title = track.get("title", "Unknown Title")
        artists = track.get("artist", "Unknown Artist")
        album = "YouTube"
        duration_str = track.get("duration_str", "N/A")
        source_icon = "▶️"

    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

    with col1:
        st.markdown(f"**{source_icon} {title}**")
        st.caption(f"🎤 {artists}")

    with col2:
        st.markdown(f"💿 {album}")
        st.caption(f"⏱️ {duration_str}")

    with col3:
        if track.get("preview_url"):
            if st.button("🔊", key=f"prev_{key_suffix}"):
                st.audio(track["preview_url"])

    with col4:
        if st.button("📥", key=f"dl_{key_suffix}"):
            if source == "spotify":
                youtube_results = youtube_service.search_music(
                    track["search_query"], max_results=1
                )
                if youtube_results:
                    job_id = job_manager.add_job(
                        "single_song",
                        youtube_results[0]["url"],
                        {"artist": artists, "album": album},
                    )
                    st.success(f"✅ Queued!")
            else:
                job_id = job_manager.add_job("single_song", track["url"], {})
                st.success(f"✅ Queued!")


def render_genre_discovery(
    spotify_service, youtube_service, job_manager, spotify_connected
):
    """Render genre and mood-based discovery section"""

    st.subheader("🎭 **Discover by Genre & Mood**")

    if spotify_connected:
        # Genre categories with enhanced descriptions
        genre_categories = {
            "🎸 **Rock & Alternative**": {
                "rock": "Classic and modern rock hits",
                "alternative": "Alternative and indie rock",
                "metal": "Heavy metal and hard rock",
                "punk": "Punk and post-punk",
            },
            "🎤 **Pop & Mainstream**": {
                "pop": "Current pop hits and classics",
                "dance-pop": "Danceable pop music",
                "electropop": "Electronic-influenced pop",
                "teen-pop": "Teen and young adult pop",
            },
            "🎵 **Electronic & Dance**": {
                "electronic": "Electronic music and EDM",
                "house": "House music and deep house",
                "techno": "Techno and minimal",
                "dubstep": "Dubstep and bass music",
            },
            "🌍 **World & Regional**": {
                "bollywood": "Indian Bollywood music",
                "k-pop": "Korean pop music",
                "latin": "Latin American music",
                "afrobeat": "African beats and rhythms",
            },
            "🎷 **Jazz & Classical**": {
                "jazz": "Jazz standards and modern",
                "classical": "Classical compositions",
                "blues": "Blues and soul",
                "gospel": "Gospel and spiritual",
            },
        }

        # Display genres in expandable sections
        for category, genres in genre_categories.items():
            with st.expander(category):
                genre_cols = st.columns(2)
                for i, (genre, description) in enumerate(genres.items()):
                    with genre_cols[i % 2]:
                        st.markdown(f"**{genre.title()}**")
                        st.caption(description)
                        if st.button(
                            f"🔍 Explore {genre.title()}", key=f"genre_{genre}"
                        ):
                            with st.spinner(f"Finding {genre} music..."):
                                results = spotify_service.search_tracks(
                                    f"genre:{genre}", limit=8
                                )
                                if results:
                                    st.session_state.discovery_results = results
                                    st.session_state.discovery_title = (
                                        f"🎵 {genre.title()} Music"
                                    )
                                    st.session_state.discovery_source = "spotify"
                                    st.rerun()

    else:
        # Simplified genre discovery for YouTube
        st.info(
            "🎵 **YouTube Genre Discovery** (Limited features - Spotify recommended)"
        )

        genres = [
            "🎸 Rock",
            "🎤 Pop",
            "🎵 Electronic",
            "🇮🇳 Bollywood",
            "🇰🇷 K-Pop",
            "🎷 Jazz",
            "🎼 Classical",
            "🎺 Blues",
        ]

        genre_cols = st.columns(4)
        for i, genre in enumerate(genres):
            with genre_cols[i % 4]:
                if st.button(genre, key=f"yt_genre_{i}"):
                    query = genre.split(" ", 1)[1].lower()
                    results = youtube_service.search_music(
                        f"{query} music", max_results=6
                    )
                    if results:
                        st.session_state.discovery_results = results
                        st.session_state.discovery_title = f"{genre} Music"
                        st.session_state.discovery_source = "youtube"
                        st.rerun()


def render_trending_section(
    spotify_service, youtube_service, job_manager, spotify_connected
):
    """Render trending and charts section"""

    st.subheader("📈 **Trending & Charts**")

    if spotify_connected:
        trend_col1, trend_col2, trend_col3 = st.columns(3)

        with trend_col1:
            if st.button("🔥 **Global Top 50**", use_container_width=True):
                with st.spinner("📊 Loading global charts..."):
                    # Search for popular current tracks
                    results = spotify_service.search_tracks("year:2024", limit=15)
                    if results:
                        # Sort by popularity
                        results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                        st.session_state.discovery_results = results[:10]
                        st.session_state.discovery_title = "🔥 Global Top 50"
                        st.session_state.discovery_source = "spotify"
                        st.rerun()

        with trend_col2:
            if st.button("🆕 **New Releases**", use_container_width=True):
                with st.spinner("🎵 Finding new releases..."):
                    # Search for recent releases
                    results = spotify_service.search_tracks("tag:new", limit=10)
                    if results:
                        st.session_state.discovery_results = results
                        st.session_state.discovery_title = "🆕 New Releases"
                        st.session_state.discovery_source = "spotify"
                        st.rerun()

        with trend_col3:
            if st.button("💎 **Hidden Gems**", use_container_width=True):
                with st.spinner("💎 Discovering hidden gems..."):
                    # Search for less popular but good tracks
                    recommendations = spotify_service.get_recommendations(limit=10)
                    if recommendations:
                        # Filter for lower popularity (hidden gems)
                        hidden_gems = [
                            track
                            for track in recommendations
                            if track.get("popularity", 0) < 70
                        ]
                        if hidden_gems:
                            st.session_state.discovery_results = hidden_gems
                            st.session_state.discovery_title = "💎 Hidden Gems"
                            st.session_state.discovery_source = "spotify"
                            st.rerun()

    # Display discovery results
    if (
        hasattr(st.session_state, "discovery_results")
        and st.session_state.discovery_results
    ):
        st.markdown(f"### {st.session_state.discovery_title}")

        # Display in card format
        for i in range(0, len(st.session_state.discovery_results), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(st.session_state.discovery_results):
                    track = st.session_state.discovery_results[i + j]
                    with col:
                        render_music_card(
                            track,
                            f"discovery_{i+j}",
                            spotify_service,
                            youtube_service,
                            job_manager,
                        )
