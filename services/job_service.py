import os
import json
import threading
import subprocess
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional
import streamlit as st

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobManager:
    """Advanced job queue management for background music downloads"""

    def __init__(self):
        self.jobs_file = "/config/download_jobs.json"
        self.history_file = "/config/download_history.json"
        self.log_file = "/config/download_debug.log"
        self.ensure_files()

        # Setup file logging
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

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
            "last_error": "",
        }

        # Save job to queue
        jobs = self.get_all_jobs()
        jobs[job_id] = job
        self._save_jobs(jobs)

        logger.info(f"Added job {job_id}: {job_type} - {url}")

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
        except Exception as e:
            logger.error(f"Error reading jobs file: {e}")
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
                logger.info(f"Job {job_id} status: {status}")
            if progress is not None:
                jobs[job_id]["progress"] = progress
            if message:
                jobs[job_id]["message"] = message
            if error:
                jobs[job_id]["last_error"] = error
                jobs[job_id]["error_count"] = jobs[job_id].get("error_count", 0) + 1
                logger.error(f"Job {job_id} error: {error}")

            jobs[job_id]["updated"] = datetime.now().isoformat()
            self._save_jobs(jobs)

    def _save_jobs(self, jobs: Dict):
        """Save jobs to file"""
        try:
            with open(self.jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving jobs: {e}")

    def _process_job(self, job_id: str):
        """Process a job in background thread"""
        try:
            job = self.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            logger.info(f"Processing job {job_id}: {job['url']}")
            self.update_job(job_id, "running", 5, "Starting download...")

            # Pre-flight checks
            if not self._check_prerequisites():
                self.update_job(job_id, "failed", 0, "System prerequisites not met")
                return

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
                logger.info(f"Job {job_id} completed successfully")
            else:
                # Check if we should retry
                job = self.get_job(job_id)
                if job and job.get("error_count", 0) < job.get("max_retries", 3):
                    retry_count = job.get("error_count", 0) + 1
                    self.update_job(
                        job_id,
                        "queued",
                        0,
                        f"Retrying... (attempt {retry_count})",
                    )
                    logger.info(f"Job {job_id} scheduled for retry {retry_count}")

                    # Retry after delay (increase delay with each retry)
                    delay = 30.0 * retry_count
                    threading.Timer(delay, self._process_job, args=(job_id,)).start()
                else:
                    self.update_job(
                        job_id, "failed", 0, "Download failed after retries"
                    )
                    self._add_to_history(job_id, "failed")
                    logger.error(f"Job {job_id} failed after all retries")

        except Exception as e:
            logger.error(f"Exception in _process_job for {job_id}: {str(e)}")
            self.update_job(job_id, "failed", 0, f"Exception: {str(e)}")
            self._add_to_history(job_id, "error")

    def _check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        try:
            # Check if yt-dlp is available
            result = subprocess.run(
                ["which", "yt-dlp"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                logger.error("yt-dlp not found in PATH")
                return False

            # Check if output directory exists and is writable
            output_dir = "/music/youtube-music"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"Created output directory: {output_dir}")

            # Test write permissions
            test_file = os.path.join(output_dir, ".test_write")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                logger.error(f"Cannot write to output directory: {e}")
                return False

            return True

        except Exception as e:
            logger.error(f"Prerequisites check failed: {e}")
            return False

    def _download_single_song(self, job_id: str, url: str, metadata: Dict) -> bool:
        """Download a single song with enhanced error handling"""
        try:
            self.update_job(job_id, "running", 10, "Processing URL...")
            logger.info(f"Starting download for job {job_id}: {url}")

            # Use search query if present
            search_query = metadata.get("search_query")
            if search_query:
                url = f"ytsearch1:{search_query}"
                logger.info(f"Using search query: {search_query}")

            artist = metadata.get("artist", "")
            album = metadata.get("album", "")

            # Create output path
            if artist and album:
                output_template = f"/music/youtube-music/{self._clean_filename(artist)}/{self._clean_filename(album)}/%(title)s.%(ext)s"
            elif artist:
                output_template = f"/music/youtube-music/{self._clean_filename(artist)}/%(title)s.%(ext)s"
            else:
                output_template = "/music/youtube-music/%(uploader)s/%(title)s.%(ext)s"

            # Ensure output directory exists
            output_dir = os.path.dirname(
                output_template.replace("%(title)s.%(ext)s", "")
            )
            os.makedirs(output_dir, exist_ok=True)

            self.update_job(job_id, "running", 30, "Downloading audio...")

            # Enhanced yt-dlp command with better error handling
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
                "--no-check-certificate",  # Skip SSL verification if needed
                "--cookies-from-browser",
                "firefox",
                "--user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--retries",
                "3",
                "--fragment-retries",
                "3",
                url,
            ]

            logger.info(f"Running command: {' '.join(cmd)}")

            # Run with detailed logging
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd="/tmp",  # Set working directory
            )

            # Log detailed output
            if result.stdout:
                logger.info(f"yt-dlp stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"yt-dlp stderr: {result.stderr}")

            if result.returncode == 0:
                self.update_job(job_id, "running", 80, "Triggering library scan...")
                self._trigger_navidrome_scan()
                self.update_job(job_id, "running", 95, "Finalizing...")
                logger.info(f"Download successful for job {job_id}")
                return True
            else:
                error_msg = f"yt-dlp failed with code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr[:200]}"
                self.update_job(job_id, "failed", 0, error_msg)
                logger.error(f"Download failed for job {job_id}: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            error_msg = "Download timeout (10 minutes)"
            self.update_job(job_id, "failed", 0, error_msg)
            logger.error(f"Timeout for job {job_id}")
            return False
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            self.update_job(job_id, "failed", 0, error_msg)
            logger.error(f"Exception in download for job {job_id}: {e}")
            return False

    def _download_playlist(self, job_id: str, url: str, metadata: Dict) -> bool:
        """Download entire playlist with better error handling"""
        try:
            self.update_job(job_id, "running", 5, "Processing playlist URL...")
            logger.info(f"Starting playlist download for job {job_id}: {url}")

            # Handle YouTube Music URLs
            processed_url = self._process_url(url)
            logger.info(f"Processed URL: {processed_url}")

            playlist_name = metadata.get("playlist_name", "Downloaded Playlist")
            output_dir = f"/music/youtube-music/{self._clean_filename(playlist_name)}"
            os.makedirs(output_dir, exist_ok=True)

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
                "--no-check-certificate",
                "--cookies-from-browser",
                "firefox",
                "--user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--retries",
                "3",
                "--fragment-retries",
                "3",
                processed_url,
            ]

            logger.info(f"Running playlist command: {' '.join(cmd)}")

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
            stdout_lines = []
            stderr_lines = []

            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    stdout_lines.append(output)
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

            # Wait for completion and collect stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                stderr_lines.append(stderr_output)

            process.wait()

            # Log all output
            if stdout_lines:
                logger.info(f"Playlist stdout: {''.join(stdout_lines)}")
            if stderr_lines:
                logger.warning(f"Playlist stderr: {''.join(stderr_lines)}")

            if process.returncode == 0:
                self.update_job(job_id, "running", 90, "Triggering library scan...")
                self._trigger_navidrome_scan()
                logger.info(f"Playlist download successful for job {job_id}")
                return True
            else:
                error_msg = f"Playlist download failed with code {process.returncode}"
                if stderr_lines:
                    error_msg += f": {''.join(stderr_lines)[:200]}"
                self.update_job(job_id, "failed", 0, error_msg)
                logger.error(f"Playlist download failed for job {job_id}: {error_msg}")
                return False

        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            self.update_job(job_id, "failed", 0, error_msg)
            logger.error(f"Exception in playlist download for job {job_id}: {e}")
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
            # Try multiple approaches
            endpoints = [
                "http://192.168.1.39:4533/api/scanner/scan",
                "http://localhost:4533/api/scanner/scan",
                "http://navidrome:4533/api/scanner/scan",
            ]

            for endpoint in endpoints:
                try:
                    result = subprocess.run(
                        ["curl", "-X", "POST", "--connect-timeout", "5", endpoint],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        logger.info(f"Navidrome scan triggered via {endpoint}")
                        return
                except:
                    continue

            # Try Docker exec as fallback
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
            logger.info("Navidrome scan triggered via docker exec")

        except Exception as e:
            logger.warning(f"Failed to trigger Navidrome scan: {e}")

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
                "error_count": job.get("error_count", 0),
                "last_error": job.get("last_error", ""),
            }

            history.append(history_entry)

            # Keep only last 100 entries
            history = history[-100:]

            # Save updated history
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            logger.error(f"Error adding to history: {e}")

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
            logger.error(f"Error cleaning up jobs: {e}")
            return 0

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job"""
        try:
            job = self.get_job(job_id)
            if job and job["status"] in ["queued", "running"]:
                self.update_job(job_id, "cancelled", 0, "Job cancelled by user")
                logger.info(f"Job {job_id} cancelled by user")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False

    def retry_job(self, job_id: str) -> bool:
        """Retry a failed job"""
        try:
            job = self.get_job(job_id)
            if job and job["status"] == "failed":
                # Reset job status and retry
                job["error_count"] = 0
                job["last_error"] = ""
                self.update_job(job_id, "queued", 0, "Manual retry requested...")

                # Start processing in new thread
                thread = threading.Thread(target=self._process_job, args=(job_id,))
                thread.daemon = True
                thread.start()

                logger.info(f"Job {job_id} manually retried")
                return True
            return False
        except Exception as e:
            logger.error(f"Error retrying job {job_id}: {e}")
            return False

    def debug_job(self, job_id: str) -> Dict:
        """Get detailed debug information for a job"""
        job = self.get_job(job_id)
        if not job:
            return {"error": "Job not found"}

        debug_info = {
            "job_details": job,
            "system_checks": {
                "yt_dlp_available": self._check_yt_dlp(),
                "output_dir_writable": self._check_output_dir(),
                "navidrome_reachable": self._check_navidrome(),
            },
            "recent_logs": self._get_recent_logs(job_id),
        }

        return debug_info

    def _check_yt_dlp(self) -> bool:
        """Check if yt-dlp is available"""
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_output_dir(self) -> bool:
        """Check if output directory is writable"""
        try:
            test_file = "/music/youtube-music/.test_write"
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except:
            return False

    def _check_navidrome(self) -> bool:
        """Check if Navidrome is reachable"""
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-f",
                    "--connect-timeout",
                    "5",
                    "http://192.168.1.39:4533/ping",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except:
            return False

    def _get_recent_logs(self, job_id: str) -> list:
        """Get recent log entries for a job"""
        try:
            logs = []
            if os.path.exists(self.log_file):
                with open(self.log_file, "r") as f:
                    for line in f:
                        if job_id in line:
                            logs.append(line.strip())
            return logs[-10:]  # Return last 10 relevant log entries
        except:
            return []
