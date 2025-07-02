#!/usr/bin/env python3
"""
Music Library Import Tool
Intelligently imports and organizes unstructured music collections

Usage:
    python3 music_import_tool.py --source /path/to/source --target /music/library

Features:
    - Network drive support (Windows SMB shares)
    - Metadata extraction and organization
    - Duplicate detection and handling
    - Progress tracking with detailed logging
    - Dry-run mode for testing
    - Resume capability for interrupted imports
"""

import os
import sys
import shutil
import argparse
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import logging
from datetime import datetime
import re

# Optional imports with fallbacks
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("Warning: mutagen not available. Install with: pip install mutagen")

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class MusicImporter:
    """Advanced music library importer with intelligent organization"""

    def __init__(self, source_path: str, target_path: str, options: Dict):
        self.source_path = Path(source_path)
        self.target_path = Path(target_path)
        self.options = options

        # Supported audio formats
        self.audio_extensions = {
            ".mp3",
            ".m4a",
            ".flac",
            ".wav",
            ".aac",
            ".ogg",
            ".wma",
            ".opus",
            ".aiff",
            ".ape",
            ".dsf",
            ".dff",
        }

        # Statistics tracking
        self.stats = {
            "files_found": 0,
            "files_processed": 0,
            "files_copied": 0,
            "files_skipped": 0,
            "duplicates_found": 0,
            "errors": 0,
            "total_size": 0,
            "start_time": datetime.now(),
        }

        # Track processed files to avoid duplicates
        self.processed_hashes: Set[str] = set()
        self.processed_files: Dict[str, str] = {}

        # Resume support
        self.progress_file = self.target_path / ".import_progress.json"
        self.load_progress()

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Setup comprehensive logging"""
        log_file = (
            self.target_path / f'import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger(__name__)

    def load_progress(self):
        """Load previous import progress for resume capability"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, "r") as f:
                    progress_data = json.load(f)
                    self.processed_hashes = set(
                        progress_data.get("processed_hashes", [])
                    )
                    self.processed_files = progress_data.get("processed_files", {})
                    self.logger.info(
                        f"Resumed: {len(self.processed_hashes)} files already processed"
                    )
            except Exception as e:
                self.logger.warning(f"Could not load progress file: {e}")

    def save_progress(self):
        """Save current progress for resume capability"""
        try:
            progress_data = {
                "processed_hashes": list(self.processed_hashes),
                "processed_files": self.processed_files,
                "stats": self.stats,
            }
            with open(self.progress_file, "w") as f:
                json.dump(progress_data, f, default=str, indent=2)
        except Exception as e:
            self.logger.warning(f"Could not save progress: {e}")

    def get_file_hash(self, file_path: Path) -> str:
        """Generate hash for duplicate detection"""
        try:
            # Use first 64KB + last 64KB + file size for speed
            hash_md5 = hashlib.md5()

            with open(file_path, "rb") as f:
                # First chunk
                chunk = f.read(65536)
                if chunk:
                    hash_md5.update(chunk)

                # File size
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                hash_md5.update(str(file_size).encode())

                # Last chunk (if file is large enough)
                if file_size > 131072:  # 128KB
                    f.seek(-65536, 2)  # Seek to 64KB from end
                    chunk = f.read()
                    hash_md5.update(chunk)

            return hash_md5.hexdigest()

        except Exception as e:
            self.logger.warning(f"Could not hash {file_path}: {e}")
            return str(file_path.stat().st_size)  # Fallback to file size

    def extract_metadata(self, file_path: Path) -> Dict[str, str]:
        """Extract metadata from audio file"""
        metadata = {
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "title": file_path.stem,
            "year": "",
            "genre": "",
            "track_number": "",
            "album_artist": "",
        }

        if not MUTAGEN_AVAILABLE:
            return self.extract_metadata_from_path(file_path, metadata)

        try:
            audio_file = MutagenFile(file_path)
            if audio_file is None:
                return self.extract_metadata_from_path(file_path, metadata)

            # Common tag mappings across formats
            tag_mappings = {
                "artist": ["TPE1", "ARTIST", "\xa9ART", "artist"],
                "album": ["TALB", "ALBUM", "\xa9alb", "album"],
                "title": ["TIT2", "TITLE", "\xa9nam", "title"],
                "year": ["TDRC", "DATE", "\xa9day", "date"],
                "genre": ["TCON", "GENRE", "\xa9gen", "genre"],
                "track_number": ["TRCK", "TRACKNUMBER", "trkn", "tracknumber"],
                "album_artist": ["TPE2", "ALBUMARTIST", "aART", "albumartist"],
            }

            for field, possible_tags in tag_mappings.items():
                for tag in possible_tags:
                    if tag in audio_file:
                        value = audio_file[tag]
                        if isinstance(value, list) and value:
                            value = value[0]
                        if value:
                            # Clean up the value
                            value = str(value).strip()
                            if "/" in value and field == "track_number":
                                value = value.split("/")[0]  # Take track number only
                            metadata[field] = value
                            break

        except (ID3NoHeaderError, Exception) as e:
            self.logger.debug(f"Could not read metadata from {file_path}: {e}")
            return self.extract_metadata_from_path(file_path, metadata)

        # Fallback to path-based extraction if metadata is sparse
        if (
            metadata["artist"] == "Unknown Artist"
            or metadata["album"] == "Unknown Album"
        ):
            metadata = self.extract_metadata_from_path(file_path, metadata)

        return metadata

    def extract_metadata_from_path(
        self, file_path: Path, base_metadata: Dict
    ) -> Dict[str, str]:
        """Extract metadata from file path structure"""
        parts = file_path.parts

        # Try to identify artist and album from path
        # Common patterns: /Artist/Album/Track.mp3 or /Music/Artist - Album/Track.mp3
        if len(parts) >= 3:
            # Check if second-to-last part looks like album (contains year or is structured)
            potential_album = parts[-2]
            potential_artist = parts[-3]

            # Parse "Artist - Album (Year)" pattern
            if " - " in potential_artist:
                artist_album = potential_artist.split(" - ", 1)
                if len(artist_album) == 2:
                    base_metadata["artist"] = self.clean_string(artist_album[0])
                    album_part = artist_album[1]

                    # Extract year from album
                    year_match = re.search(r"\((\d{4})\)", album_part)
                    if year_match:
                        base_metadata["year"] = year_match.group(1)
                        album_part = re.sub(r"\s*\(\d{4}\)", "", album_part)

                    base_metadata["album"] = self.clean_string(album_part)
            else:
                base_metadata["artist"] = self.clean_string(potential_artist)
                base_metadata["album"] = self.clean_string(potential_album)

        # Extract track number from filename
        filename = file_path.stem
        track_match = re.match(r"^(\d+)[\s\-\.]*(.+)", filename)
        if track_match:
            base_metadata["track_number"] = track_match.group(1).zfill(2)
            base_metadata["title"] = self.clean_string(track_match.group(2))
        else:
            base_metadata["title"] = self.clean_string(filename)

        return base_metadata

    def clean_string(self, text: str) -> str:
        """Clean and normalize text for filenames"""
        if not text:
            return "Unknown"

        # Remove common prefixes/suffixes
        text = re.sub(r"^(the\s+|a\s+)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*(feat\.?|ft\.?|featuring).*$", "", text, flags=re.IGNORECASE)

        # Replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            text = text.replace(char, "_")

        # Clean up whitespace
        text = " ".join(text.split())

        # Limit length
        if len(text) > 100:
            text = text[:100].rsplit(" ", 1)[0]

        return text.strip() or "Unknown"

    def create_organized_path(self, metadata: Dict, file_extension: str) -> Path:
        """Create organized file path based on metadata"""
        artist = metadata["artist"]
        album = metadata["album"]
        title = metadata["title"]
        track_num = metadata.get("track_number", "")

        # Create directory structure
        artist_dir = self.target_path / artist
        album_dir = artist_dir / album

        # Create filename
        if track_num:
            filename = f"{track_num} - {title}{file_extension}"
        else:
            filename = f"{title}{file_extension}"

        return album_dir / filename

    def scan_source(self) -> List[Path]:
        """Scan source directory for audio files"""
        self.logger.info(f"Scanning source directory: {self.source_path}")

        audio_files = []
        try:
            for file_path in self.source_path.rglob("*"):
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in self.audio_extensions
                ):
                    audio_files.append(file_path)
                    self.stats["total_size"] += file_path.stat().st_size

            self.stats["files_found"] = len(audio_files)
            self.logger.info(f"Found {len(audio_files)} audio files")

        except Exception as e:
            self.logger.error(f"Error scanning source directory: {e}")

        return audio_files

    def process_file(self, source_file: Path) -> bool:
        """Process a single audio file"""
        try:
            # Skip if already processed
            file_hash = self.get_file_hash(source_file)
            if file_hash in self.processed_hashes:
                self.stats["files_skipped"] += 1
                return True

            # Extract metadata
            metadata = self.extract_metadata(source_file)

            # Create target path
            target_file = self.create_organized_path(
                metadata, source_file.suffix.lower()
            )

            # Check if target already exists
            if target_file.exists():
                if self.options.get("skip_existing", True):
                    self.logger.debug(f"Skipping existing file: {target_file}")
                    self.stats["duplicates_found"] += 1
                    self.processed_hashes.add(file_hash)
                    return True
                elif self.options.get("overwrite", False):
                    self.logger.info(f"Overwriting existing file: {target_file}")
                else:
                    # Generate unique filename
                    counter = 1
                    base_path = target_file.parent / target_file.stem
                    ext = target_file.suffix
                    while target_file.exists():
                        target_file = (
                            base_path.parent / f"{base_path.name} ({counter}){ext}"
                        )
                        counter += 1

            # Create target directory
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            if not self.options.get("dry_run", False):
                if self.options.get("move_files", False):
                    shutil.move(str(source_file), str(target_file))
                    self.logger.info(f"Moved: {source_file} -> {target_file}")
                else:
                    shutil.copy2(str(source_file), str(target_file))
                    self.logger.info(f"Copied: {source_file} -> {target_file}")

                self.stats["files_copied"] += 1
            else:
                self.logger.info(
                    f"[DRY RUN] Would copy: {source_file} -> {target_file}"
                )

            # Track progress
            self.processed_hashes.add(file_hash)
            self.processed_files[str(source_file)] = str(target_file)
            self.stats["files_processed"] += 1

            return True

        except Exception as e:
            self.logger.error(f"Error processing {source_file}: {e}")
            self.stats["errors"] += 1
            return False

    def import_library(self):
        """Main import process"""
        self.logger.info("Starting music library import")
        self.logger.info(f"Source: {self.source_path}")
        self.logger.info(f"Target: {self.target_path}")
        self.logger.info(f"Options: {self.options}")

        # Create target directory
        self.target_path.mkdir(parents=True, exist_ok=True)

        # Scan for files
        audio_files = self.scan_source()
        if not audio_files:
            self.logger.warning("No audio files found to import")
            return

        # Process files
        for i, file_path in enumerate(audio_files, 1):
            self.logger.info(f"Processing {i}/{len(audio_files)}: {file_path.name}")

            success = self.process_file(file_path)

            # Save progress periodically
            if i % 10 == 0:
                self.save_progress()
                self.print_progress(i, len(audio_files))

        # Final progress save
        self.save_progress()
        self.print_final_stats()

    def print_progress(self, current: int, total: int):
        """Print current progress"""
        percent = (current / total) * 100
        elapsed = datetime.now() - self.stats["start_time"]
        rate = current / elapsed.total_seconds() if elapsed.total_seconds() > 0 else 0

        print(f"\nProgress: {current}/{total} ({percent:.1f}%) - {rate:.1f} files/sec")
        print(
            f"Processed: {self.stats['files_processed']}, "
            f"Copied: {self.stats['files_copied']}, "
            f"Skipped: {self.stats['files_skipped']}, "
            f"Errors: {self.stats['errors']}"
        )

    def print_final_stats(self):
        """Print final import statistics"""
        elapsed = datetime.now() - self.stats["start_time"]
        size_gb = self.stats["total_size"] / (1024**3)

        self.logger.info("\n" + "=" * 50)
        self.logger.info("IMPORT COMPLETED")
        self.logger.info("=" * 50)
        self.logger.info(f"Files found: {self.stats['files_found']}")
        self.logger.info(f"Files processed: {self.stats['files_processed']}")
        self.logger.info(f"Files copied: {self.stats['files_copied']}")
        self.logger.info(f"Files skipped: {self.stats['files_skipped']}")
        self.logger.info(f"Duplicates found: {self.stats['duplicates_found']}")
        self.logger.info(f"Errors: {self.stats['errors']}")
        self.logger.info(f"Total size: {size_gb:.2f} GB")
        self.logger.info(f"Time elapsed: {elapsed}")
        self.logger.info(
            f"Average speed: {self.stats['files_processed']/elapsed.total_seconds():.1f} files/sec"
        )

        if self.stats["errors"] == 0 and not self.options.get("dry_run"):
            # Clean up progress file on successful completion
            if self.progress_file.exists():
                self.progress_file.unlink()


