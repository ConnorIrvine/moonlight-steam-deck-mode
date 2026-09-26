#!/usr/bin/env python3
"""Add/update this project's Steam Deck app in Sunshine's apps.json."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_APPS = Path(r"C:\Program Files\Sunshine\config\apps.json")
APP_NAME = "Steam Deck"


def app_entry() -> dict:
    session_script = ROOT / "moonlight_session.py"
    python = r"C:\Windows\py.exe"
    command = f'"{python}" -B "{session_script}"'
    return {
        "name": APP_NAME,
        "image-path": str(ROOT / "icons" / "SteamDeckMoonlight.png"),
        "working-dir": str(ROOT),
        "prep-cmd": [
            {"do": f"{command} --start", "undo": f"{command} --stop"}
        ],
        "detached": ["steam://open/bigpicture"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps-file", type=Path, default=DEFAULT_APPS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entry = app_entry()
    for required in (ROOT / "display_toggle.py", ROOT / "moonlight_session.py", ROOT / "icons" / "SteamDeckMoonlight.png"):
        if not required.is_file():
            parser.error(f"Missing required file: {required}")
    try:
        document = json.loads(args.apps_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        print(f"Could not read Sunshine app list: {error}", file=sys.stderr)
        return 1
    apps = document.get("apps")
    if not isinstance(apps, list):
        print("Sunshine app list has no 'apps' array.", file=sys.stderr)
        return 1
    matches = [index for index, item in enumerate(apps) if isinstance(item, dict) and item.get("name") == APP_NAME]
    if len(matches) > 1:
        print("Multiple 'Steam Deck' Sunshine apps exist; resolve duplicates before installing.", file=sys.stderr)
        return 1
    if matches:
        if apps[matches[0]] == entry:
            print("Sunshine Steam Deck app is already up to date.")
            return 0
        apps[matches[0]] = entry
        action = "Updated"
    else:
        apps.append(entry)
        action = "Added"

    if args.dry_run:
        print(f"Would {action.lower()} {APP_NAME} in {args.apps_file}")
        print(json.dumps(entry, indent=4))
        return 0

    backup = ROOT / f"apps.backup.{datetime.now():%Y%m%d-%H%M%S}.{uuid.uuid4().hex[:6]}.json"
    temporary = args.apps_file.with_name(args.apps_file.name + f".{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(args.apps_file, backup)
        temporary.write_text(json.dumps(document, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(args.apps_file)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"Could not update Sunshine app list: {error}", file=sys.stderr)
        return 1
    print(f"{action} {APP_NAME} in {args.apps_file}")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
