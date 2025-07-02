#!/usr/bin/env python3
"""
Batch update existing music library with enhanced metadata and album art
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict
import streamlit as st
from services.metadata_service import MetadataService
from services.lyrics_service import LyricsManager
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
import requests


class BatchMetadataUpdater:
    def __init__(self):
        self.metadata_service = MetadataService()
        self.lyrics_manager = LyricsManager()
        self.music_path = Path("/music/library")
        self.processed_count = 0
        self.enhanced_count = 0

    def find_music_files(self) -> List[Path]:
        """Find all music files in library"""
        audio_extensions = {".mp3", ".m4a", ".flac", ".wav"}
        music_files = []

        for ext in audio_extensions:
            music_files.extend(self.music_path.rglob(f"*{ext}"))

        return music_files

    def extract_metadata_from_path(self, file_path: Path) -> Dict[str, str]:
        """Extract artist/track from file path structure"""
        parts = file_path.parts

        # Common structure: /music/library/Artist/Album/Track.mp3
        if len(parts) >= 4:
            artist = parts[-3]  # Artist folder
            track = file_path.stem  # Filename without extension
            album = parts[-2] if len(parts) >= 4 else ""

            # Clean track name (remove track numbers)
            import re

            track = re.sub(r"^\d+[\s\-\.]*", "", track).strip()

            return {"artist": artist, "track": track, "album": album}

        return {"artist": "Unknown", "track": file_path.stem, "album": ""}

    def update_file_metadata(self, file_path: Path, metadata: Dict) -> bool:
        """Update file with enhanced metadata and album art"""
        try:
            # Extract current metadata
            file_meta = self.extract_metadata_from_path(file_path)

            # Get enhanced metadata
            enhanced = self.metadata_service.get_enhanced_metadata(
                file_meta["artist"], file_meta["track"], file_meta["album"]
            )

            if not enhanced or not enhanced.get("album_art_urls"):
                return False

            # Download album art
            album_art_url = enhanced["album_art_urls"][0]
            art_data = self.download_album_art(album_art_url)

            if art_data:
                # Update MP3 file with album art
                self.embed_album_art(file_path, art_data)

                # Save lyrics if available
                if enhanced.get("lyrics"):
                    lyrics_file = file_path.parent / f"{file_path.stem}.lrc"
                    with open(lyrics_file, "w", encoding="utf-8") as f:
                        f.write(enhanced["lyrics"])

                return True

        except Exception as e:
            print(f"Error updating {file_path}: {e}")

        return False

    def download_album_art(self, url: str) -> bytes:
        """Download album art image"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.content
        except:
            pass
        return None

    def embed_album_art(self, file_path: Path, art_data: bytes):
        """Embed album art into MP3 file"""
        try:
            audio = ID3(str(file_path))
        except ID3NoHeaderError:
            audio = ID3()

        # Remove existing album art
        audio.delall("APIC")

        # Add new album art
        audio.add(
            APIC(
                encoding=3,  # UTF-8
                mime="image/jpeg",
                type=3,  # Cover (front)
                desc="Cover",
                data=art_data,
            )
        )

        audio.save(str(file_path))

    def batch_update_library(self, max_files: int = 100):
        """Update library metadata in batches"""
        music_files = self.find_music_files()

        print(f"Found {len(music_files)} music files")
        print(f"Processing first {min(max_files, len(music_files))} files...")

        for i, file_path in enumerate(music_files[:max_files]):
            print(f"Processing {i+1}/{max_files}: {file_path.name}")

            if self.update_file_metadata(file_path):
                self.enhanced_count += 1
                print(f"  ✅ Enhanced with album art")
            else:
                print(f"  ⚠️ No enhancement available")

            self.processed_count += 1

            # Rate limiting to avoid API abuse
            time.sleep(2)

            if i % 10 == 9:
                print(f"\nProgress: {i+1}/{max_files} files processed")
                print(f"Enhanced: {self.enhanced_count} files")

        print(f"\n🎉 Batch update complete!")
        print(f"Files processed: {self.processed_count}")
        print(f"Files enhanced: {self.enhanced_count}")


if __name__ == "__main__":
    updater = BatchMetadataUpdater()

    # Start with 50 files as test
    updater.batch_update_library(max_files=50)
