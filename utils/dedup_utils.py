import os
import json
import hashlib
from pathlib import Path
from mutagen import File as MutagenFile
from typing import Dict, List, Tuple
import streamlit as st


class MusicDeduplicator:
    """Advanced music deduplication utility"""

    def __init__(self, music_path: str = "/music"):
        self.music_path = music_path
        self.cache_file = "/config/music_fingerprints.json"
        self.load_fingerprint_cache()

    def load_fingerprint_cache(self):
        """Load existing fingerprint cache"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    self.fingerprints = json.load(f)
            else:
                self.fingerprints = {}
        except:
            self.fingerprints = {}

    def save_fingerprint_cache(self):
        """Save fingerprint cache"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self.fingerprints, f, indent=2)
        except Exception as e:
            st.error(f"Failed to save fingerprint cache: {e}")

    def get_audio_fingerprint(self, file_path: str) -> Dict:
        """Generate audio fingerprint for deduplication"""
        try:
            # Check cache first
            file_stat = os.stat(file_path)
            cache_key = f"{file_path}_{file_stat.st_mtime}_{file_stat.st_size}"

            if cache_key in self.fingerprints:
                return self.fingerprints[cache_key]

            # Generate new fingerprint
            audio_file = MutagenFile(file_path)
            if audio_file is None:
                return {}

            # Extract metadata for comparison
            fingerprint = {
                "title": str(
                    audio_file.get("TIT2", [""])[0]
                    if "TIT2" in audio_file
                    else (
                        audio_file.get("TITLE", [""])[0]
                        if "TITLE" in audio_file
                        else ""
                    )
                )
                .lower()
                .strip(),
                "artist": str(
                    audio_file.get("TPE1", [""])[0]
                    if "TPE1" in audio_file
                    else (
                        audio_file.get("ARTIST", [""])[0]
                        if "ARTIST" in audio_file
                        else ""
                    )
                )
                .lower()
                .strip(),
                "album": str(
                    audio_file.get("TALB", [""])[0]
                    if "TALB" in audio_file
                    else (
                        audio_file.get("ALBUM", [""])[0]
                        if "ALBUM" in audio_file
                        else ""
                    )
                )
                .lower()
                .strip(),
                "duration": (
                    int(audio_file.info.length)
                    if hasattr(audio_file, "info") and audio_file.info
                    else 0
                ),
                "bitrate": (
                    getattr(audio_file.info, "bitrate", 0)
                    if hasattr(audio_file, "info")
                    else 0
                ),
                "file_size": file_stat.st_size,
                "file_path": file_path,
            }

            # Create a composite hash for fast comparison
            composite_string = f"{fingerprint['title']}_{fingerprint['artist']}_{fingerprint['duration']}"
            fingerprint["hash"] = hashlib.md5(composite_string.encode()).hexdigest()

            # Cache the fingerprint
            self.fingerprints[cache_key] = fingerprint

            return fingerprint

        except Exception as e:
            st.warning(f"Could not fingerprint {file_path}: {e}")
            return {}

    def find_duplicates(self, directories: List[str] = None) -> Dict[str, List[str]]:
        """Find duplicate music files"""
        if directories is None:
            directories = [
                f"{self.music_path}/library",
                f"{self.music_path}/youtube-music",
            ]

        st.info("🔍 Scanning for duplicates...")

        # Collect all audio files
        audio_files = []
        for directory in directories:
            if os.path.exists(directory):
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if file.lower().endswith(
                            (".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg")
                        ):
                            audio_files.append(os.path.join(root, file))

        st.info(f"📁 Found {len(audio_files)} audio files to analyze")

        # Generate fingerprints
        fingerprints = {}
        progress_bar = st.progress(0)

        for i, file_path in enumerate(audio_files):
            fingerprint = self.get_audio_fingerprint(file_path)
            if fingerprint and fingerprint.get("hash"):
                hash_key = fingerprint["hash"]
                if hash_key not in fingerprints:
                    fingerprints[hash_key] = []
                fingerprints[hash_key].append(fingerprint)

            progress_bar.progress((i + 1) / len(audio_files))

        # Save updated cache
        self.save_fingerprint_cache()

        # Find duplicates
        duplicates = {}
        for hash_key, files in fingerprints.items():
            if len(files) > 1:
                # Group by title-artist for better duplicate detection
                key = f"{files[0]['title']} - {files[0]['artist']}"
                duplicates[key] = [f["file_path"] for f in files]

        st.success(f"✅ Found {len(duplicates)} groups of duplicates")
        return duplicates

    def suggest_best_version(self, file_paths: List[str]) -> str:
        """Suggest the best version to keep among duplicates"""
        best_file = file_paths[0]
        best_score = 0

        for file_path in file_paths:
            fingerprint = self.get_audio_fingerprint(file_path)
            score = 0

            # Prefer higher bitrate
            score += fingerprint.get("bitrate", 0) / 1000

            # Prefer certain file formats
            if file_path.lower().endswith(".flac"):
                score += 10
            elif file_path.lower().endswith(".m4a"):
                score += 5
            elif file_path.lower().endswith(".mp3"):
                score += 3

            # Prefer files in library over downloads
            if "/library/" in file_path:
                score += 2

            # Prefer larger file sizes (usually better quality)
            score += fingerprint.get("file_size", 0) / (1024 * 1024)  # Convert to MB

            if score > best_score:
                best_score = score
                best_file = file_path

        return best_file

    def remove_duplicates(
        self, duplicates: Dict[str, List[str]], auto_remove: bool = False
    ) -> int:
        """Remove duplicate files, keeping the best version"""
        removed_count = 0

        for title_artist, file_paths in duplicates.items():
            if len(file_paths) > 1:
                best_file = self.suggest_best_version(file_paths)

                for file_path in file_paths:
                    if file_path != best_file:
                        if auto_remove:
                            try:
                                os.remove(file_path)
                                removed_count += 1
                                st.success(f"🗑️ Removed: {os.path.basename(file_path)}")
                            except Exception as e:
                                st.error(f"❌ Failed to remove {file_path}: {e}")
                        else:
                            st.info(f"🔍 Would remove: {file_path}")

        return removed_count


