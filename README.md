# 🎵 Lucky's Music Discovery Hub

A modern, Spotify-inspired web interface for YouTube Music search, download automation, and Spotify library sync - integrated with your homelab media server.

## **🎯 What It Does**

**Search** → **Download** → **Auto-Organize** → **Stream via Navidrome**  
**Spotify Sync** → **Bulk Download** → **AI Organization** → **Zero Subscriptions**

- **YouTube Music search** with intelligent content filtering
- **Spotify integration** for syncing your entire music library
- **One-click downloads** with instant feedback and background processing
- **Smart auto-organization** by artist/album structure with metadata
- **Real-time library statistics** from your actual music collection
- **Navidrome integration** for immediate streaming access

## **✨ Current Features**

### **🔍 Discovery & Search**

- YouTube Music search with advanced music content filtering
- 8-column grid layout for optimal browsing experience
- Quick genre discovery (Bollywood, Punjabi, Hip Hop, EDM, etc.)
- Album artwork and comprehensive track metadata display
- Instant download feedback with progress tracking

### **🎵 Spotify Integration**

- **OAuth authentication** for secure Spotify account access
- **Sync your liked tracks** - automatically download all saved songs
- **Sync playlists** - bulk download entire playlists with one click
- **Search Spotify catalog** and download via YouTube
- **Complete library sync** - import your entire Spotify collection

### **📥 Download Management**

- Single song and playlist URL processing
- 320kbps MP3 with embedded thumbnails and metadata
- Instant download queue with real-time progress tracking
- Background job management with retry capabilities
- Automatic Navidrome library scanning after downloads

### **📊 Library Management**

- Live statistics from your actual music collection
- Storage usage monitoring with ZFS integration
- Navidrome database cleanup and optimization tools
- Intelligent duplicate track management
- Library import tools for existing collections

## **🗂️ Folder Structure**

```

/music/
├── library/              # Your existing music collection (imported)
├── youtube-music/        # New downloads (auto-organized)
│   ├── Artist Name/
│   │   └── Album Name/
│   │       ├── 01 - Song.mp3
│   │       ├── 02 - Song.mp3
│   │       └── cover.jpg
├── spotify-sync/         # Spotify synchronized tracks
│   ├── Liked Songs/
│   └── Playlists/
│       ├── Playlist Name/
│       └── Another Playlist/
└── playlists/           # M3U playlists and collections

```

## **🚀 Quick Deploy**

### **Prerequisites**

- Container 104 with Docker running
- Navidrome configured and accessible at `192.168.1.39:4533`
- ZFS music storage mounted at `/music`
- Spotify Developer App (for Spotify sync features)

### **Installation**

``` bash
# Navigate to your Docker data directory
pct enter 104
cd /mnt/docker-data
git clone  music-discovery-hub
cd music-discovery-hub

# Build and deploy the stack
docker compose up --build -d

# Verify deployment
docker ps | grep music-discovery
```

### **External Access**

- **Music Discovery UI**: `https://music-discovery.luckyverma.com`
- **Navidrome Player**: `https://music.luckyverma.com`

### **Spotify Setup**

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create new app with redirect URI: `https://music-discovery.luckyverma.com`
3. Copy Client ID and Client Secret
4. Enter credentials in the Spotify Sync tab
5. Complete OAuth flow to access your library

## **📱 How to Use**

### **🔍 Search & Download**

1. **Search** for artists, songs, or albums using the enhanced search
2. **Browse genres** with curated quick discovery buttons
3. **Click download** - get instant feedback with background processing
4. **Monitor progress** in the Download Status tab
5. **Stream immediately** via Navidrome once complete

### **🎵 Spotify Library Sync**

1. **Connect Spotify** using OAuth in the Spotify Sync tab
2. **Sync Liked Songs** - download all your saved tracks automatically
3. **Sync Playlists** - select and download entire playlists
4. **Monitor progress** - watch as your entire library downloads
5. **Access instantly** - stream via Navidrome as downloads complete

### **📋 Playlist Management**

1. **Paste URLs** (YouTube/YouTube Music playlists)
2. **Preview content** before downloading with metadata
3. **Bulk download** entire playlists with progress tracking
4. **Custom organization** with playlist naming options

### **📊 Library Monitoring**

- **Real-time stats** show actual track/artist/album counts
- **Storage monitoring** displays ZFS usage and performance
- **Download history** tracks all completed jobs with details
- **Health monitoring** for Navidrome integration

## **🎵 Current Status**

