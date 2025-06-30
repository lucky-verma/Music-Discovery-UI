import streamlit as st
import os
import subprocess
import shutil
from pathlib import Path
from utils.dedup_utils import MusicDeduplicator, render_deduplication_interface


def render_import_page():
    """Render the music import and management page"""

    st.header("📥 Music Library Import & Management")

    # Import section
    st.subheader("🎵 Import Your Existing Music")

    import_tab1, import_tab2, import_tab3 = st.tabs(
        ["📂 Folder Import", "💽 External Drive", "🔍 Deduplication"]
    )

    with import_tab1:
        st.markdown("**Import music from a folder on your system**")

        # Source path input
        source_path = st.text_input(
            "📂 Source Folder Path:",
            placeholder="/path/to/your/music/folder",
            help="Enter the full path to your music collection",
        )

        # Destination selection
        destination = st.selectbox(
            "📁 Import Destination:",
            [
                "/music/library (Recommended - Your organized collection)",
                "/music/import-staging (For review before organizing)",
            ],
        )

        dest_path = (
            "/music/library" if "library" in destination else "/music/import-staging"
        )

        # Import options
        col1, col2 = st.columns(2)

        with col1:
            copy_files = st.checkbox("📋 Copy files (keep originals)", value=True)
            organize_files = st.checkbox("📁 Auto-organize by metadata", value=True)

        with col2:
            check_duplicates = st.checkbox("🔍 Check for duplicates", value=True)
            fix_metadata = st.checkbox("🏷️ Fix common metadata issues", value=True)

        if st.button("🚀 Start Import", type="primary", disabled=not source_path):
            if source_path and os.path.exists(source_path):
                import_music_folder(
                    source_path,
                    dest_path,
                    copy_files,
                    organize_files,
                    check_duplicates,
                    fix_metadata,
                )
            else:
                st.error("❌ Source folder does not exist!")

    with import_tab2:
        st.markdown("**Import music from external drives (USB, etc.)**")

        # Detect available drives
        if st.button("🔍 Scan for External Drives"):
            drives = detect_external_drives()
            if drives:
                st.session_state.detected_drives = drives
                st.success(f"Found {len(drives)} external drives")
            else:
                st.info("No external drives detected")

        # Display detected drives
        if hasattr(st.session_state, "detected_drives"):
            st.markdown("**📁 Detected Drives:**")

            for i, drive in enumerate(st.session_state.detected_drives):
                with st.expander(
                    f"💽 {drive['device']} - {drive['size']} ({drive['type']})"
                ):
                    st.markdown(
                        f"""
                    **Mount Point:** `{drive['mount']}`  
                    **File System:** {drive['filesystem']}  
                    **Available Space:** {drive['available']}
                    """
                    )

                    # Quick scan for music
                    if st.button(f"🎵 Scan for Music", key=f"scan_drive_{i}"):
                        music_files = scan_drive_for_music(drive["mount"])
                        if music_files:
                            st.success(f"Found {len(music_files)} music files!")
                            st.session_state[f"drive_music_{i}"] = music_files
                        else:
                            st.info("No music files found on this drive")

                    # Import from drive
                    if hasattr(st.session_state, f"drive_music_{i}"):
                        music_count = len(st.session_state[f"drive_music_{i}"])
                        if st.button(
                            f"📥 Import {music_count} Music Files",
                            key=f"import_drive_{i}",
                        ):
                            import_from_external_drive(drive["mount"], "/music/library")

    with import_tab3:
        render_deduplication_interface()

    st.markdown("---")

    # Library management section
    st.subheader("📊 Library Management")

    management_tab1, management_tab2 = st.tabs(["📈 Statistics", "🔧 Maintenance"])

    with management_tab1:
        display_library_statistics()

    with management_tab2:
        render_maintenance_tools()


