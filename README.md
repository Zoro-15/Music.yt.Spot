# Termux Playlist Audio Downloader 🎵▶️

A high-performance, multi-threaded **Android / Termux** tool for downloading audio from **Spotify playlists** (exported as JSON via Exportify), **YouTube / YouTube Music playlists & albums**, **music videos**, and **single songs by name** using `yt-dlp` and `FFmpeg`.

---

## 🌟 Key Features

- 🔎 **Search & Download Song by Name**: Download any track by typing its name (`python main.py search "Song Name"`). The script automatically finds the best YouTube Music match, downloads native audio, crops 1:1 cover art, embeds metadata, fetches synced lyrics, and syncs to Android Music.
- 🔗 **Universal Link Downloader**: Directly handles YouTube Playlists, YouTube Music Playlists, YouTube Music Albums (`music.youtube.com/playlist?list=...`), Music Videos, and single videos.
- ⚡ **8x Parallel Downloads by Default**: Multi-threaded processing (`8` concurrent workers) slashes download times by up to 80%.
- 🎵 **YouTube Music (YTM) Topic Priority**: Multi-pass search targets official YouTube Music topic tracks (`ytmusic:`) first, eliminating intro/outro video skits.
- 🎤 **Synchronized Lyrics (.lrc)**: Integrates with LRCLIB to fetch synchronized lyrics alongside audio files.
- 🖼️ **1:1 Square Cover Art Cropping**: Automatically crops 16:9 YouTube thumbnails to a 1:1 square aspect ratio via FFmpeg to prevent letterboxing on mobile player screens.
- 📲 **Android Music Folder Auto-Sync**: Automatically copies finished tracks to Android's native `/sdcard/Music` directory and triggers the Android Media Scanner broadcast.
- 🛠️ **Interactive Review Mode**: Interactively review flagged tracks (`python main.py review`) to select alternate candidates or paste direct YouTube URLs.
- ⚙️ **Configurable (`config.json`)**: Easily tweak worker threads, confidence thresholds, lyrics, and sync behavior.
- ❌ **Zero Spotify Developer Credentials Required**: Export playlists using Exportify without registering a Spotify Developer account.

---

## 📁 Repository Structure

```text
spotify-ytdlp-downloader/
│
├── README.md                 # Complete documentation
├── requirements.txt           # Python dependencies (yt-dlp)
├── config.json                # User settings (max_workers=5, etc.)
├── .gitignore                 # Shields user files & downloads from git
│
├── main.py                    # Unified CLI & interactive menu
├── prepare.py                 # Wrapper for Spotify JSON parser
├── download.py                # Wrapper for Spotify download loop
├── status.py                  # Wrapper for status report
│
├── downloader/                # Core Python package
│   ├── __init__.py
│   ├── config.py              # Configuration manager
│   ├── finder.py              # Exportify JSON auto-discovery helper
│   ├── search_mode.py        # Single song search by name
│   ├── spotify_mode.py        # 5x Parallel Spotify workflow
│   ├── youtube_mode.py        # Universal YouTube & YT Music link downloader
│   ├── matcher.py             # YTM & multi-pass search scoring engine
│   ├── lyrics.py              # LRCLIB synced lyrics engine
│   ├── review_mode.py        # Interactive CLI review tool
│   ├── ffmpeg_tagger.py       # Lossless FFmpeg metadata tagger & square cropper
│   ├── progress.py            # Resume state manager & status report
│   └── utils.py               # Filename sanitizer & Android sync helpers
│
├── input/                     # Place Exportify JSON files here
├── data/                      # Auto-generated CSV, progress state, & logs
└── output/                    # Downloaded M4A/Opus files, artwork, & .lrc lyrics
```

---

## 🚀 Quick Start for Termux (Android)

### 1. Update Termux Packages
```bash
pkg update && pkg upgrade -y
```

### 2. Install Prerequisites
```bash
pkg install python ffmpeg git -y
termux-setup-storage
```
*(Accept storage permission on your phone)*

### 3. Install / Update `yt-dlp`
```bash
python -m pip install -U yt-dlp
```

---

## 🛠️ Installation & Setup

Clone this repository and enter the directory:
```bash
git clone https://github.com/Zoro-15/Music.yt.Spot.git
cd Music.yt.Spot
python -m pip install -r requirements.txt
```

---

## 🧹 Reset & Clean Cache (Optional)

Before starting a fresh playlist download, you can clear previous CSV files, progress logs, cache, and temporary data by running:

```bash
python main.py clean
```
*(Or use shortcut wrapper: `python clean.py`)*

