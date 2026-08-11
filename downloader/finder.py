import json
import shutil
from pathlib import Path
from typing import Optional, Union, List, Tuple, Set
from downloader.utils import INPUT_DIR, BASE_DIR, find_downloads_dirs


def is_valid_exportify_json(file_path: Path) -> bool:
    """
    Checks if a JSON file matches any Spotify playlist structure (Exportify, Spotify API, Soundiiz, etc.).
    """
    try:
        if not file_path.is_file() or file_path.suffix.lower() != ".json":
            return False
        if file_path.name in ["config.json", "package.json", "tsconfig.json", "progress.json"]:
            return False

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        if isinstance(data, list) and len(data) > 0:
            return True

        if isinstance(data, dict):
            for key in ["items", "tracks", "playlist", "songs", "data"]:
                if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                    return True
    except Exception:
        pass
    return False


def discover_playlist_json(provided_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """
    Discovers Exportify JSON playlist files across input/, project root, and Android Downloads folders,
    and presents a numbered selection menu to the user.
    """
    if provided_path:
        p = Path(provided_path).resolve()
        if p.exists() and is_valid_exportify_json(p):
            return p
        print(f"WARNING: Specified file '{provided_path}' does not exist or is not a valid Exportify JSON.")

    all_found: List[Tuple[Path, str]] = []
    seen_paths: Set[Path] = set()

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