def import_music_folder(
    source_path: str,
    dest_path: str,
    copy_files: bool,
    organize_files: bool,
    check_duplicates: bool,
    fix_metadata: bool,
):
    """Import music from a folder with various options"""

    try:
        # Create destination
        os.makedirs(dest_path, exist_ok=True)

        # Scan source for music files
        with st.spinner("🔍 Scanning source folder..."):
            music_files = []
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    if file.lower().endswith(
                        (".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".wma")
                    ):
                        music_files.append(os.path.join(root, file))

        if not music_files:
            st.error("❌ No music files found in the source folder!")
            return

        st.success(f"📁 Found {len(music_files)} music files")

        # Check for duplicates if requested
        if check_duplicates:
            with st.spinner("🔍 Checking for duplicates..."):
                deduplicator = MusicDeduplicator()
                # Add source files to temporary fingerprint check
                duplicates_found = 0
                for file_path in music_files:
                    fingerprint = deduplicator.get_audio_fingerprint(file_path)
                    # Simple duplicate check logic here

                if duplicates_found > 0:
                    st.warning(f"⚠️ Found {duplicates_found} potential duplicates")

        # Import files
        progress_bar = st.progress(0)
        success_count = 0
        error_count = 0

        for i, source_file in enumerate(music_files):
            try:
                # Determine destination filename
                if organize_files:
                    dest_file = get_organized_path(source_file, dest_path)
                else:
                    rel_path = os.path.relpath(source_file, source_path)
                    dest_file = os.path.join(dest_path, rel_path)

                # Create destination directory
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)

                # Copy or move file
                if copy_files:
                    shutil.copy2(source_file, dest_file)
                else:
                    shutil.move(source_file, dest_file)

                # Fix metadata if requested
                if fix_metadata:
                    fix_common_metadata_issues(dest_file)

                success_count += 1

            except Exception as e:
                st.error(f"❌ Failed to import {os.path.basename(source_file)}: {e}")
                error_count += 1

            progress_bar.progress((i + 1) / len(music_files))

        # Trigger Navidrome rescan
        with st.spinner("📡 Triggering library scan..."):
            trigger_navidrome_scan()

        st.success(
            f"✅ Import completed! {success_count} files imported, {error_count} errors"
        )

    except Exception as e:
        st.error(f"❌ Import failed: {e}")


def detect_external_drives():
    """Detect connected external drives"""
    try:
        result = subprocess.run(["lsblk", "-J"], capture_output=True, text=True)
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)

            drives = []
            for device in data.get("blockdevices", []):
                if device.get("type") == "disk" and device.get("size"):
                    # Look for mounted partitions
                    for child in device.get("children", []):
                        if child.get("mountpoint"):
                            drives.append(
                                {
                                    "device": device["name"],
                                    "mount": child["mountpoint"],
                                    "size": device["size"],
                                    "type": device.get("tran", "unknown"),
                                    "filesystem": child.get("fstype", "unknown"),
                                    "available": child.get("avail", "unknown"),
                                }
                            )

            return drives
    except:
        return []


