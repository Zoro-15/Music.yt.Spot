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
    Discovers an Exportify JSON playlist file.
    Order of search:
    1. Provided path (if user passed CLI argument)
    2. input/ directory
    3. Android Downloads folders (~/storage/downloads/)
    """
    if provided_path:
        p = Path(provided_path).resolve()
        if p.exists() and is_valid_exportify_json(p):
            return p
        print(f"WARNING: Specified file '{provided_path}' does not exist or is not a valid Exportify JSON.")

    # 1. Search input/ directory
    input_jsons = [f for f in INPUT_DIR.glob("*.json") if is_valid_exportify_json(f)]
    
    # 1b. Search project root directory (BASE_DIR) for JSON files like Gedi.json
    root_jsons = [
        f for f in BASE_DIR.glob("*.json")
        if f.name != "config.json" and is_valid_exportify_json(f)
    ]
    
    all_local_jsons = input_jsons + [f for f in root_jsons if f not in input_jsons]
    
    if len(all_local_jsons) == 1:
        print(f"Found playlist JSON: {all_local_jsons[0].name}")
        return all_local_jsons[0]
    elif len(all_local_jsons) > 1:
        print("\nMultiple playlist JSON files found:")
        for idx, f in enumerate(all_local_jsons, 1):
            loc = "input/" if f.parent == INPUT_DIR else "root folder"
            print(f" [{idx}] {f.name} ({loc})")
        choice = input("\nSelect JSON file number (or press Enter for 1): ").strip()
        try:
            sel_idx = int(choice) - 1 if choice else 0
            if 0 <= sel_idx < len(all_local_jsons):
                return all_local_jsons[sel_idx]
        except ValueError:
            pass
        return all_local_jsons[0]

    # 2. Search Termux/Android Downloads folders
    print("No JSON found in input/. Searching Termux storage downloads...")
    downloads_dirs = find_downloads_dirs()
    found_in_downloads = []

    for d_dir in downloads_dirs:
        for f in d_dir.glob("*.json"):
            if is_valid_exportify_json(f):
                found_in_downloads.append(f)

    if len(found_in_downloads) == 1:
        target = found_in_downloads[0]
        dest = INPUT_DIR / target.name
        print(f"Discovered Exportify JSON in Downloads: {target.name}")
        print(f"Copying to input/{target.name}...")
        try:
            shutil.copy2(target, dest)
            return dest
        except Exception as e:
            print(f"Could not copy file: {e}")
            return target
    elif len(found_in_downloads) > 1:
        print("\nDiscovered multiple Exportify JSON files in Downloads:")
        for idx, f in enumerate(found_in_downloads, 1):
            print(f" [{idx}] {f.name} ({f.parent})")
        choice = input("\nSelect JSON file number to use: ").strip()
        try:
            sel_idx = int(choice) - 1
            if 0 <= sel_idx < len(found_in_downloads):
                target = found_in_downloads[sel_idx]
                dest = INPUT_DIR / target.name
                shutil.copy2(target, dest)
                return dest
        except Exception:
            pass

    return None
