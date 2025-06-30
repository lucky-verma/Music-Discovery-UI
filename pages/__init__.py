"""
Application Pages

This package contains individual page modules:
- Discovery page with Spotify integration
- Import and management page
- Individual page components
"""

from .discovery import render_discovery_page
from .import_page import render_import_page

__all__ = ["render_discovery_page", "render_import_page"]
