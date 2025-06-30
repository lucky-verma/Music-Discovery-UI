"""
Utility Functions

This package contains utility functions and classes:
- Configuration management
- Audio file utilities
- Deduplication tools
"""

from .config import Config
from .dedup_utils import MusicDeduplicator

__all__ = ['Config', 'MusicDeduplicator']