To also clear the downloaded files in `output/`:
```bash
python main.py clean --all
```

---

## 🎮 Usage Guide

### Interactive Menu
Launch `main.py`:
```bash
python main.py
```
Menu:
```text
======================================================================
 Termux Playlist Audio Downloader
======================================================================

  1. Spotify Playlist JSON (Exportify mode)
  2. Search & Download Song by Name
  3. Download from Link (YT / YT Music Playlist, Album, or Video)
  4. View Spotify Download Status
  5. Review Low-Confidence / Failed Tracks
  6. Exit
--------------------------------------------------
Select an option [1-6]:
```

---

### Search & Download Song by Name
Type any song name to search and download instantly:
```bash
python main.py search "No Handouts Amantej Hundal"
```

---

### Universal Link Downloader (YouTube / YT Music Playlists, Albums, Videos)
Download YouTube playlists, YouTube Music playlists, YouTube Music albums, or video links:
```bash
python main.py link "https://music.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
```

### Spotify Playlist Mode (8x Parallel)

#### Step 1: Export Spotify Playlist as JSON
1. Open [Exportify](https://exportify.madebyruuen.com/) in your browser.
2. Log in and export your Spotify playlist as **JSON**.
3. The downloaded JSON file (e.g., `Gedi.json` or `playlist.json`) lands on your phone/computer.

#### How to Export & Use `cookies.txt` (If Requested by YouTube)

If YouTube challenges your IP address with bot detection, exporting cookies takes less than 1 minute:

1. **Install Browser Extension**:
   - Chrome / Brave / Edge: Install **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)** extension.
   - Firefox / Kiwi Browser (Android): Install **cookies.txt** extension.
2. **Export Cookies**:
   - Go to [YouTube.com](https://www.youtube.com) (make sure you are logged in).
   - Click the extension icon and click **Export** (saves a file named `cookies.txt`).
3. **Copy to Termux**:
   - In Termux, copy `cookies.txt` into your `Music.yt.Spot` repository directory:
     ```bash
     cp ~/storage/downloads/cookies.txt ~/Music.yt.Spot/
     ```
   - *The downloader will automatically detect `cookies.txt` and use it for all downloads!*

---

#### Step 2: Provide the JSON to the Script (3 Easy Methods)

Choose **any** of the following 3 ways to provide your JSON file:

- **Method A — Automatic Downloads Discovery (Easiest for Android / Termux)**:
  Leave the exported JSON right in your phone's `Downloads` folder (`~/storage/downloads/`). Simply run:
  ```bash
  python main.py spotify
  ```
  *The script will automatically detect and use the Exportify JSON from your Downloads folder!*

- **Method B — Place in Project Directory or `input/` Folder**:
  Copy or move your JSON file (e.g. `Gedi.json`) into the `input/` folder or directly into the `Music.yt.Spot` repository folder:
  ```text
  Music.yt.Spot/
  ├── Gedi.json   <-- (or inside input/Gedi.json)
  ```
  Then run:
  ```bash
  python main.py spotify
  ```

- **Method C — Pass File Path via Command Line**:
  Specify your JSON filename or file path directly when running the command:
  ```bash
  python main.py spotify Gedi.json
  ```
  or
  ```bash
  python main.py spotify /sdcard/Download/Gedi.json
  ```

#### Prevent Termux Sleep During Downloads (Recommended for Large Playlists)
```bash
termux-wake-lock
```
*(When finished: `termux-wake-unlock`)*

---

### Interactive Track Review Mode
If any tracks are flagged in `data/review.txt` (`score < 70`), run:
```bash
python main.py review
```

---

## ⚙️ Configuration (`config.json`)

Created automatically on first run:
```json
{
  "max_workers": 8,
  "min_score": 70,
  "ytmusic_priority": true,
  "fetch_lyrics": true,
  "square_crop_artwork": true,
  "auto_sync_android_music": true
}
```

---

## 🎧 Audio & Quality Philosophy

- **Native Streams**: AAC (`.m4a`) preferred, Opus (`.webm`) fallback. Zero lossy MP3 re-encoding.
- **FFmpeg Stream Copy**: Injects title, artist, and album tags using `-c copy`.
- **1:1 Square Covers**: Crops letterboxed thumbnails into clean square album art.
- **Synced Lyrics**: Automatically saves `.lrc` files alongside songs.

---

## 📜 License & Disclaimer

Uses `yt-dlp` and `FFmpeg`. Users are responsible for complying with YouTube's Terms of Service and applicable copyright regulations in their jurisdiction. Only download content you own or are authorized to process.