def render_deduplication_interface():
    """Render the deduplication interface"""
    st.subheader("🔍 Music Deduplication")

    deduplicator = MusicDeduplicator()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Scan for Duplicates"):
            duplicates = deduplicator.find_duplicates()
            st.session_state.duplicates = duplicates

    with col2:
        if st.button("🧹 Clear Fingerprint Cache"):
            try:
                os.remove(deduplicator.cache_file)
                st.success("Cache cleared!")
            except:
                st.info("No cache to clear")

    if hasattr(st.session_state, "duplicates") and st.session_state.duplicates:
        st.markdown(
            f"**Found {len(st.session_state.duplicates)} groups of duplicates:**"
        )

        for title_artist, file_paths in st.session_state.duplicates.items():
            with st.expander(f"🎵 {title_artist} ({len(file_paths)} copies)"):
                best_file = deduplicator.suggest_best_version(file_paths)

                for file_path in file_paths:
                    is_best = file_path == best_file
                    icon = "⭐" if is_best else "🗑️"
                    status = "KEEP (Best Quality)" if is_best else "REMOVE"

                    fingerprint = deduplicator.get_audio_fingerprint(file_path)
                    bitrate = fingerprint.get("bitrate", 0)
                    size_mb = fingerprint.get("file_size", 0) / (1024 * 1024)

                    st.markdown(
                        f"""
                    {icon} **{status}**  
                    📁 {file_path}  
                    🎵 {bitrate} kbps | 💾 {size_mb:.1f} MB
                    """
                    )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("👀 Preview Removal (Safe)"):
                removed = deduplicator.remove_duplicates(
                    st.session_state.duplicates, auto_remove=False
                )
                st.info(f"Would remove {removed} duplicate files")

        with col2:
            if st.button("🗑️ Remove Duplicates (PERMANENT)", type="primary"):
                removed = deduplicator.remove_duplicates(
                    st.session_state.duplicates, auto_remove=True
                )
                st.success(f"Removed {removed} duplicate files!")
                del st.session_state.duplicates
                st.rerun()
