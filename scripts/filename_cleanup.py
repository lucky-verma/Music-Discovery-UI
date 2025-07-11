#!/usr/bin/env python3
import os
import re
import shutil
from pathlib import Path
import logging

class FilenameCleanup:
    def __init__(self, source_dir="/music/library", backup_dir="/music/library-backup"):
        self.source_dir = Path(source_dir)
        self.backup_dir = Path(backup_dir)
        
        # Website patterns to remove
        self.website_patterns = [
            r'\(.*?\.com\)',
            r'\(.*?\.net\)',
            r'\(.*?\.org\)',
            r'\(.*?\.in\)',
            r'\(.*?mp3.*?\)',
            r'pagalworld',
            r'songspk',
            r'djmaza',
            r'freshmaza',
            r'bengali-mp3',
            r'bollywoodsongs',
            r'hindisongs',
            r'musicbadshah',
            r'downloadming',
            r'mr-jatt',
            r'wapking',
            r'songs\.pk',
        ]
        
        # Invalid filename characters
        self.invalid_chars = r'[<>:"/\\|?*]'
        
    def clean_name(self, name):
        """Clean individual filename or directory name"""
        # Remove website patterns
        for pattern in self.website_patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        # Remove invalid characters
        name = re.sub(self.invalid_chars, '_', name)
        
        # Clean up extra spaces and underscores
        name = re.sub(r'[_\s]+', ' ', name)
        name = name.strip(' _-.')
        
        # Remove leading numbers/dots
        name = re.sub(r'^[\d\.\-_\s]+', '', name)
        
        return name if name else "Unknown"
    
    def create_backup(self):
        """Create backup of original library"""
        if not self.backup_dir.exists():
            print(f"Creating backup at {self.backup_dir}")
            shutil.copytree(self.source_dir, self.backup_dir)
            print("✅ Backup created successfully")
        else:
            print("⚠️ Backup already exists, skipping")
    
    def cleanup_library(self, dry_run=True):
        """Clean up the entire library"""
        changes = []
        
        for root, dirs, files in os.walk(self.source_dir, topdown=False):
            current_path = Path(root)
            
            # Clean files first
            for file in files:
                if file.lower().endswith(('.mp3', '.m4a', '.flac', '.wav')):
                    old_path = current_path / file
                    clean_name = self.clean_name(file)
                    new_path = current_path / clean_name
                    
                    if old_path != new_path:
                        changes.append(('file', str(old_path), str(new_path)))
                        if not dry_run:
                            new_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(old_path), str(new_path))
            
            # Clean directories
            for dir_name in dirs:
                old_dir_path = current_path / dir_name
                clean_name = self.clean_name(dir_name)
                new_dir_path = current_path / clean_name
                
                if old_dir_path != new_dir_path and clean_name != "Unknown":
                    changes.append(('dir', str(old_dir_path), str(new_dir_path)))
                    if not dry_run:
                        new_dir_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(old_dir_path), str(new_dir_path))
        
        return changes

if __name__ == "__main__":
    cleanup = FilenameCleanup()
    
    # Create backup first
    cleanup.create_backup()
    
    # Dry run first
    print("🔍 Dry run - showing what would be changed:")
    changes = cleanup.cleanup_library(dry_run=True)
    
    for change_type, old_path, new_path in changes[:20]:  # Show first 20
        print(f"{change_type}: {old_path} -> {new_path}")
    
    print(f"\nTotal changes: {len(changes)}")
    
    if input("\nProceed with cleanup? (y/N): ").lower() == 'y':
        print("🧹 Executing cleanup...")
        cleanup.cleanup_library(dry_run=False)
        print("✅ Cleanup completed!")
