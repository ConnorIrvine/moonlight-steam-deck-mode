#!/usr/bin/env python3
"""Sunshine preparation and cleanup for the Steam Deck Moonlight app."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


DISPLAY_SCRIPT = Path(__file__).with_name("display_toggle.py")


def display_mode(option: str) -> None:
    command = [sys.executable, "-B", str(DISPLAY_SCRIPT), option]
    result = subprocess.run(command, check=False, timeout=35)
    if result.returncode:
        raise RuntimeError(f"Display switch {option} failed (exit {result.returncode}).")


def start() -> None:
    try:
        display_mode("--single")
    except Exception:
        # Sunshine does not run this prep command's undo if its do step fails.
        try:
            display_mode("--extend")
        except Exception as rollback_error:
            print(f"Could not restore Desktop Mode: {rollback_error}", file=sys.stderr)
        raise


def stop() -> None:
    steam_error = None
    try:
        os.startfile("steam://close/bigpicture")
        print("Requested normal Steam mode.")
    except OSError as error:
        steam_error = error
        print(f"Could not close Steam Big Picture: {error}", file=sys.stderr)
    # Restore the desktop even if Steam's URI handler is unavailable.
    display_mode("--extend")
    if steam_error:
        raise RuntimeError("Steam Big Picture cleanup failed.") from steam_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Prepare the PC for the Steam Deck stream")
    group.add_argument("--stop", action="store_true", help="Leave Big Picture and restore Desktop Mode")
    args = parser.parse_args()
    try:
        if args.start:
            start()
        else:
            stop()
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Steam Deck session error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