def setup_network_mount():
    """Helper function to setup Windows SMB mount on Linux"""
    print("\nNetwork Mount Setup Helper")
    print("=" * 40)

    windows_ip = input("Enter Windows PC IP address: ")
    share_name = input("Enter share name (e.g., 'Music' or 'C$'): ")
    username = input("Enter Windows username: ")

    mount_point = f"/mnt/windows_music"

    print(f"\nTo mount Windows share, run these commands as root:")
    print(f"mkdir -p {mount_point}")
    print(
        f"mount -t cifs //{windows_ip}/{share_name} {mount_point} -o username={username},uid=0,gid=0,iocharset=utf8"
    )
    print(f"\nThen run the import tool with:")
    print(
        f"python3 music_import_tool.py --source {mount_point}/path/to/music --target /music/library"
    )


def main():
    parser = argparse.ArgumentParser(description="Music Library Import Tool")
    parser.add_argument(
        "--source", required=True, help="Source directory containing music files"
    )
    parser.add_argument(
        "--target", required=True, help="Target directory for organized library"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without copying"
    )
    parser.add_argument(
        "--move", action="store_true", help="Move files instead of copying"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip existing files (default)",
    )
    parser.add_argument(
        "--network-setup",
        action="store_true",
        help="Show network mount setup instructions",
    )

    args = parser.parse_args()

    if args.network_setup:
        setup_network_mount()
        return

    # Validate paths
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source path does not exist: {source_path}")
        sys.exit(1)

    options = {
        "dry_run": args.dry_run,
        "move_files": args.move,
        "overwrite": args.overwrite,
        "skip_existing": args.skip_existing,
    }

    # Create importer and run
    importer = MusicImporter(args.source, args.target, options)
    importer.import_library()


if __name__ == "__main__":
    main()
