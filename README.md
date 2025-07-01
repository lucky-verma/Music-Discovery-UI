# 🎵 Music Discovery Hub

A modern, Spotify-inspired web interface for YouTube Music search and download automation, integrated with your homelab media server.

## **🎯 What It Does**

**Search** → **Download** → **Auto-Organize** → **Stream via Navidrome**

- **YouTube Music search** with album art and metadata
- **One-click downloads** with background processing  
- **Auto-organization** by artist/album structure
- **Real-time library statistics** from your music collection
- **Navidrome integration** for immediate streaming access

## **✨ Current Features**

### **🔍 Discovery & Search**

- YouTube Music search with music content filtering
- Quick genre discovery (Bollywood, K-Pop, Rock, etc.)
- Album artwork and track metadata display
- Background download queue with progress tracking

### **📥 Download Management**

- Single song and playlist URL processing
- 320kbps MP3 with embedded thumbnails and metadata
- Real-time download status and history
- Automatic Navidrome library scanning

### **📊 Library Management**

- Live statistics from your actual music collection
- Storage usage monitoring
- Navidrome database cleanup tools
- Duplicate track management (automatic)

## **🗂️ Folder Structure**

``` bash
/music/
├── library/              # Your existing 20k tracks (to be organized)
├── youtube-music/        # New downloads (auto-organized)
│   ├── Artist Name/
│   │   └── Album Name/
│   │       ├── 01 - Song.mp3
│   │       ├── 02 - Song.mp3
│   │       └── cover.jpg
└── playlists/           # M3U playlists (future use)
```

## **🚀 Quick Deploy**

### **Prerequisites**

- Container 104 with Docker running
- Navidrome configured and accessible
- ZFS music storage mounted at `/music`

### **Installation**

```bash
# Navigate to your Docker data directory
pct enter 104
cd /mnt/docker-data/navidrome-music-system
mkdir -p music-discovery-ui && cd music-discovery-ui

# Create the app files (copy from your working version)
# app.py, requirements.txt, Dockerfile, docker-compose.yml

# Deploy the stack
docker compose up --build -d
```

### **Access**

- **External**: `https://music-download.luckyverma.com`

## **📱 How to Use**

### **Search & Download**

1. **Search** for artists, songs, or albums
2. **Browse genres** with quick discovery buttons
3. **Click download** - files process in background
4. **Stream immediately** via Navidrome once complete

### **Playlist Management**

1. **Paste URLs** (YouTube/YouTube Music playlists)
2. **Preview content** before downloading
3. **Bulk download** entire playlists with one click

### **Library Monitoring**

- **Real stats** show actual track/artist/album counts
- **Storage monitoring** displays usage from ZFS
- **Download history** tracks all completed jobs

## **🎵 Current Status**

| Component | Status | Details |
|-----------|--------|---------|
| **Search** | ✅ Working | YouTube Music integration |
| **Downloads** | ✅ Working | yt-dlp with 320kbps MP3 |
| **Organization** | ✅ Working | Auto artist/album folders |
| **Library Stats** | ✅ Working | Real-time from `/music` |
| **Background Jobs** | ✅ Working | Queue with progress tracking |
| **Navidrome Sync** | ✅ Working | Auto-scan after downloads |

## **🔧 Technical Details**

### **Stack**

- **Frontend**: Streamlit with Spotify-like dark theme
- **Download Engine**: yt-dlp (direct integration)
- **Audio Quality**: 320kbps MP3 + embedded artwork
- **Organization**: Automatic artist/album/track structure
- **Integration**: Navidrome API for library scanning

### **Storage Integration**

```bash
# Current ZFS allocation
data/media/music              2.57G  # Base music storage
data/media/music/library      96K    # Your 20k tracks (to migrate)
data/media/music/youtube-music 96K   # New downloads
data/media/music/playlists    96K    # Future playlist storage
```

## **🎧 Next Steps**

1. **Deploy the app** using the instructions above
2. **Test downloads** with a few songs
3. **Import your 20k tracks** to `/music/library/`
4. **Access via Navidrome** at `https://music.luckyverma.com`

## **🔗 Ecosystem Integration**

- **Navidrome**: `https://music.luckyverma.com` (streaming)
- **qBittorrent**: `https://qbittorrent.luckyverma.com` (torrents)  
- **Jellyfin**: `https://jellyfin.luckyverma.com` (media server)

**🎯 Goal**: Zero music subscriptions, unlimited downloads, complete ownership, seamless streaming from anywhere.

*Part of Lucky's Homelab - Container 104*
