"""
Music Discovery Services

This package contains all external service integrations:
- Spotify API service
- YouTube/yt-dlp service  
- Background job management
"""

from .spotify_service import SpotifyService
from .youtube_service import YouTubeService
from .job_service import JobManager

__all__ = ['SpotifyService', 'YouTubeService', 'JobManager']
