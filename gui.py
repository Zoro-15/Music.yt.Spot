#!/usr/bin/env python3
"""
Launcher script for Music.yt.Spot Android Web GUI.
Starts local web server and automatically opens browser.
"""

import sys
import time
import webbrowser
import threading
from downloader.utils import run_command, print_banner
from web_server import start_server, PORT


def open_browser(url):
    """Attempts termux-open-url first, falling back to python webbrowser module."""
    time.sleep(1.2)
    print(f"Opening Android browser: {url}")
    # Try termux-open-url if available
    code, _, _ = run_command(["termux-open-url", url])
    if code != 0:
        webbrowser.open(url)


def main():
    print_banner("Launching Music.yt.Spot Android Web GUI")
    url = f"http://127.0.0.1:{PORT}"
    print(f" Web GUI URL: {url}")
    print(" Press Ctrl+C to stop server.\n")

    # Start browser opener thread
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    # Start server on main thread
    try:
        start_server(PORT)
    except KeyboardInterrupt:
        print("\nWeb GUI Server stopped. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
