import csv
import json
import os
import shutil
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from downloader.config import load_config, save_config
from downloader.finder import discover_playlist_json, find_downloads_dirs, is_valid_exportify_json
from downloader.spotify_mode import prepare_csv, run_download, download_single_spotify_track
from downloader.search_mode import search_and_download_song
from downloader.youtube_mode import download_from_link
from downloader.progress import load_progress
from downloader.utils import (
    BASE_DIR,
    INPUT_DIR,
    DATA_DIR,
    TRACKS_CSV,
    PROGRESS_FILE,
    REVIEW_FILE,
    FAILED_FILE,
    clean_project_cache,
)

PORT = 8000
WEBUI_DIR = BASE_DIR / "webui"

# Global state tracker for background downloads
download_state = {
    "is_running": False,
    "current_task": "Idle",
    "last_error": "",
}
state_lock = threading.Lock()


def run_background_task(task_func, task_name, *args, **kwargs):
    """Executes a function in a background thread and manages download_state."""
    def worker():
        with state_lock:
            download_state["is_running"] = True
            download_state["current_task"] = task_name
            download_state["last_error"] = ""
        try:
            task_func(*args, **kwargs)
        except Exception as e:
            with state_lock:
                download_state["last_error"] = str(e)
        finally:
            with state_lock:
                download_state["is_running"] = False
                download_state["current_task"] = "Idle"

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


class MusicGUIRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for Music.yt.Spot REST API and static web UI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEBUI_DIR), **kwargs)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body_json(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length).decode("utf-8")
                return json.loads(body)
        except Exception:
            pass
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.path = "/index.html"
            return super().do_GET()

        # ----------------------------------------------------
        # REST API ENDPOINTS
        # ----------------------------------------------------
        if path == "/api/status":
            total = 0
            if TRACKS_CSV.exists():
                with open(TRACKS_CSV, "r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    total = sum(1 for _ in reader)

            prog = load_progress()
            success = sum(1 for x in prog.values() if x.get("status") == "success")
            failed = sum(1 for x in prog.values() if x.get("status") == "failed")
            review = sum(1 for x in prog.values() if x.get("status") == "review")
            processed = success + failed + review
            remaining = max(0, total - processed) if total > 0 else 0

            with state_lock:
                is_running = download_state["is_running"]
                current_task = download_state["current_task"]
                last_error = download_state["last_error"]

            self._send_json({
                "total": total,
                "processed": processed,
                "success": success,
                "failed": failed,
                "review": review,
                "remaining": remaining,
                "is_running": is_running,
                "current_task": current_task,
                "last_error": last_error,
            })
            return

        elif path == "/api/find-jsons":
            all_found = []
            seen_paths = set()

            for f in INPUT_DIR.glob("*.json"):
                if is_valid_exportify_json(f) and f.resolve() not in seen_paths:
                    all_found.append({"name": f.name, "path": str(f.resolve()), "location": "input/"})
                    seen_paths.add(f.resolve())

            for f in BASE_DIR.glob("*.json"):
                if f.name != "config.json" and is_valid_exportify_json(f) and f.resolve() not in seen_paths:
                    all_found.append({"name": f.name, "path": str(f.resolve()), "location": "root folder"})
                    seen_paths.add(f.resolve())

            for d_dir in find_downloads_dirs():
                for f in d_dir.glob("*.json"):
                    if is_valid_exportify_json(f) and f.resolve() not in seen_paths:
                        all_found.append({"name": f.name, "path": str(f.resolve()), "location": "Downloads"})
                        seen_paths.add(f.resolve())

            self._send_json({"jsons": all_found})
            return

        elif path == "/api/progress-details":
            prog = load_progress()
            tracks = []
            if TRACKS_CSV.exists():
                with open(TRACKS_CSV, "r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        idx = row["index"]
                        p_data = prog.get(str(idx), {})
                        tracks.append({
                            "index": idx,
                            "title": row["title"],
                            "artist": row["artist"],
                            "album": row["album"],
                            "status": p_data.get("status", "pending"),
                            "score": p_data.get("score", 0),
                            "youtube_title": p_data.get("youtube_title", ""),
                            "youtube_url": p_data.get("youtube_url", ""),
                        })
            self._send_json({"tracks": tracks})
            return

        elif path == "/api/review-tracks":
            items = []
            if REVIEW_FILE.exists():
                with open(REVIEW_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split("\t")
                        if len(parts) >= 6:
                            items.append({
                                "index": parts[0],
                                "title": parts[1],
                                "artist": parts[2],
                                "score": parts[3],
                                "yt_title": parts[4],
                                "url": parts[5],
                            })
            self._send_json({"review_tracks": items})
            return

        elif path == "/api/config":
            self._send_json(load_config())
            return

        # Serve static webui files
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body_json()

        if path == "/api/prepare-spotify":
            json_path = body.get("json_path")
            ok = prepare_csv(json_path)
            self._send_json({"success": ok})
            return

        elif path == "/api/start-spotify":
            with state_lock:
                if download_state["is_running"]:
                    self._send_json({"error": "A download task is already running"}, status=400)
                    return

            run_background_task(run_download, "Spotify Playlist Download")
            self._send_json({"success": True, "message": "Spotify download started"})
            return

        elif path == "/api/search-song":
            query = body.get("query", "").strip()
            if not query:
                self._send_json({"error": "Missing search query"}, status=400)
                return

            with state_lock:
                if download_state["is_running"]:
                    self._send_json({"error": "A download task is already running"}, status=400)
                    return

            run_background_task(search_and_download_song, f"Song Search: {query}", query)
            self._send_json({"success": True, "message": f"Searching and downloading: {query}"})
            return

        elif path == "/api/download-link":
            url = body.get("url", "").strip()
            if not url:
                self._send_json({"error": "Missing URL"}, status=400)
                return

            with state_lock:
                if download_state["is_running"]:
                    self._send_json({"error": "A download task is already running"}, status=400)
                    return

            run_background_task(download_from_link, f"Link Download: {url}", url)
            self._send_json({"success": True, "message": "Link download started"})
            return

        elif path == "/api/resolve-review":
            idx = body.get("index")
            url = body.get("url")
            title = body.get("title", "Reviewed Track")
            artist = body.get("artist", "")

            if not idx or not url:
                self._send_json({"error": "Missing index or url"}, status=400)
                return

            track = {"title": title, "artist": artist, "album": ""}
            status, res = download_single_spotify_track(track, int(idx))
            if status == "success":
                prog = load_progress()
                prog[str(idx)] = {
                    "title": title,
                    "artist": artist,
                    "album": "",
                    "status": "success",
                    "youtube_url": url,
                }
                from downloader.progress import save_progress
                save_progress(prog)
                self._send_json({"success": True})
            else:
                self._send_json({"success": False, "error": "Download failed"}, status=500)
            return

        elif path == "/api/config":
            save_config(body)
            self._send_json({"success": True, "config": body})
            return

        elif path == "/api/clean":
            inc_out = body.get("include_output", False)
            clean_project_cache(include_output=inc_out)
            self._send_json({"success": True})
            return

        self._send_json({"error": "Not Found"}, status=404)


def start_server(port=PORT):
    """Starts the Music.yt.Spot Web GUI Server."""
    WEBUI_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("0.0.0.0", port), MusicGUIRequestHandler)
    print(f"Music.yt.Spot Web GUI Server running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()
