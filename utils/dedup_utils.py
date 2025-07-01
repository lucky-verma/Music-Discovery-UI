import os
import hashlib
from mutagen import File
from typing import List, Dict, Optional
import streamlit as st


class MusicDeduplicator:
    """Music file deduplication utility"""

    def __init__(self, music_directory: str = "/music"):
        self.music_directory = music_directory

    def find_duplicates(self) -> Dict[str, List[str]]:
        """Find duplicate music files based on audio fingerprint"""
        try:
            audio_hashes = {}
            duplicates = {}

            # Scan for audio files
            for root, dirs, files in os.walk(self.music_directory):
                for file in files:
                    if file.lower().endswith((".mp3", ".m4a", ".flac", ".wav")):
                        file_path = os.path.join(root, file)

                        try:
                            # Get basic metadata for comparison
                            audio_file = File(file_path)
                            if audio_file:
                                # Create identifier from title, artist, duration
                                title = (
                                    str(audio_file.get("TIT2", [""])[0]).lower().strip()
                                )
                                artist = (
                                    str(audio_file.get("TPE1", [""])[0]).lower().strip()
                                )
                                duration = (
                                    audio_file.info.length
                                    if hasattr(audio_file, "info")
                                    else 0
                                )

                                # Create hash from metadata
                                identifier = f"{title}|{artist}|{int(duration)}"
                                identifier_hash = hashlib.md5(
                                    identifier.encode()
                                ).hexdigest()

                                if identifier_hash in audio_hashes:
                                    # Found duplicate
                                    if identifier_hash not in duplicates:
                                        duplicates[identifier_hash] = [
                                            audio_hashes[identifier_hash]
                                        ]
                                    duplicates[identifier_hash].append(file_path)
                                else:
                                    audio_hashes[identifier_hash] = file_path

                        except Exception as e:
                            continue

            return duplicates

        except Exception as e:
            st.error(f"Error finding duplicates: {str(e)}")
            return {}

    def remove_duplicates(
        self, duplicates: Dict[str, List[str]], keep_highest_quality: bool = True
    ) -> int:
        """Remove duplicate files, keeping the highest quality version"""
        removed_count = 0

        try:
            for hash_key, file_list in duplicates.items():
                if len(file_list) <= 1:
                    continue

                if keep_highest_quality:
                    # Sort by file size (proxy for quality)
                    file_list.sort(key=lambda x: os.path.getsize(x), reverse=True)
                    files_to_remove = file_list[1:]  # Keep first (largest)
                else:
                    files_to_remove = file_list[1:]  # Keep first found

                for file_path in files_to_remove:
                    try:
                        os.remove(file_path)
                        removed_count += 1
                    except Exception as e:
                        st.warning(f"Could not remove {file_path}: {str(e)}")

        except Exception as e:
            st.error(f"Error removing duplicates: {str(e)}")

        return removed_count

    def get_duplicate_stats(self) -> Dict:
        """Get statistics about duplicates in the library"""
        duplicates = self.find_duplicates()

        total_duplicates = sum(len(files) - 1 for files in duplicates.values())
        duplicate_groups = len(duplicates)

        # Calculate wasted space
        wasted_space = 0
        for file_list in duplicates.values():
            if len(file_list) > 1:
                # Keep largest, sum the rest
                file_list.sort(key=lambda x: os.path.getsize(x), reverse=True)
                wasted_space += sum(os.path.getsize(f) for f in file_list[1:])

        return {
            "duplicate_groups": duplicate_groups,
            "total_duplicates": total_duplicates,
            "wasted_space_bytes": wasted_space,
            "wasted_space_mb": round(wasted_space / (1024 * 1024), 2),
        }
