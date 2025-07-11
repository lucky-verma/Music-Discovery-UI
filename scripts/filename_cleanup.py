#!/usr/bin/env python3
"""
Advanced Music Library Cleanup Script
Removes website names, fixes extensions, and prepares files for Beets processing
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Set
import logging
from mutagen import File as MutagenFile
import mimetypes


class AdvancedMusicCleaner:
    def __init__(self, source_path: str = "/music/library"):
        self.source_path = Path(source_path)
        self.backup_path = Path("/music/library-backup")
        self.processed_count = 0
        self.error_count = 0

        # Comprehensive website name patterns
        self.website_patterns = [
            # Exact matches (case insensitive)
            r"pagalworld",
            r"songspk",
            r"djmaza",
            r"freshmaza",
            r"bengali-mp3",
            r"bollywoodsongs",
            r"hindisongs",
            r"musicbadshah",
            r"downloadming",
            r"mr-jatt",
            r"wapking",
            r"songs\.pk",
            r"songsmp3",
            r"mp3skull",
            r"beemp3",
            r"mp3juices",
            r"mp3clan",
            r"mp3raid",
            r"mp3bear",
            r"mp3fusion",
            r"mp3download",
            r"mp3free",
            r"mp3party",
            r"mp3tube",
            r"mp3cloud",
            r"mp3hub",
            r"mp3king",
            r"mp3zone",
            r"mp3world",
            r"songslover",
            r"primemusic",
            r"webmusic",
            r"musicpleer",
            r"gaana",
            r"saavn",
            r"wynk",
            r"hungama",
            r"jiosaavn",
            r"soundcloud",
            r"spotify",
            r"youtube",
            r"ytmp3",
            r"mp3converter",
            # Pattern-based matches
            r".*mp3.*",
            r".*song.*",
            r".*music.*",
            r".*download.*",
            r".*free.*",
            r".*pk.*",
            r".*world.*",
            r".*hub.*",
            r".*zone.*",
            r".*cloud.*",
            r".*tube.*",
            r".*bear.*",
            r".*skull.*",
            r".*juice.*",
            r".*clan.*",
            r".*raid.*",
            # Domain-like patterns
            r".*\.com.*",
            r".*\.net.*",
            r".*\.org.*",
            r".*\.in.*",
            r".*\.pk.*",
            r".*\.co.*",
            r".*\.info.*",
            # Bracketed patterns
            r"\[.*mp3.*\]",
            r"\[.*song.*\]",
            r"\[.*music.*\]",
            r"\(.*mp3.*\)",
            r"\(.*song.*\)",
            r"\(.*music.*\)",
            r"\{.*mp3.*\}",
            r"\{.*song.*\}",
            r"\{.*music.*\}",
        ]

        # Valid audio extensions
        self.valid_extensions = {
            ".mp3",
            ".m4a",
            ".flac",
            ".wav",
            ".ogg",
            ".aac",
            ".wma",
            ".opus",
        }

        # Common audio MIME types
        self.audio_mimes = {
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/flac": ".flac",
            "audio/x-flac": ".flac",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/vorbis": ".ogg",
            "audio/aac": ".aac",
            "audio/x-ms-wma": ".wma",
            "audio/opus": ".opus",
        }

        self.setup_logging()

    def setup_logging(self):
        """Setup comprehensive logging"""
        log_file = "/music/cleanup_log.txt"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def create_backup(self):
        """Create backup of original library"""
        if self.backup_path.exists():
            self.logger.info("Backup already exists, skipping...")
            return True

        try:
            self.logger.info("Creating backup of original library...")
            shutil.copytree(self.source_path, self.backup_path)
            self.logger.info(f"Backup created at {self.backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False

    def detect_audio_format(self, file_path: Path) -> str:
        """Detect proper audio format and return correct extension"""
        try:
            # First try mutagen
            audio_file = MutagenFile(file_path)
            if audio_file:
                mime_type = audio_file.mime[0] if audio_file.mime else None
                if mime_type in self.audio_mimes:
                    return self.audio_mimes[mime_type]

            # Fallback to mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type in self.audio_mimes:
                return self.audio_mimes[mime_type]

            # Check file signature (magic bytes)
            with open(file_path, "rb") as f:
                header = f.read(12)

                # MP3 signatures
                if header.startswith(b"ID3") or header[0:2] == b"\xff\xfb":
                    return ".mp3"

                # M4A/AAC signatures
                if b"ftyp" in header[4:8]:
                    return ".m4a"

                # FLAC signature
                if header.startswith(b"fLaC"):
                    return ".flac"

                # WAV signature
                if header.startswith(b"RIFF") and b"WAVE" in header:
                    return ".wav"

                # OGG signature
                if header.startswith(b"OggS"):
                    return ".ogg"

            return file_path.suffix.lower()

        except Exception as e:
            self.logger.warning(f"Could not detect format for {file_path}: {e}")
            return file_path.suffix.lower()

    def clean_filename(self, filename: str) -> str:
        """Clean filename removing website names and problematic characters"""
        original = filename

        # Remove file extension for processing
        name_part = Path(filename).stem
        ext_part = Path(filename).suffix

        # Remove website patterns (case insensitive)
        for pattern in self.website_patterns:
            name_part = re.sub(pattern, "", name_part, flags=re.IGNORECASE)

        # Remove common problematic patterns
        problematic_patterns = [
            r"www\..*",  # www. patterns
            r"http[s]?://.*",  # URLs
            r"\.com.*",
            r"\.net.*",
            r"\.org.*",  # Domain extensions
            r"\[.*?\]",  # Bracketed content (often website names)
            r"\(.*?\)",  # Parenthetical content that looks like websites
            r"\{.*?\}",  # Braced content
            r"_+",  # Multiple underscores
            r"-+",  # Multiple hyphens
            r"\.+",  # Multiple dots
            r"\s+",  # Multiple spaces
            r"[^\w\s\-\.]",  # Non-word characters except space, hyphen, dot
            r"^\s*[-\.\s]*",  # Leading spaces, hyphens, dots
            r"[-\.\s]*\s*$",  # Trailing spaces, hyphens, dots
        ]

        for pattern in problematic_patterns:
            name_part = re.sub(pattern, " ", name_part, flags=re.IGNORECASE)

        # Clean up spacing and formatting
        name_part = " ".join(name_part.split())  # Normalize whitespace
        name_part = name_part.strip()

        # Remove track numbers if they're at the beginning
        name_part = re.sub(r"^\d+\s*[-\.\s]*", "", name_part)

        # If name became empty, use original
        if not name_part or len(name_part) < 3:
            name_part = Path(original).stem

        # Capitalize properly
        name_part = name_part.title()

        return name_part + ext_part

    def clean_directory_name(self, dirname: str) -> str:
        """Clean directory name removing website names"""
        original = dirname

        # Remove website patterns
        for pattern in self.website_patterns:
            dirname = re.sub(pattern, "", dirname, flags=re.IGNORECASE)

        # Clean brackets and parentheses that often contain website names
        dirname = re.sub(r"\[.*?\]", "", dirname)
        dirname = re.sub(r"\(.*?\)", "", dirname)
        dirname = re.sub(r"\{.*?\}", "", dirname)

        # Remove problematic characters
        dirname = re.sub(r"[^\w\s\-]", " ", dirname)
        dirname = " ".join(dirname.split())
        dirname = dirname.strip()

        # If directory name became empty, use original
        if not dirname or len(dirname) < 2:
            dirname = original

        return dirname.title()

    def process_file(self, file_path: Path) -> bool:
        """Process individual audio file"""
        try:
            # Check if it's actually an audio file
            if file_path.suffix.lower() not in self.valid_extensions:
                # Try to detect the real format
                correct_ext = self.detect_audio_format(file_path)
                if correct_ext in self.valid_extensions:
                    new_name = file_path.stem + correct_ext
                    new_path = file_path.parent / new_name
                    file_path.rename(new_path)
                    file_path = new_path
                    self.logger.info(f"Fixed extension: {file_path.name}")
                else:
                    self.logger.warning(f"Not an audio file: {file_path}")
                    return False

            # Clean filename
            clean_name = self.clean_filename(file_path.name)

            if clean_name != file_path.name:
                new_path = file_path.parent / clean_name

                # Handle conflicts
                counter = 1
                while new_path.exists():
                    stem = Path(clean_name).stem
                    ext = Path(clean_name).suffix
                    new_name = f"{stem}_{counter}{ext}"
                    new_path = file_path.parent / new_name
                    counter += 1

                file_path.rename(new_path)
                self.logger.info(f"Renamed: {file_path.name} -> {new_path.name}")

            self.processed_count += 1
            return True

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            self.error_count += 1
            return False

    def process_directory(self, dir_path: Path) -> bool:
        """Process directory and its contents"""
        try:
            # First process all files in directory
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    self.process_file(file_path)
                elif file_path.is_dir():
                    self.process_directory(file_path)

            # Then clean directory name
            clean_name = self.clean_directory_name(dir_path.name)

            if clean_name != dir_path.name and clean_name:
                new_path = dir_path.parent / clean_name

                # Handle conflicts
                counter = 1
                while new_path.exists():
                    new_name = f"{clean_name}_{counter}"
                    new_path = dir_path.parent / new_name
                    counter += 1

                dir_path.rename(new_path)
                self.logger.info(
                    f"Renamed directory: {dir_path.name} -> {new_path.name}"
                )

            return True

        except Exception as e:
            self.logger.error(f"Error processing directory {dir_path}: {e}")
            return False

    def run_cleanup(self, create_backup: bool = True) -> Dict:
        """Run the complete cleanup process"""
        self.logger.info("Starting advanced music library cleanup...")

        if create_backup:
            if not self.create_backup():
                return {"success": False, "error": "Failed to create backup"}

        # Process entire library
        for item in self.source_path.iterdir():
            if item.is_file():
                self.process_file(item)
            elif item.is_dir():
                self.process_directory(item)

        results = {
            "success": True,
            "processed_files": self.processed_count,
            "errors": self.error_count,
            "backup_created": create_backup,
        }

        self.logger.info(
            f"Cleanup complete! Processed: {self.processed_count}, Errors: {self.error_count}"
        )
        return results


if __name__ == "__main__":
    cleaner = AdvancedMusicCleaner()
    results = cleaner.run_cleanup(create_backup=True)
    print(f"Cleanup Results: {results}")
