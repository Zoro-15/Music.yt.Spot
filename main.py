#!/usr/bin/env python3
"""
Unified CLI Entrypoint for Termux Playlist Audio Downloader.
"""

import sys
from downloader.spotify_mode import prepare_csv, run_download
from downloader.search_mode import search_and_download_song
from downloader.youtube_mode import download_from_link
from downloader.progress import show_status
from downloader.review_mode import run_review_mode
from downloader.utils import print_banner, clean_project_cache


def interactive_menu():
    """Displays an interactive terminal menu for users running 'python main.py'."""
    while True:
        print_banner("Termux Playlist Audio Downloader")
        print("  1. Spotify Playlist / Album / Track (Direct URL or Exportify JSON)")
        print("  2. Search & Download Song by Name")
        print("  3. Download from Universal Link (YouTube, YT Music, or Spotify)")
        print("  4. View Spotify Download Status")
        print("  5. Review Low-Confidence / Failed Tracks")
        print("  6. Clean / Reset Cache, CSV & Logs")
        print("  7. Exit")
        print("-" * 50)

        choice = input("Select an option [1-7]: ").strip()

        if choice == "1":
            url_or_json = input("\nEnter Spotify URL or press Enter to auto-discover local JSON: ").strip()
            if prepare_csv(url_or_json if url_or_json else None):
                start = input("\nStart downloading playlist tracks now? [Y/n]: ").strip()
                if start.lower() != "n":
                    run_download()
            break
        elif choice == "2":
            query = input("\nEnter Song Name or Search Query: ").strip()
            if query:
                search_and_download_song(query)
            break
        elif choice == "3":
            url = input("\nEnter YouTube / YT Music / Spotify URL: ").strip()
            if url:
                download_from_link(url)
            break
        elif choice == "4":
            show_status()
            input("\nPress Enter to return to menu...")
        elif choice == "5":
            run_review_mode()
            input("\nPress Enter to return to menu...")
        elif choice == "6":
            confirm = input("Reset CSV, progress logs, and cache? [y/N]: ").strip().lower()
            if confirm == "y":
                inc_out = input("Also clear all downloaded audio files in output/ folder? [y/N]: ").strip().lower() == "y"
                clean_project_cache(include_output=inc_out)
            input("\nPress Enter to return to menu...")

        elif choice == "7" or choice.lower() == "exit":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please enter a number between 1 and 7.")


def print_usage():
    print("""
Termux Playlist Audio Downloader — Usage Guide:

Interactive Mode:
  python main.py

Spotify URL / JSON Mode (Parallel Download Engine):
  python main.py spotify [url_or_json_path]

Search Song by Name:
  python main.py search "Song Name"

Universal Link Downloader (YouTube, YT Music, or Spotify):
  python main.py link "URL"

Interactive Review Mode:
  python main.py review

Clean Cache & Reset Data:
  python main.py clean

Status Report:
  python main.py status
""")


def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    cmd = sys.argv[1].lower()

    if cmd in ["-h", "--help", "help"]:
        print_usage()
    elif cmd in ["spotify", "sp"]:
        path_or_url = sys.argv[2] if len(sys.argv) > 2 else None
        if prepare_csv(path_or_url):
            run_download()
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("ERROR: Please provide a song name or search query.")
            print("Example: python main.py search \"No Handouts Amantej Hundal\"")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        search_and_download_song(query)
    elif cmd in ["link", "youtube", "video", "url"]:
        if len(sys.argv) < 3:
            print("ERROR: Please provide a valid YouTube, YT Music, or Spotify URL.")
            print("Example: python main.py link \"https://open.spotify.com/playlist/...\"")
            sys.exit(1)
        url = sys.argv[2]
        download_from_link(url)
    elif cmd == "review":
        run_review_mode()
    elif cmd == "clean":
        clean_project_cache(include_output="--all" in sys.argv or "-a" in sys.argv)
    elif cmd == "status":
        show_status()
    else:
        print(f"Unknown command: '{cmd}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
