import streamlit as st
from components.music_card import display_music_card
from services.spotify_service import SpotifyService
from services.youtube_service import YouTubeService


def render_discovery_page(
    spotify_service: SpotifyService, youtube_service: YouTubeService, job_manager
):
    """Render the enhanced discovery page with Spotify integration"""

    st.header("🔍 Enhanced Music Discovery")

    # Check Spotify connection
    access_token = spotify_service.config.get("spotify.access_token")
    spotify_connected = bool(access_token)

    if spotify_connected:
        # Featured content section
        st.subheader("🌟 Trending & Featured")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔥 Get Featured Playlists"):
                with st.spinner("Fetching Spotify featured content..."):
                    featured = spotify_service.get_featured_playlists(limit=6)
                    if featured:
                        st.session_state.featured_playlists = featured
                        st.rerun()

        with col2:
            if st.button("🎯 Get Recommendations"):
                with st.spinner("Getting personalized recommendations..."):
                    recommendations = spotify_service.get_recommendations(limit=10)
                    if recommendations:
                        st.session_state.recommendations = recommendations
                        st.rerun()

        # Display featured playlists
        if hasattr(st.session_state, "featured_playlists"):
            st.markdown("**🎵 Featured Playlists:**")

            cols = st.columns(3)
            for i, playlist in enumerate(st.session_state.featured_playlists):
                with cols[i % 3]:
                    if playlist.get("image"):
                        st.image(playlist["image"], width=150)

                    st.markdown(
                        f"""
                    **{playlist['name']}**  
                    {playlist['description'][:50]}...  
                    🎵 {playlist['tracks_total']} tracks
                    """
                    )

                    if st.button(f"📥 Import Playlist", key=f"import_playlist_{i}"):
                        with st.spinner("Importing playlist..."):
                            tracks = spotify_service.get_playlist_tracks(playlist["id"])
                            if tracks:
                                st.session_state[f"playlist_tracks_{i}"] = tracks
                                st.success(f"Found {len(tracks)} tracks!")
                                st.rerun()

        # Display recommendations
        if hasattr(st.session_state, "recommendations"):
            st.markdown("**🎯 Recommended for You:**")

            for i, track in enumerate(st.session_state.recommendations[:5]):
                action = display_music_card(track, f"rec_{i}", show_preview=True)
                if action == "download":
                    # Convert to YouTube search and download
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
                        st.success(f"✅ Queued for download! Job: {job_id}")
                        st.rerun()

    st.markdown("---")

    # Enhanced search section
    st.subheader("🔍 Search Music")

    search_col1, search_col2 = st.columns([3, 1])

    with search_col1:
        search_query = st.text_input(
            "🔎 Search for music:", placeholder="Enter artist, song, or album name"
        )

    with search_col2:
        search_source = st.selectbox(
            "Source:",
            ["🎵 Spotify", "▶️ YouTube"] if spotify_connected else ["▶️ YouTube"],
        )

    if st.button("🔍 Search", disabled=not search_query):
        if search_query:
            with st.spinner(f"Searching {search_source}..."):
                if search_source == "🎵 Spotify" and spotify_connected:
                    results = spotify_service.search_tracks(search_query, limit=10)
                    st.session_state.search_results = results
                    st.session_state.search_source = "spotify"
                else:
                    results = youtube_service.search_music(search_query, max_results=10)
                    st.session_state.search_results = results
                    st.session_state.search_source = "youtube"

                if results:
                    st.success(f"Found {len(results)} results!")
                    st.rerun()
                else:
                    st.warning("No results found. Try different search terms.")

    # Display search results
    if hasattr(st.session_state, "search_results") and st.session_state.search_results:
        st.markdown(f"**🎵 {search_query.title()} - Search Results:**")

        for i, track in enumerate(st.session_state.search_results):
            action = display_music_card(
                track,
                f"search_{i}",
                show_preview=(st.session_state.search_source == "spotify"),
            )

            if action == "download":
                if st.session_state.search_source == "spotify":
                    # Convert Spotify track to YouTube search and download
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
                        st.success(f"✅ Queued for download! Job: {job_id}")
                else:
                    # Direct YouTube download
                    job_id = job_manager.add_job("single_song", track["url"], {})
                    st.success(f"✅ Queued for download! Job: {job_id}")

                st.rerun()

    st.markdown("---")

    # Quick discovery buttons with enhanced content
    st.subheader("🔥 Quick Discovery")

    discovery_categories = {
        "🎸 Rock Hits": "rock hits 2024",
        "🎤 Pop Charts": "pop music hits 2024",
        "🎵 Indie Vibes": "indie music 2024",
        "🇮🇳 Bollywood": "bollywood hits 2024",
        "🇰🇷 K-Pop": "kpop hits 2024",
        "🇯🇵 J-Pop": "jpop hits 2024",
        "🆕 New Releases": "new music 2024",
        "📻 Throwback": "throwback hits",
        "🎶 Classics": "classic hits all time",
    }

    cols = st.columns(3)

    for i, (button_text, search_term) in enumerate(discovery_categories.items()):
        with cols[i % 3]:
            if st.button(button_text, key=f"discovery_{i}"):
                with st.spinner(f"Discovering {button_text}..."):
                    if spotify_connected:
                        # Use Spotify for better results
                        results = spotify_service.search_tracks(search_term, limit=8)
                        source = "spotify"
                    else:
                        # Fallback to YouTube
                        results = youtube_service.search_music(
                            search_term, max_results=8
                        )
                        source = "youtube"

                    if results:
                        st.session_state.discovery_results = results
                        st.session_state.discovery_query = button_text
                        st.session_state.discovery_source = source
                        st.rerun()

    # Display discovery results
    if (
        hasattr(st.session_state, "discovery_results")
        and st.session_state.discovery_results
    ):
        st.markdown(f"**{st.session_state.discovery_query} Results:**")

        for i, track in enumerate(st.session_state.discovery_results):
            action = display_music_card(
                track,
                f"disc_{i}",
                show_preview=(st.session_state.discovery_source == "spotify"),
            )

            if action == "download":
                if st.session_state.discovery_source == "spotify":
                    # Convert to YouTube and download
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
                        st.success(f"✅ Queued! Job: {job_id}")
                else:
                    job_id = job_manager.add_job("single_song", track["url"], {})
                    st.success(f"✅ Queued! Job: {job_id}")

                st.rerun()
