#!/usr/bin/env python3
"""
Fix Navidrome greyed out tracks and database issues
"""

import subprocess
import sqlite3
import os
from pathlib import Path
import json
import time


class NavidromeFixer:
    def __init__(self):
        self.navidrome_data = (
            "/mnt/docker-data/navidrome-music-system/music-discovery-ui/navidrome-data"
        )
        self.music_path = "/music"

    def get_database_path(self):
        """Find Navidrome database file"""
        db_path = Path(self.navidrome_data) / "navidrome.db"
        if db_path.exists():
            return db_path

        # Alternative locations
        for possible_path in [
            Path(self.navidrome_data) / "data" / "navidrome.db",
            Path("/data") / "navidrome.db",
        ]:
            if possible_path.exists():
                return possible_path

        return None

    def backup_database(self):
        """Create database backup"""
        db_path = self.get_database_path()
        if db_path:
            backup_path = db_path.parent / f"navidrome_backup_{int(time.time())}.db"
            subprocess.run(["cp", str(db_path), str(backup_path)])
            print(f"✅ Database backed up to: {backup_path}")
            return backup_path
        return None

    def clean_orphaned_records(self):
        """Remove database records for missing files"""
        db_path = self.get_database_path()
        if not db_path:
            print("❌ Database not found")
            return False

        print("🔧 Cleaning orphaned database records...")

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Get all tracks from database
            cursor.execute("SELECT id, path FROM media_file")
            tracks = cursor.fetchall()

            orphaned_count = 0
            for track_id, file_path in tracks:
                full_path = Path(self.music_path) / file_path.lstrip("/")

                if not full_path.exists():
                    print(f"  🗑️ Removing orphaned record: {file_path}")
                    cursor.execute("DELETE FROM media_file WHERE id = ?", (track_id,))
                    orphaned_count += 1

            conn.commit()
            conn.close()

            print(f"✅ Removed {orphaned_count} orphaned records")
            return True

        except Exception as e:
            print(f"❌ Error cleaning database: {e}")
            return False

    def fix_file_permissions(self):
        """Fix file permissions for music library"""
        print("🔧 Fixing file permissions...")

        try:
            # Fix ownership and permissions
            subprocess.run(["chown", "-R", "root:root", self.music_path], check=True)
            subprocess.run(["chmod", "-R", "755", self.music_path], check=True)

            # Make files readable
            subprocess.run(
                [
                    "find",
                    self.music_path,
                    "-type",
                    "f",
                    "-exec",
                    "chmod",
                    "644",
                    "{}",
                    "+",
                ],
                check=True,
            )

            print("✅ File permissions fixed")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Error fixing permissions: {e}")
            return False

    def trigger_full_rescan(self):
        """Force complete library rescan"""
        print("🔄 Triggering full library rescan...")

        try:
            # Stop Navidrome
            subprocess.run(["docker", "stop", "navidrome"], check=True)

            # Clear scan cache if it exists
            cache_path = Path(self.navidrome_data) / "cache"
            if cache_path.exists():
                subprocess.run(["rm", "-rf", str(cache_path)], check=True)

            # Restart Navidrome
            subprocess.run(["docker", "start", "navidrome"], check=True)

            # Wait for startup
            import time

            time.sleep(10)

            # Trigger scan
            subprocess.run(
                ["curl", "-X", "POST", "http://192.168.1.39:4533/api/scanner/scan"],
                timeout=10,
            )

            print("✅ Full rescan triggered")
            return True

        except Exception as e:
            print(f"❌ Error during rescan: {e}")
            return False

    def comprehensive_fix(self):
        """Run complete fix process"""
        print("🚀 Starting comprehensive Navidrome fix...")

        # Step 1: Backup
        self.backup_database()

        # Step 2: Fix permissions
        self.fix_file_permissions()

        # Step 3: Clean database
        self.clean_orphaned_records()

        # Step 4: Full rescan
        self.trigger_full_rescan()

        print("🎉 Comprehensive fix complete!")
        print("📝 Check Navidrome in 5-10 minutes for results")


if __name__ == "__main__":
    fixer = NavidromeFixer()
    fixer.comprehensive_fix()
