import json
import shutil
from pathlib import Path
from downloader.utils import INPUT_DIR, BASE_DIR


def is_valid_exportify_json(file_path):
    """
    Checks if a JSON file matches Exportify structure (list of track objects with 'name' or 'artists').
    """
    try:
        if not file_path.is_file():
            return False
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict) and ("name" in first or "artists" in first or "album" in first):
                return True
    except Exception:
        pass
    return False


def find_downloads_dirs():
    """
    Returns candidate download paths for Termux / Android.
    """
    home = Path.home()
    candidates = [
        home / "storage" / "downloads",
        home / "storage" / "shared" / "Download",
        Path("/sdcard/Download"),
        Path("/storage/emulated/0/Download"),
    ]
    return [d for d in candidates if d.exists() and d.is_dir()]


def discover_playlist_json(provided_path=None):
    """
    Discovers Exportify JSON playlist files across input/, project root, and Android Downloads folders,
    and presents a numbered selection menu to the user.
    """
    if provided_path:
        p = Path(provided_path).resolve()
        if p.exists() and is_valid_exportify_json(p):
            return p
        print(f"WARNING: Specified file '{provided_path}' does not exist or is not a valid Exportify JSON.")

    all_found = []
    seen_paths = set()

    # 1. Search input/ directory
    for f in INPUT_DIR.glob("*.json"):
        if is_valid_exportify_json(f) and f.resolve() not in seen_paths:
            all_found.append((f, "input/"))
            seen_paths.add(f.resolve())

    # 2. Search project root directory (BASE_DIR)
    for f in BASE_DIR.glob("*.json"):
        if f.name != "config.json" and is_valid_exportify_json(f) and f.resolve() not in seen_paths:
            all_found.append((f, "project root"))
            seen_paths.add(f.resolve())

    # 3. Search Android Downloads folders
    for d_dir in find_downloads_dirs():
        for f in d_dir.glob("*.json"):
            if is_valid_exportify_json(f) and f.resolve() not in seen_paths:
                all_found.append((f, "Downloads"))
                seen_paths.add(f.resolve())

    if not all_found:
        return None

    print("\n" + "=" * 60)
    print(" Available Spotify Playlist JSON Files Found:")
    print("=" * 60)
    for idx, (f_path, location) in enumerate(all_found, 1):
        print(f"  [{idx}] {f_path.name}  (Location: {location})")
    print("=" * 60)

    choice = input(f"\nSelect JSON file number [1-{len(all_found)}] (or press Enter for 1): ").strip()
    sel_idx = 0
    if choice and choice.isdigit():
        val = int(choice) - 1
        if 0 <= val < len(all_found):
            sel_idx = val

    selected_file, location = all_found[sel_idx]
    print(f"\nSelected: {selected_file.name} ({location})")

    if location == "Downloads":
        dest = INPUT_DIR / selected_file.name
        try:
            shutil.copy2(selected_file, dest)
            return dest
        except Exception:
            return selected_file

    return selected_file

