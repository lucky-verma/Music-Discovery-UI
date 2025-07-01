import os
import json
import threading
import subprocess
import uuid
from datetime import datetime
from typing import Dict, Optional
import streamlit as st


class JobManager:
    """Advanced job queue management for background music downloads"""

    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
        self.history_file = "/config/download_history.json"
        self.ensure_files()

    def ensure_files(self):
        """Ensure job and history files exist"""
        for file_path in [self.jobs_file, self.history_file]:
            if not os.path.exists(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w") as f:
                    json.dump({}, f)

    def add_job(self, job_type: str, url: str, metadata: Dict) -> str:
        """Add a new background download job"""
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "type": job_type,
            "url": url,
            "metadata": metadata,
            "status": "queued",
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "progress": 0,
            "message": "Queued for download",
            "error_count": 0,
            "max_retries": 3,
        }

        # Save job to queue
        jobs = self.get_all_jobs()
        jobs[job_id] = job
        self._save_jobs(jobs)

        # Start processing in background thread
        thread = threading.Thread(target=self._process_job, args=(job_id,))
        thread.daemon = True
        thread.start()

        return job_id

    def get_all_jobs(self) -> Dict:
        """Get all jobs from queue"""
        try:
            with open(self.jobs_file, "r") as f:
                return json.load(f)
        except:
            return {}

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get specific job by ID"""
        jobs = self.get_all_jobs()
        return jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: str = None,
        progress: int = None,
        message: str = None,
        error: str = None,
    ):
        """Update job status and progress"""
        jobs = self.get_all_jobs()
        if job_id in jobs:
            if status:
                jobs[job_id]["status"] = status
            if progress is not None:
                jobs[job_id]["progress"] = progress
            if message:
                jobs[job_id]["message"] = message
            if error:
                jobs[job_id]["error"] = error
                jobs[job_id]["error_count"] = jobs[job_id].get("error_count", 0) + 1

            jobs[job_id]["updated"] = datetime.now().isoformat()
            self._save_jobs(jobs)

    def _save_jobs(self, jobs: Dict):
        """Save jobs to file"""
        try:
            with open(self.jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)
        except Exception as e:
            print(f"Error saving jobs: {e}")

    def _process_job(self, job_id: str):
        """Process a job in background thread"""
        try:
            job = self.get_job(job_id)
            if not job:
                return

            self.update_job(job_id, "running", 5, "Starting download...")

            if job["type"] == "single_song":
                success = self._download_single_song(
                    job_id, job["url"], job["metadata"]
                )
            elif job["type"] == "playlist":
                success = self._download_playlist(job_id, job["url"], job["metadata"])
            else:
                self.update_job(job_id, "failed", 0, "Unknown job type")
                return

            if success:
                self.update_job(
                    job_id, "completed", 100, "Download completed successfully!"
                )
                self._add_to_history(job_id, "success")
            else:
                # Check if we should retry
                job = self.get_job(job_id)
                if job and job.get("error_count", 0) < job.get("max_retries", 3):
                    self.update_job(
                        job_id,
                        "queued",
                        0,
                        f"Retrying... (attempt {job.get('error_count', 0) + 1})",
                    )
                    # Retry after delay
                    threading.Timer(30.0, self._process_job, args=(job_id,)).start()
                else:
                    self.update_job(
                        job_id, "failed", 0, "Download failed after retries"
                    )
                    self._add_to_history(job_id, "failed")

        except Exception as e:
            self.update_job(job_id, "failed", 0, f"Error: {str(e)}")
            self._add_to_history(job_id, "error")

    def _download_single_song(self, job_id: str, url: str, metadata: Dict) -> bool:
        try:
            self.update_job(job_id, "running", 10, "Processing URL...")

            # Use search query if present
            search_query = metadata.get("search_query")
            if search_query:
                url = f"ytsearch1:{search_query}"

            artist = metadata.get("artist", "")
            album = metadata.get("album", "")

            if artist and album:
                output_template = f"/music/youtube-music/{self._clean_filename(artist)}/{self._clean_filename(album)}/%(title)s.%(ext)s"
            elif artist:
                output_template = f"/music/youtube-music/{self._clean_filename(artist)}/%(title)s.%(ext)s"
            else:
                output_template = "/music/youtube-music/%(uploader)s/%(title)s.%(ext)s"

            self.update_job(job_id, "running", 30, "Downloading audio...")

            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "320K",
                "--embed-thumbnail",
                "--add-metadata",
                "--no-playlist",
                "--output",
                output_template,
                "--no-warnings",
                url,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                self.update_job(job_id, "running", 80, "Triggering library scan...")
                self._trigger_navidrome_scan()
                self.update_job(job_id, "running", 95, "Finalizing...")
                return True
            else:
                error_msg = result.stderr[:200] if result.stderr else "Download failed"
                self.update_job(job_id, "failed", 0, f"Download error: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self.update_job(job_id, "failed", 0, "Download timeout (10 minutes)")
            return False
        except Exception as e:
            self.update_job(job_id, "failed", 0, f"Exception: {str(e)}")
            return False

    def _download_playlist(self, job_id: str, url: str, metadata: Dict) -> bool:
        """Download entire playlist using yt-dlp"""
        try:
            self.update_job(job_id, "running", 5, "Processing playlist URL...")

            # Handle YouTube Music URLs
            processed_url = self._process_url(url)

            playlist_name = metadata.get("playlist_name", "Downloaded Playlist")
            output_dir = f"/music/youtube-music/{self._clean_filename(playlist_name)}"

            self.update_job(job_id, "running", 15, "Starting playlist download...")

            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "320K",
                "--embed-thumbnail",
                "--add-metadata",
                "--yes-playlist",
                "--output",
                f"{output_dir}/%(uploader)s/%(playlist_title)s/%(playlist_index)02d - %(title)s.%(ext)s",
                "--no-warnings",
                processed_url,
            ]

            # Use subprocess.Popen for real-time progress updates
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Monitor progress
            progress = 15
            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    # Update progress based on output
                    if "[download]" in output and "%" in output:
                        try:
                            # Extract percentage from yt-dlp output
                            percent_start = output.find("%")
                            if percent_start > 0:
                                # Look backwards for the number
                                i = percent_start - 1
                                while i >= 0 and (
                                    output[i].isdigit() or output[i] == "."
                                ):
                                    i -= 1
                                percent_str = output[i + 1 : percent_start]
                                if percent_str:
                                    file_progress = float(percent_str)
                                    # Scale to overall progress (15-85%)
                                    progress = 15 + (file_progress * 0.7)
                                    self.update_job(
                                        job_id,
                                        "running",
                                        int(progress),
                                        f"Downloading playlist... {file_progress:.1f}%",
                                    )
                        except:
                            pass

            # Wait for completion
            process.wait()

            if process.returncode == 0:
                self.update_job(job_id, "running", 90, "Triggering library scan...")
                self._trigger_navidrome_scan()
                return True
            else:
                stderr = process.stderr.read()
                error_msg = stderr[:200] if stderr else "Playlist download failed"
                self.update_job(job_id, "failed", 0, f"Playlist error: {error_msg}")
                return False

        except Exception as e:
            self.update_job(job_id, "failed", 0, f"Exception: {str(e)}")
            return False

    def _process_url(self, url: str) -> str:
        """Convert YouTube Music URLs to regular YouTube URLs"""
        if "music.youtube.com" in url:
            if "watch?v=" in url:
                video_id = url.split("watch?v=")[1].split("&")[0]
                return f"https://youtube.com/watch?v={video_id}"
            elif "playlist?list=" in url:
                playlist_id = url.split("playlist?list=")[1].split("&")[0]
                return f"https://youtube.com/playlist?list={playlist_id}"
        return url

    def _clean_filename(self, name: str) -> str:
        """Clean filename for filesystem compatibility"""
        if not name:
            return "Unknown"

        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Replace multiple spaces with single space
        name = " ".join(name.split())

        # Limit length
        if len(name) > 100:
            name = name[:100].rsplit(" ", 1)[0]  # Break at word boundary

        return name.strip()

    def _trigger_navidrome_scan(self):
        """Trigger Navidrome library rescan"""
        try:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "navidrome",
                    "curl",
                    "-X",
                    "POST",
                    "http://localhost:4533/api/scanner/scan",
                ],
                timeout=10,
                capture_output=True,
            )
        except:
            pass  # Scan trigger is optional

    def _add_to_history(self, job_id: str, status: str):
        """Add completed job to history"""
        try:
            job = self.get_job(job_id)
            if not job:
                return

            # Load existing history
            history = []
            try:
                with open(self.history_file, "r") as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = []
            except:
                history = []

            # Add job to history
            history_entry = {
                "id": job_id,
                "type": job["type"],
                "url": job["url"],
                "status": status,
                "created": job["created"],
                "completed": datetime.now().isoformat(),
                "metadata": job.get("metadata", {}),
                "message": job.get("message", ""),
            }

            history.append(history_entry)

            # Keep only last 100 entries
            history = history[-100:]

            # Save updated history
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            print(f"Error adding to history: {e}")

    def get_download_history(self) -> list:
        """Get download history"""
        try:
            with open(self.history_file, "r") as f:
                history = json.load(f)
                return history if isinstance(history, list) else []
        except:
            return []

    def get_stats(self) -> Dict:
        """Get job statistics"""
        jobs = self.get_all_jobs()
        history = self.get_download_history()

        # Current job stats
        active_jobs = [j for j in jobs.values() if j["status"] in ["queued", "running"]]
        failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]

        # Historical stats
        total_downloads = len(history)
        successful_downloads = len([h for h in history if h["status"] == "success"])

        # Today's stats
        today = datetime.now().strftime("%Y-%m-%d")
        today_downloads = len([h for h in history if h["completed"].startswith(today)])

        return {
            "active_jobs": len(active_jobs),
            "failed_jobs": len(failed_jobs),
            "total_downloads": total_downloads,
            "successful_downloads": successful_downloads,
            "success_rate": (
                (successful_downloads / total_downloads * 100)
                if total_downloads > 0
                else 0
            ),
            "today_downloads": today_downloads,
        }

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed/failed jobs"""
        try:
            jobs = self.get_all_jobs()
            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

            cleaned_jobs = {}
            for job_id, job in jobs.items():
                job_time = datetime.fromisoformat(job["updated"]).timestamp()

                # Keep active jobs and recent completed/failed jobs
                if job["status"] in ["queued", "running"] or job_time > cutoff_time:
                    cleaned_jobs[job_id] = job

            self._save_jobs(cleaned_jobs)
            return len(jobs) - len(cleaned_jobs)  # Return number of cleaned jobs

        except Exception as e:
            print(f"Error cleaning up jobs: {e}")
            return 0

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job"""
        try:
            job = self.get_job(job_id)
            if job and job["status"] == "queued":
                self.update_job(job_id, "cancelled", 0, "Job cancelled by user")
                return True
            return False
        except:
            return False

    def retry_job(self, job_id: str) -> bool:
        """Retry a failed job"""
        try:
            job = self.get_job(job_id)
            if job and job["status"] == "failed":
                # Reset job status and retry
                self.update_job(job_id, "queued", 0, "Retrying job...")

                # Start processing in new thread
                thread = threading.Thread(target=self._process_job, args=(job_id,))
                thread.daemon = True
                thread.start()

                return True
            return False
        except:
            return False