| Component | Status | Details |
|-----------|--------|---------|
| **YouTube Search** | ✅ Complete | Advanced filtering, 8-column layout |
| **Spotify OAuth** | ✅ Complete | Full library access and sync |
| **Downloads** | ✅ Complete | Direct yt-dlp with instant feedback |
| **Organization** | ✅ Complete | Smart artist/album/track structure |
| **Library Stats** | ✅ Complete | Real-time from `/music` with ZFS |
| **Background Jobs** | ✅ Complete | Advanced queue with retry logic |
| **Navidrome Sync** | ✅ Complete | Auto-scan with duplicate handling |
| **UI/UX** | ✅ Complete | Spotify-inspired dark theme, 8-column grid |

## **🔧 Technical Stack**

### **Frontend**

- **Streamlit** with custom Spotify-inspired dark theme
- **8-column responsive grid** for optimal track browsing
- **Instant feedback** with session state management
- **Progressive enhancement** with smooth animations

### **Backend Services**

- **yt-dlp** direct integration for YouTube downloads
- **Spotify Web API** with OAuth 2.0 authentication
- **Background job manager** with retry and progress tracking
- **Navidrome API** integration for library management

### **Audio Quality & Metadata**

- **320kbps MP3** with embedded artwork and metadata
- **Automatic tagging** with artist, album, and track information
- **Thumbnail embedding** for visual library browsing
- **Smart filename sanitization** for cross-platform compatibility

### **Storage Integration**

``` bash
# ZFS Pool Allocation
data/media/music              2.57G  # Base music storage
data/media/music/library      96K    # Imported existing collection
data/media/music/youtube-music 96K   # YouTube downloads
data/media/music/spotify-sync 96K    # Spotify synchronized content
data/media/music/playlists    96K    # Playlists and collections
```

## **📂 Library Import**

For importing your existing unorganized music collection, use the included import script:

``` bash
# Run the music import script
python3 music_import_tool.py --source /path/to/hdd --target /music/library --organize
```

See `music_import_tool.py` for detailed import options and network setup.

## **🔗 Ecosystem Integration**

- **Navidrome**: `https://music.luckyverma.com` (streaming)
- **qBittorrent**: `https://qbittorrent.luckyverma.com` (VPN-protected torrents)
- **Jellyfin**: `https://jellyfin.luckyverma.com` (4K media streaming)
- **Immich**: `https://immich.luckyverma.com` (AI photo management)

## **🎯 Features Roadmap**

### **Phase 1: Core Functionality** ✅ **COMPLETE**

- YouTube Music search and download
- Spotify OAuth and library sync
- Background job management
- Navidrome integration

### **Phase 2: Enhanced Organization** 🔄 **IN PROGRESS**

- Advanced metadata extraction and cleanup
- Duplicate detection and removal
- Album art enhancement and standardization
- Automatic playlist generation

### **Phase 3: AI & Automation** 📋 **PLANNED**

- AI-powered music recommendation
- Automatic genre classification
- Smart playlist creation based on listening habits
- Integration with Last.fm for scrobbling

### **Phase 4: Advanced Features** 📋 **PLANNED**

- Multi-user support with separate libraries
- Advanced search with natural language queries
- Integration with other streaming services
- Mobile app companion

## **🛠️ Development**

### **Contributing**

- Fork the repository
- Create feature branch
- Submit pull request with detailed description

### **Local Development**

``` bash
# Install dependencies
pip install -r requirements.txt

# Run development server
streamlit run app.py --server.port 8501
```

### **Container Development**

``` bash
# Build and test locally
docker build -t music-discovery-hub .
docker run -p 8501:8501 -v /music:/music music-discovery-hub
```

## **📝 Configuration**

### **Environment Variables**

- `TZ`: Timezone (default: America/Chicago)
- `SPOTIFY_CLIENT_ID`: Spotify application client ID
- `SPOTIFY_CLIENT_SECRET`: Spotify application client secret

### **Volume Mounts**

- `/music`: Music library storage (ZFS recommended)
- `/config`: Application configuration and job data
- `/var/run/docker.sock`: Docker socket for container management

## **🎵 Goals Achieved**

✅ **Zero music subscriptions** - Download unlimited music for free  
✅ **Complete ownership** - All music stored locally with metadata  
✅ **Global streaming** - Access your library from anywhere via HTTPS  
✅ **Spotify integration** - Sync your entire Spotify library automatically  
✅ **Enterprise quality** - GPU-accelerated transcoding, VPN protection  
✅ **Seamless experience** - Search, download, stream in one interface  

**🏆 Result**: The ultimate personal music empire with complete privacy, unlimited content, and professional-grade streaming capabilities.

---

*Part of Lucky's Homelab - Container 104*
