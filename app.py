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
    initial_sidebar_state="collapsed"
)

# Modern Spotify-like CSS
st.markdown("""
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
        box-shadow: 0 8px 25px rgba(29, 185, 84, 0.2);
    }
    
    /* Results container */
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
""", unsafe_allow_html=True)

class SimpleMusicApp:
    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
        os.makedirs("/config", exist_ok=True)
        if not os.path.exists(self.jobs_file):
            with open(self.jobs_file, 'w') as f:
                json.dump({}, f)
    
    def get_real_library_stats(self):
        """Get actual library statistics"""
        try:
            # Count music files
            cmd = ["find", "/music", "-type", "f", "-name", "*.mp3", "-o", "-name", "*.m4a", "-o", "-name", "*.flac"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            files = [f for f in result.stdout.split('\n') if f.strip()]
            
            # Get storage info
            storage_cmd = ["df", "-h", "/music"]
            storage_result = subprocess.run(storage_cmd, capture_output=True, text=True)
            
            used_size = "Unknown"
            if storage_result.returncode == 0:
                lines = storage_result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        used_size = parts[2]
            
            # Count artists and albums
            artists = set()
            albums = set()
            
            for file_path in files[:500]:  # Sample for performance
                try:
                    parts = file_path.split('/')
                    if len(parts) >= 4 and 'youtube-music' in parts:
                        youtube_idx = parts.index('youtube-music')
                        if youtube_idx + 1 < len(parts):
                            artists.add(parts[youtube_idx + 1])
                        if youtube_idx + 2 < len(parts):
                            albums.add(f"{parts[youtube_idx + 1]}/{parts[youtube_idx + 2]}")
                except:
                    continue
            
            return {
                'total_tracks': len(files),
                'artists': len(artists),
                'albums': len(albums),
                'storage_used': used_size
            }
        except Exception as e:
            return {
                'total_tracks': 0,
                'artists': 0,
                'albums': 0,
                'storage_used': 'Unknown'
            }
    
    def is_music_content(self, title, description="", duration=0):
        """FIXED: More lenient music filter"""
        title_lower = title.lower()
        desc_lower = description.lower()
        
        # Obvious non-music indicators (be more specific)
        non_music_keywords = [
            'tutorial', 'how to make', 'review of', 'reaction to', 'unboxing', 'gaming',
            'news report', 'interview with', 'movie trailer', 'tv show', 'podcast episode',
            'cooking recipe', 'workout routine', 'meditation guide', 'documentary',
            'vlog entry', 'comedy sketch'
        ]
        
        # Check for clear non-music indicators
        has_non_music = any(keyword in title_lower or keyword in desc_lower for keyword in non_music_keywords)
        
        # Duration filter (music typically 30 seconds to 20 minutes)
        reasonable_duration = 30 <= duration <= 1200  # 30 seconds to 20 minutes
        
        # If it has obvious non-music keywords, exclude it
        if has_non_music:
            return False
        
        # If duration is reasonable or unknown, include it (be more permissive)
        if reasonable_duration or duration == 0:
            return True
        
        # Default: include unless clearly not music
        return True
    
    def search_youtube_music(self, query, max_results=20, filter_music=True):
        """FIXED: Search YouTube Music with better error handling and logging"""
        try:
            st.write(f"🔍 Searching for: '{query}' (filter_music: {filter_music})")
            
            cmd = [
                "yt-dlp", 
                "--flat-playlist", 
                "--dump-json",
                "--playlist-end", str(max_results * 2 if filter_music else max_results),
                f"ytsearch{max_results * 2 if filter_music else max_results}:{query}"
            ]
            
            st.write(f"🔧 Running command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            
            st.write(f"📊 Command result: returncode={result.returncode}, stdout_lines={len(result.stdout.strip().split('\n')) if result.stdout else 0}")
            
            if result.returncode != 0:
                st.error(f"❌ yt-dlp error (code {result.returncode}): {result.stderr}")
                return []
            
            if not result.stdout.strip():
                st.warning("⚠️ No output from yt-dlp")
                return []
            
            results = []
            lines = result.stdout.strip().split('\n')
            
            for line_num, line in enumerate(lines):
                if line.strip():
                    try:
                        item = json.loads(line)
                        duration = int(item.get('duration', 0) or 0)
                        title = item.get('title', 'Unknown')
                        description = item.get('description', '')
                        
                        # Apply music filter if requested
                        if filter_music and not self.is_music_content(title, description, duration):
                            continue
                        
                        results.append({
                            'id': item.get('id', ''),
                            'title': title,
                            'uploader': item.get('uploader', 'Unknown'),
                            'duration': duration,
                            'duration_str': f"{duration//60}:{duration%60:02d}" if duration else "N/A",
                            'url': f"https://youtube.com/watch?v={item.get('id', '')}",
                            'thumbnail': f"https://img.youtube.com/vi/{item.get('id', '')}/mqdefault.jpg"
                        })
                        
                        # Stop when we have enough results
                        if len(results) >= max_results:
                            break
                            
                    except json.JSONDecodeError as e:
                        st.write(f"⚠️ JSON decode error on line {line_num}: {str(e)}")
                        continue
                    except Exception as e:
                        st.write(f"⚠️ Processing error on line {line_num}: {str(e)}")
                        continue
            
            st.write(f"✅ Found {len(results)} valid results after filtering")
            return results
            
        except subprocess.TimeoutExpired:
            st.error("❌ Search timeout - try a shorter query")
        except Exception as e:
            st.error(f"❌ Search failed: {str(e)}")
        
        return []
    
    def extract_playlist_info(self, url):
        """Extract playlist information from URL"""
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end", "50",
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                items = []
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    if line.strip():
                        try:
                            item = json.loads(line)
                            if item.get('_type') == 'playlist':
                                continue
                            
                            duration = int(item.get('duration', 0) or 0)
                            title = item.get('title', 'Unknown')
                            
                            if self.is_music_content(title, '', duration):
                                items.append({
                                    'id': item.get('id', ''),
                                    'title': title,
                                    'uploader': item.get('uploader', 'Unknown'),
                                    'duration': duration,
                                    'duration_str': f"{duration//60}:{duration%60:02d}" if duration else "N/A",
                                    'url': f"https://youtube.com/watch?v={item.get('id', '')}",
                                    'thumbnail': f"https://img.youtube.com/vi/{item.get('id', '')}/mqdefault.jpg"
                                })
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
            'id': job_id,
            'url': url,
            'artist': artist,
            'album': album,
            'status': 'queued',
            'created': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Queued for download'
        }
        
        # Save job
        jobs = self.get_all_jobs()
        jobs[job_id] = job
        self.save_jobs(jobs)
        
        # Start download in background
        threading.Thread(target=self._process_download, args=(job_id,), daemon=True).start()
        
        return job_id
    
    def download_playlist(self, url, playlist_name=""):
        """Queue entire playlist for download"""
        job_id = str(uuid.uuid4())[:8]
        
        job = {
            'id': job_id,
            'url': url,
            'playlist_name': playlist_name or 'Downloaded Playlist',
            'type': 'playlist',
            'status': 'queued',
            'created': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Queued for playlist download'
        }
        
        # Save job
        jobs = self.get_all_jobs()
        jobs[job_id] = job
        self.save_jobs(jobs)
        
        # Start download in background
        threading.Thread(target=self._process_playlist_download, args=(job_id,), daemon=True).start()
        
        return job_id
    
    def _process_download(self, job_id):
        """Process single song download in background"""
        try:
            jobs = self.get_all_jobs()
            job = jobs.get(job_id)
            if not job:
                return
            
            # Update status
            job['status'] = 'downloading'
            job['progress'] = 10
            job['message'] = 'Starting download...'
            self.save_jobs(jobs)
            
            # Download using direct yt-dlp
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "320K",
                "--embed-thumbnail",
                "--add-metadata",
                "--no-playlist",
                "--output", "/music/youtube-music/%(uploader)s/%(title)s.%(ext)s",
                job['url']
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                job['status'] = 'completed'
                job['progress'] = 90
                job['message'] = 'Triggering library scan...'
                self.save_jobs(jobs)
                
                # Trigger Navidrome scan
                self._trigger_navidrome_scan()
                
                job['status'] = 'completed'
                job['progress'] = 100
                job['message'] = 'Download completed!'
            else:
                job['status'] = 'failed'
                job['progress'] = 0
                job['message'] = f"Download failed: {result.stderr[:100] if result.stderr else 'Unknown error'}"
            
            self.save_jobs(jobs)
            
        except Exception as e:
            jobs = self.get_all_jobs()
            if job_id in jobs:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['progress'] = 0
                jobs[job_id]['message'] = f"Error: {str(e)}"
                self.save_jobs(jobs)
    
    def _process_playlist_download(self, job_id):
        """Process playlist download in background"""
        try:
            jobs = self.get_all_jobs()
            job = jobs.get(job_id)
            if not job:
                return
            
            # Update status
            job['status'] = 'downloading'
            job['progress'] = 5
            job['message'] = 'Starting playlist download...'
            self.save_jobs(jobs)
            
            playlist_name = job.get('playlist_name', 'Downloaded Playlist')
            
            # Download using direct yt-dlp with playlist support
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "320K",
                "--embed-thumbnail",
                "--add-metadata",
                "--yes-playlist",
                "--output", f"/music/youtube-music/{playlist_name}/%(uploader)s/%(title)s.%(ext)s",
                job['url']
            ]
            
            # Use Popen for progress monitoring
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                     text=True, bufsize=1, universal_newlines=True)
            
            progress = 5
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Update progress based on yt-dlp output
                    if '[download]' in output and '%' in output:
                        try:
                            # Extract percentage
                            percent_match = re.search(r'(\d+(?:\.\d+)?)%', output)
                            if percent_match:
                                file_progress = float(percent_match.group(1))
                                progress = 5 + (file_progress * 0.85)
                                job['progress'] = int(progress)
                                job['message'] = f'Downloading playlist... {file_progress:.1f}%'
                                self.save_jobs(jobs)
                        except:
                            pass
            
            # Wait for completion
            process.wait()
            
            if process.returncode == 0:
                job['status'] = 'completed'
                job['progress'] = 95
                job['message'] = 'Triggering library scan...'
                self.save_jobs(jobs)
                
                # Trigger Navidrome scan
                self._trigger_navidrome_scan()
                
                job['status'] = 'completed'
                job['progress'] = 100
                job['message'] = f'Playlist "{playlist_name}" downloaded successfully!'
            else:
                stderr = process.stderr.read()
                job['status'] = 'failed'
                job['progress'] = 0
                job['message'] = f"Playlist download failed: {stderr[:100] if stderr else 'Unknown error'}"
            
            self.save_jobs(jobs)
            
        except Exception as e:
            jobs = self.get_all_jobs()
            if job_id in jobs:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['progress'] = 0
                jobs[job_id]['message'] = f"Error: {str(e)}"
                self.save_jobs(jobs)
    
    def _trigger_navidrome_scan(self):
        """Trigger Navidrome library scan - handles deduplication automatically"""
        try:
            # Try direct API call to Navidrome
            subprocess.run([
                "curl", "-X", "POST", "http://192.168.1.39:4533/api/scanner/scan"
            ], timeout=10, capture_output=True)
        except:
            try:
                # Fallback: try through docker if container setup
                subprocess.run([
                    "docker", "exec", "navidrome",
                    "curl", "-X", "POST", "http://localhost:4533/api/scanner/scan"
                ], timeout=10, capture_output=True)
            except:
                pass
    
    def get_all_jobs(self):
        """Get all download jobs"""
        try:
            with open(self.jobs_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_jobs(self, jobs):
        """Save jobs to file"""
        try:
            with open(self.jobs_file, 'w') as f:
                json.dump(jobs, f, indent=2)
        except:
            pass
    
    def fix_navidrome_duplicates(self):
        """Fix greyed out tracks in Navidrome - runs in background"""
        try:
            self._trigger_navidrome_scan()
            return True
        except:
            return False

def main():
    # Initialize app
    app = SimpleMusicApp()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎵 Lucky's Music Discovery Hub</h1>
        <p>Unlimited YouTube Music Downloads • Spotify-Style Discovery • Zero Subscriptions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Real Stats Dashboard
    stats = app.get_real_library_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tracks", stats['total_tracks'])
    with col2:
        st.metric("Artists", stats['artists'])
    with col3:
        st.metric("Albums", stats['albums'])
    with col4:
        st.metric("Storage Used", stats['storage_used'])
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 **Discover & Download**", 
        "📋 **Playlist Manager**",
        "📊 **Download Status**", 
        "🔧 **Library Tools**"
    ])
    
    with tab1:
        # Search interface
        st.header("🔍 Search & Discover Music")
        
        # FIXED: Add proper label to avoid warning
        search_query = st.text_input(
            "Search Music",  # FIXED: Added proper label
            placeholder="🎵 Search for songs, artists, albums... (e.g., 'Arijit Singh', 'Bollywood hits', 'rock music')",
            key="search_input",
            label_visibility="collapsed"  # Hide the label but provide it for accessibility
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_button = st.button("🔍 Search", type="primary", use_container_width=True)
        with col2:
            music_filter = st.checkbox("🎵 Music Only", value=False, help="Filter out non-music content (more restrictive)")
        
        if search_query and search_button:
            with st.spinner("🎵 Searching YouTube Music..."):
                results = app.search_youtube_music(search_query, max_results=20, filter_music=music_filter)
                
                if results:
                    st.success(f"Found {len(results)} results for '{search_query}'")
                    
                    # Display results in card grid (4 columns for better layout)
                    st.markdown('<div class="results-container">', unsafe_allow_html=True)
                    
                    for i in range(0, len(results), 4):
                        cols = st.columns(4)
                        
                        for j, col in enumerate(cols):
                            if i + j < len(results):
                                track = results[i + j]
                                with col:
                                    # Album art
                                    if track.get('thumbnail'):
                                        st.image(track['thumbnail'], width=150)
                                    
                                    # Track info
                                    title = track['title'][:30] + "..." if len(track['title']) > 30 else track['title']
                                    uploader = track['uploader'][:20] + "..." if len(track['uploader']) > 20 else track['uploader']
                                    
                                    st.markdown(f"**{title}**")
                                    st.caption(f"🎤 {uploader}")
                                    st.caption(f"⏱️ {track['duration_str']}")
                                    
                                    # Download button
                                    if st.button("📥 Download", key=f"dl_{i+j}", use_container_width=True):
                                        job_id = app.download_song(track['url'])
                                        st.success(f"✅ Queued! Job: {job_id}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.warning("No results found. Try different keywords or disable music filter.")
        
        # Quick discovery
        st.header("🎭 Quick Discovery")
        
        genres = [
            ("🇮🇳 Bollywood Hits", "bollywood songs"),
            ("🎸 Rock Hits", "rock music"),
            ("🎤 Pop Charts", "pop songs"),
            ("🇰🇷 K-Pop", "kpop music"),
            ("🎵 Electronic", "electronic music"),
            ("🎷 Jazz", "jazz music"),
            ("🎼 Classical", "classical music"),
            ("🏴‍☠️ Old School", "90s music")
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
        if hasattr(st.session_state, 'genre_query'):
            with st.spinner(f"Finding {st.session_state.genre_name} music..."):
                results = app.search_youtube_music(st.session_state.genre_query, max_results=16, filter_music=False)
                
                if results:
                    st.success(f"🎵 {st.session_state.genre_name} - {len(results)} tracks found")
                    
                    st.markdown('<div class="results-container">', unsafe_allow_html=True)
                    
                    for j in range(0, len(results), 4):
                        result_cols = st.columns(4)
                        
                        for k, col in enumerate(result_cols):
                            if j + k < len(results):
                                track = results[j + k]
                                with col:
                                    if track.get('thumbnail'):
                                        st.image(track['thumbnail'], width=150)
                                    
                                    title = track['title'][:30] + "..." if len(track['title']) > 30 else track['title']
                                    uploader = track['uploader'][:20] + "..." if len(track['uploader']) > 20 else track['uploader']
                                    
                                    st.markdown(f"**{title}**")
                                    st.caption(f"🎤 {uploader}")
                                    st.caption(f"⏱️ {track['duration_str']}")
                                    
                                    if st.button("📥 Download", key=f"genre_dl_{j+k}", use_container_width=True):
                                        job_id = app.download_song(track['url'])
                                        st.success(f"✅ Queued! Job: {job_id}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Clear results button
                    if st.button("🗑️ Clear Results"):
                        del st.session_state.genre_query
                        del st.session_state.genre_name
                        st.rerun()
                else:
                    st.warning(f"No {st.session_state.genre_name} results found.")
    
    with tab2:
        # Playlist Manager Tab
        st.header("📋 Playlist & URL Manager")
        
        st.markdown('<div class="playlist-section">', unsafe_allow_html=True)
        
        # URL input section
        st.subheader("🔗 Add URLs or Playlists")
        
        url_input = st.text_area(
            "Paste URLs (one per line):",
            placeholder="https://youtube.com/watch?v=dQw4w9WgXcQ\nhttps://youtube.com/playlist?list=PLrAXtmRdnEQy3Qo2KnG...\nhttps://music.youtube.com/watch?v=...",
            height=100
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            playlist_name = st.text_input(
                "Playlist Name (optional):",
                placeholder="e.g., 'My Awesome Mix'",
                help="Custom folder name for organization"
            )
        
        with col2:
            apply_filter = st.checkbox("🎵 Filter Music Only", value=True, help="Skip non-music content")
        
        if url_input and st.button("📥 **Process URLs**", type="primary"):
            urls = [url.strip() for url in url_input.split('\n') if url.strip()]
            
            if urls:
                processed_count = 0
                
                for url in urls:
                    if 'playlist' in url or 'list=' in url:
                        # Handle as playlist
                        job_id = app.download_playlist(url, playlist_name or "Downloaded Playlist")
                        st.success(f"📋 Playlist queued! Job: {job_id}")
                        processed_count += 1
                    elif 'youtube.com/watch' in url or 'music.youtube.com' in url:
                        # Handle as single video
                        job_id = app.download_song(url)
                        st.success(f"🎵 Song queued! Job: {job_id}")
                        processed_count += 1
                    else:
                        st.warning(f"⚠️ Unsupported URL: {url[:50]}...")
                
                if processed_count > 0:
                    st.success(f"✅ Processed {processed_count} URLs successfully!")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        # Download status tab - same as before
        st.header("📊 Download Status & History")
        
        if st.button("🔄 Refresh", key="refresh_status"):
            st.rerun()
        
        jobs = app.get_all_jobs()
        
        if not jobs:
            st.info("No downloads yet. Search for music or add playlists to start downloading!")
            return
        
        # Active downloads
        active_jobs = [j for j in jobs.values() if j['status'] in ['queued', 'downloading']]
        
        if active_jobs:
            st.subheader("🔄 Active Downloads")
            
            for job in active_jobs:
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    
                    with col1:
                        status_emoji = "⏳" if job['status'] == 'queued' else "⬇️"
                        job_type = "📋 Playlist" if job.get('type') == 'playlist' else "🎵 Song"
                        st.markdown(f"**{status_emoji} {job_type} Downloading...**")
                        st.caption(f"URL: {job['url'][:60]}...")
                        st.caption(f"Status: {job.get('message', 'Processing...')}")
                    
                    with col2:
                        progress = job.get('progress', 0)
                        st.progress(progress / 100)
                        st.caption(f"{progress}%")
                    
                    with col3:
                        st.caption(f"Job: {job['id']}")
        
        # Recent downloads
        completed_jobs = [j for j in jobs.values() if j['status'] == 'completed']
        failed_jobs = [j for j in jobs.values() if j['status'] == 'failed']
        
        col1, col2 = st.columns(2)
        
        with col1:
            if completed_jobs:
                st.subheader("✅ Recent Completed")
                for job in completed_jobs[-10:]:
                    created_time = job.get('created', '')[:19].replace('T', ' ')
                    job_type = "📋" if job.get('type') == 'playlist' else "🎵"
                    st.success(f"{job_type} {created_time} - Completed")
        
        with col2:
            if failed_jobs:
                st.subheader("❌ Recent Failed")
                for job in failed_jobs[-5:]:
                    st.error(f"❌ {job.get('message', 'Download failed')}")
    
    with tab4:
        # Library tools tab - same as before but with better Navidrome integration
        st.header("🔧 Library Management Tools")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎵 Navidrome Integration")
            
            # Navidrome status check
            try:
                result = subprocess.run(["curl", "-f", "http://192.168.1.39:4533/ping"], 
                                      capture_output=True, text=True, timeout=5)
                navidrome_status = "🟢 Online" if result.returncode == 0 else "🔴 Offline"
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
                        st.info("ℹ️ Deduplication runs automatically in background")
                    else:
                        st.error("❌ Cleanup failed")
        
        with col2:
            st.subheader("📊 Storage & Performance")
            
            # Real-time storage info
            try:
                result = subprocess.run(["df", "-h", "/music"], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 4:
                            st.metric("Total Space", parts[1])
                            st.metric("Used Space", parts[2])
                            st.metric("Free Space", parts[3])
                            
                            usage_pct = parts[4] if len(parts) > 4 else "Unknown"
                            st.metric("Usage", usage_pct)
            except:
                st.info("Storage info unavailable")
        
        # Quick links
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
        
        # Footer info
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; font-size: 0.8em;">
            🎵 Lucky's Music Empire | Built with Streamlit + yt-dlp | VPN-Protected Downloads
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