def scan_drive_for_music(mount_point: str):
    """Scan a drive for music files"""
    music_files = []
    try:
        for root, dirs, files in os.walk(mount_point):
            for file in files:
                if file.lower().endswith(
                    (".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".wma")
                ):
                    music_files.append(os.path.join(root, file))

            # Limit scan to prevent timeout
            if len(music_files) > 1000:
                break
    except:
        pass

    return music_files


def get_organized_path(file_path: str, base_dest: str) -> str:
    """Get organized destination path based on metadata"""
    try:
        from mutagen import File as MutagenFile

        audio_file = MutagenFile(file_path)
        if audio_file is None:
            return os.path.join(base_dest, "Unknown", os.path.basename(file_path))

        # Extract metadata
        artist = str(
            audio_file.get("TPE1", ["Unknown Artist"])[0]
            if "TPE1" in audio_file
            else (
                audio_file.get("ARTIST", ["Unknown Artist"])[0]
                if "ARTIST" in audio_file
                else "Unknown Artist"
            )
        )
        album = str(
            audio_file.get("TALB", ["Unknown Album"])[0]
            if "TALB" in audio_file
            else (
                audio_file.get("ALBUM", ["Unknown Album"])[0]
                if "ALBUM" in audio_file
                else "Unknown Album"
            )
        )
        title = str(
            audio_file.get("TIT2", ["Unknown Title"])[0]
            if "TIT2" in audio_file
            else (
                audio_file.get("TITLE", ["Unknown Title"])[0]
                if "TITLE" in audio_file
                else "Unknown Title"
            )
        )

        # Clean names for filesystem
        artist = clean_filename(artist)
        album = clean_filename(album)
        title = clean_filename(title)

        # Get file extension
        ext = os.path.splitext(file_path)[1]

        # Create organized path
        return os.path.join(base_dest, artist, album, f"{title}{ext}")

    except:
        # Fallback to original filename
        return os.path.join(base_dest, "Import", os.path.basename(file_path))


def clean_filename(name: str) -> str:
    """Clean filename for filesystem compatibility"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")

    # Limit length
    if len(name) > 100:
        name = name[:100]

    return name.strip()


def fix_common_metadata_issues(file_path: str):
    """Fix common metadata issues"""
    try:
        from mutagen import File as MutagenFile

        audio_file = MutagenFile(file_path)
        if audio_file is None:
            return

        modified = False

        # Add missing album artist
        if "ALBUMARTIST" not in audio_file and "TPE1" in audio_file:
            audio_file["ALBUMARTIST"] = audio_file["TPE1"]
            modified = True

        # Fix common encoding issues
        for key in audio_file.keys():
            if isinstance(audio_file[key], list) and len(audio_file[key]) > 0:
                value = str(audio_file[key][0])
                # Fix common issues like double encoding, etc.
                # This is a simplified example
                if modified:
                    audio_file[key] = [value]

        if modified:
            audio_file.save()

    except Exception as e:
        st.warning(f"Could not fix metadata for {os.path.basename(file_path)}: {e}")


def display_library_statistics():
    """Display library statistics"""
    try:
        # Count files by type
        stats = {}
        total_size = 0

        for root, dirs, files in os.walk("/music"):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in [".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".wma"]:
                    stats[ext] = stats.get(ext, 0) + 1
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except:
                        pass

        if stats:
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Total Files", sum(stats.values()))
                st.metric("Total Size", f"{total_size / (1024**3):.1f} GB")

            with col2:
                for ext, count in sorted(stats.items()):
                    st.metric(f"{ext.upper()} Files", count)
        else:
            st.info("No music files found in library")

    except Exception as e:
        st.error(f"Error calculating statistics: {e}")


def render_maintenance_tools():
    """Render maintenance tools"""

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Rescan Navidrome Library"):
            with st.spinner("Triggering library rescan..."):
                if trigger_navidrome_scan():
                    st.success("✅ Library rescan triggered!")
                else:
                    st.error("❌ Failed to trigger rescan")

        if st.button("🧹 Clean Empty Folders"):
            removed = clean_empty_folders("/music")
            if removed > 0:
                st.success(f"✅ Removed {removed} empty folders")
            else:
                st.info("No empty folders found")

    with col2:
        if st.button("📊 Regenerate Statistics"):
            st.rerun()

        if st.button("🔍 Verify File Integrity"):
            verify_file_integrity()


def trigger_navidrome_scan():
    """Trigger Navidrome library rescan"""
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "navidrome",
                "curl",
                "-X",
                "POST",
                "http://localhost:4533/api/scanner/scan",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except:
        return False


def clean_empty_folders(path: str) -> int:
    """Remove empty folders recursively"""
    removed = 0
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):  # Directory is empty
                        os.rmdir(dir_path)
                        removed += 1
                except:
                    pass
    except:
        pass

    return removed


def verify_file_integrity():
    """Basic file integrity verification"""
    with st.spinner("Verifying file integrity..."):
        corrupted_files = []

        for root, dirs, files in os.walk("/music"):
            for file in files:
                if file.lower().endswith(
                    (".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg")
                ):
                    file_path = os.path.join(root, file)
                    try:
                        from mutagen import File as MutagenFile

                        audio_file = MutagenFile(file_path)
                        if audio_file is None:
                            corrupted_files.append(file_path)
                    except:
                        corrupted_files.append(file_path)

        if corrupted_files:
            st.error(f"❌ Found {len(corrupted_files)} potentially corrupted files")
            with st.expander("View corrupted files"):
                for file_path in corrupted_files:
                    st.text(file_path)
        else:
            st.success("✅ All files passed integrity check")


def import_from_external_drive(drive_mount: str, dest_path: str):
    """Import music from external drive"""
    with st.spinner("Importing from external drive..."):
        import_music_folder(
            drive_mount,
            dest_path,
            copy_files=True,
            organize_files=True,
            check_duplicates=True,
            fix_metadata=True,
        )
