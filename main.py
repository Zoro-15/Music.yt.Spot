#!/usr/bin/env python3
"""
Unified CLI Entrypoint for Termux Playlist Audio Downloader.
"""

import sys
import argparse
from downloader.spotify_mode import prepare_csv, run_download
from downloader.search_mode import search_and_download_song
from downloader.youtube_mode import download_from_link
from downloader.progress import show_status
from downloader.review_mode import run_review_mode
from downloader.utils import print_banner, clean_project_cache
from downloader.config import load_config, save_config


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


def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(
        description="Termux Playlist Audio Downloader — High performance CLI audio tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available Commands")

    # spotify subcommand
    sp_parser = subparsers.add_parser("spotify", aliases=["sp"], help="Download Spotify playlist / album / track")
    sp_parser.add_argument("source", nargs="?", default=None, help="Spotify URL or path to Exportify JSON file")
    sp_parser.add_argument("-w", "--workers", type=int, default=None, help="Override parallel download thread count")

    # search subcommand
    search_parser = subparsers.add_parser("search", help="Search song by name and download audio")
    search_parser.add_argument("query", nargs="+", help="Song title or artist query")

    # link subcommand
    link_parser = subparsers.add_parser("link", aliases=["youtube", "video", "url"], help="Download from YouTube / YT Music / Spotify URL")
    link_parser.add_argument("url", help="Media URL to download")

    # review subcommand
    subparsers.add_parser("review", help="Interactively review low-confidence track matches")

    # clean subcommand
    clean_parser = subparsers.add_parser("clean", help="Clean cache, logs, and temporary files")
    clean_parser.add_argument("-a", "--all", action="store_true", help="Also clear output directory")

    # status subcommand
    subparsers.add_parser("status", help="Display download progress status report")

    args = parser.parse_args()

    cmd = args.command.lower() if args.command else None

    if cmd in ["spotify", "sp"]:
        if getattr(args, "workers", None):
            cfg = load_config()
            cfg["max_workers"] = args.workers
            save_config(cfg)
        if prepare_csv(args.source):
            run_download()
    elif cmd == "search":
        q = " ".join(args.query) if isinstance(args.query, list) else args.query
        search_and_download_song(q)
    elif cmd in ["link", "youtube", "video", "url"]:
        download_from_link(args.url)
    elif cmd == "review":
        run_review_mode()
    elif cmd == "clean":
        clean_project_cache(include_output=args.all)
    elif cmd == "status":
        show_status()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
