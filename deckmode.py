#!/usr/bin/env python3
"""One-file Windows installer and Sunshine session helper for Moonlight Deck Mode.

With no arguments, checks prerequisites and offers to install. --check and
--dry-run never modify the display, Sunshine, Steam, or the filesystem.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import deckmode_core as core
import display_toggle as win


PROGRAM_DIR = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "MoonlightDeckMode"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "MoonlightDeckMode"
EXECUTABLE_NAME = "MoonlightDeckMode.exe"
ART_NAME = "SteamDeckMoonlight.png"
VERSION = "1.0.0-beta.2"
QDC_ALL_PATHS = 1
SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x20
SDC_VALIDATE = 0x40
SDC_ALLOW_CHANGES = 0x400
STATE_VERSION = 1


class DeckModeError(RuntimeError):
    pass


def resource(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / "icons" / name


def current_display(api):
    primary, active = win.primary_and_active(api)
    current = win.current_mode(api, primary.DeviceName)
    if current is None:
        raise DeckModeError("Could not read the main display mode.")
    return primary, active, current


def modes_for(api, name: str) -> list[tuple[core.Mode, win.DEVMODEW]]:
    result = []
    index = 0
    while True:
        mode = win.DEVMODEW()
        mode.dmSize = ctypes.sizeof(mode)
        if not api.EnumDisplaySettingsW(name, index, ctypes.byref(mode)):
            break
        result.append((core.Mode(mode.dmPelsWidth, mode.dmPelsHeight,
                                 mode.dmDisplayFrequency, mode.dmBitsPerPel), mode))
        index += 1
    return result


def choose_display_mode(api, name: str, current) -> tuple[core.Mode, win.DEVMODEW]:
    available = modes_for(api, name)
    selected = core.choose_mode(
        [mode for mode, _ in available],
        core.Mode(current.dmPelsWidth, current.dmPelsHeight,
                  current.dmDisplayFrequency, current.dmBitsPerPel),
    )
    return next(pair for pair in available if pair[0] == selected)


def query_config(api, flags=win.QDC_ONLY_ACTIVE_PATHS):
    for _ in range(3):
        path_count = win.wintypes.UINT()
        mode_count = win.wintypes.UINT()
        error = api.GetDisplayConfigBufferSizes(flags, ctypes.byref(path_count), ctypes.byref(mode_count))
        if error:
            raise DeckModeError(f"Could not query display configuration (Windows error {error}).")
        paths = (win.PATH_INFO * path_count.value)()
        modes = (win.MODE_INFO * mode_count.value)()
        error = api.QueryDisplayConfig(flags, ctypes.byref(path_count), paths,
                                       ctypes.byref(mode_count), modes, None)
        if not error:
            return list(paths[:path_count.value]), list(modes[:mode_count.value])
        if error != 122:
            raise DeckModeError(f"Could not read display configuration (Windows error {error}).")
    raise DeckModeError("Displays changed during detection; try again.")


def connected_count(api) -> int:
    paths, _ = query_config(api, QDC_ALL_PATHS)
    targets = set()
    for path in paths:
        target = path.targetInfo
        if target.targetAvailable:
            targets.add((target.adapterId.LowPart, target.adapterId.HighPart, target.id))
    return len(targets)


def steam_path() -> Path | None:
    try:
        import winreg
        for hive, key_name, value in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamExe"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    found = Path(winreg.QueryValueEx(key, value)[0])
                    if found.is_dir():
                        found /= "steam.exe"
                    if found.is_file():
                        return found
            except OSError:
                pass
    except ImportError:
        pass
    found = shutil.which("steam.exe")
    return Path(found) if found else None


def steam_uri_registered() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "steam") as key:
            winreg.QueryValueEx(key, "URL Protocol")
        return True
    except (ImportError, OSError):
        return False


def sunshine_apps(explicit: Path | None = None) -> Path:
    if explicit:
        candidates = [explicit]
    else:
        roots = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
                 Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))]
        if "ProgramFiles(x86)" in os.environ:
            roots.append(Path(os.environ["ProgramFiles(x86)"]))
        if "APPDATA" in os.environ:
            roots.append(Path(os.environ["APPDATA"]))
        candidates = []
        for root in roots:
            config_dir = root / "Sunshine" / "config"
            if root == Path(os.environ.get("APPDATA", "")):
                config_dir = root / "Sunshine"
            config = config_dir / "sunshine.conf"
            app_name = "apps.json"
            if config.is_file():
                for line in config.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                    key, separator, value = line.partition("=")
                    if separator and key.strip() == "file_apps":
                        app_name = os.path.expandvars(value.split("#", 1)[0].strip().strip('"'))
                        break
            candidate = Path(app_name)
            candidates.append(candidate if candidate.is_absolute() else config_dir / candidate)
    found = [p.resolve() for p in candidates if p.is_file()]
    found = list(dict.fromkeys(found))
    if not found:
        raise DeckModeError("Sunshine apps.json was not found. Use --apps-file PATH for a custom installation.")
    if len(found) > 1:
        raise DeckModeError("Several Sunshine app lists were found. Use --apps-file PATH to select the active one.")
    return found[0]


def check(apps_file: Path | None = None) -> dict:
    if sys.platform != "win32":
        raise DeckModeError("Windows is required.")
    api = win.windows_api()
    primary, active, current = current_display(api)
    selected, target_mode = choose_display_mode(api, primary.DeviceName, current)
    paths, modes = query_config(api)
    if len(paths) > 1:
        keep = [p for p in paths if win.source_name(api, p) == primary.DeviceName]
        if len(keep) != 1:
            raise DeckModeError("Cannot identify one unique path for the main display.")
        apply_config(api, encode_config(keep, modes), SDC_VALIDATE | SDC_ALLOW_CHANGES)
    target_mode.dmFields |= win.DM_PELSWIDTH | win.DM_PELSHEIGHT | win.DM_DISPLAYFREQUENCY
    win.set_mode(api, primary.DeviceName, target_mode, win.CDS_TEST,
                 "Testing the selected 16:10 mode")
    apps = sunshine_apps(apps_file)
    try:
        data = json.loads(apps.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise DeckModeError(f"Cannot read Sunshine apps.json: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
        raise DeckModeError("Sunshine apps.json has no apps array.")
    steam = steam_path()
    if steam is None:
        raise DeckModeError("Steam was not found in the registry or PATH.")
    if not steam_uri_registered():
        raise DeckModeError("Steam is installed, but the steam:// URL handler is not registered. Start Steam once and retry.")
    return {
        "primary": primary.DeviceName,
        "active_displays": len(active),
        "connected_displays": connected_count(api),
        "current": (current.dmPelsWidth, current.dmPelsHeight),
        "target": (selected.width, selected.height),
        "steam": steam,
        "apps": apps,
    }


def report(plan: dict) -> None:
    print(f"Main display: {plan['primary']} ({plan['current'][0]}x{plan['current'][1]})")
    print(f"Displays: {plan['active_displays']} active, {plan['connected_displays']} available targets")
    print(f"Session resolution: {plan['target'][0]}x{plan['target'][1]} (16:10)")
    print(f"Steam: {plan['steam']}")
    print(f"Sunshine apps: {plan['apps']}")


def app_entry() -> dict:
    executable = PROGRAM_DIR / EXECUTABLE_NAME
    command = f'"{executable}"'
    return {
        "name": core.APP_NAME,
        "image-path": str(PROGRAM_DIR / ART_NAME),
        "working-dir": str(PROGRAM_DIR),
        "prep-cmd": [{"do": f"{command} --session-start",
                      "undo": f"{command} --session-stop"}],
        "detached": ["steam://open/bigpicture"],
    }


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def elevate(apps_file: Path | None) -> None:
    if not getattr(sys, "frozen", False):
        raise DeckModeError("Build the one-file executable before installing. Source mode supports --check.")
    args = "--install-elevated"
    if apps_file:
        args += f' --apps-file "{apps_file}"'
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
    if result <= 32:
        raise DeckModeError(f"Administrator elevation was cancelled or failed (code {result}).")


def write_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def service_state() -> str | None:
    query = subprocess.run(["sc.exe", "query", "SunshineService"],
                           capture_output=True, text=True, timeout=10)
    if query.returncode:
        return None
    match = re.search(r"STATE\s*:\s*\d+\s+([A-Z_]+)", query.stdout)
    if not match:
        raise DeckModeError("Could not read Sunshine's service state.")
    return match.group(1)


def wait_for_service(expected: str, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while True:
        state = service_state()
        if state == expected:
            return
        if state is None:
            raise DeckModeError("Sunshine service disappeared during restart.")
        if time.monotonic() >= deadline:
            raise DeckModeError(f"Sunshine remained {state} while waiting for {expected}.")
        time.sleep(1)


def sunshine_web_endpoint(apps_file: Path) -> tuple[str, int]:
    host, port = "127.0.0.1", 47990
    config = apps_file.with_name("sunshine.conf")
    if config.is_file():
        for line in config.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            key, separator, value = line.partition("=")
            if not separator:
                continue
            value = value.split("#", 1)[0].strip().strip('"')
            if key.strip() == "port":
                port = int(value) + 1
            elif key.strip() == "bind_address" and value:
                host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(value, value)
    return host, port


def wait_for_web(apps_file: Path, timeout: float = 90) -> None:
    host, port = sunshine_web_endpoint(apps_file)
    deadline = time.monotonic() + timeout
    while True:
        if service_state() != "RUNNING":
            raise DeckModeError("Sunshine stopped during startup.")
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            if time.monotonic() >= deadline:
                raise DeckModeError(
                    f"Sunshine service is running but its web UI is not listening at {host}:{port}."
                )
            time.sleep(1)


def ensure_service_running() -> None:
    for attempt in range(3):
        state = service_state()
        if state == "STOP_PENDING":
            wait_for_service("STOPPED", timeout=90)
            state = "STOPPED"
        if state == "STOPPED":
            start = subprocess.run(["sc.exe", "start", "SunshineService"],
                                   capture_output=True, text=True, timeout=20)
            if start.returncode and service_state() not in ("START_PENDING", "RUNNING"):
                if attempt == 2:
                    raise DeckModeError(
                        f"Could not start Sunshine: {start.stdout.strip()} {start.stderr.strip()}"
                    )
                time.sleep(2)
                continue
        wait_for_service("RUNNING")
        return
    raise DeckModeError("Sunshine did not start after three attempts.")


def reload_sunshine(apps_file: Path) -> None:
    initial = service_state()
    if initial is None:
        print("No Sunshine service found. Restart Sunshine manually to load the app entry.")
        return
    if initial == "RUNNING":
        try:
            stop = subprocess.run(["sc.exe", "stop", "SunshineService"],
                                  capture_output=True, text=True, timeout=20)
            if stop.returncode and service_state() == "RUNNING":
                raise DeckModeError(
                    f"Could not stop Sunshine: {stop.stdout.strip()} {stop.stderr.strip()}"
                )
            wait_for_service("STOPPED", timeout=120)
        finally:
            # A failed stop must not leave Sunshine offline if it reaches STOPPED later.
            ensure_service_running()
    else:
        ensure_service_running()
    wait_for_web(apps_file)
    print("Sunshine is running and its web UI is ready. Refresh Moonlight's app list.")


def install(apps_file: Path | None) -> None:
    if not getattr(sys, "frozen", False):
        raise DeckModeError("Run the packaged MoonlightDeckMode.exe to install; source mode supports --check.")
    plan = check(apps_file)
    report(plan)
    if not is_admin():
        print("Requesting administrator access to update Sunshine...")
        elevate(apps_file)
        return
    apps = plan["apps"]
    original = apps.read_bytes()
    document = json.loads(original.decode("utf-8-sig"))
    document, action = core.merge_app_list(document, app_entry())
    PROGRAM_DIR.mkdir(parents=True, exist_ok=True)
    installed_exe = PROGRAM_DIR / EXECUTABLE_NAME
    if Path(sys.executable).resolve() != installed_exe.resolve():
        write_atomic(installed_exe, Path(sys.executable).read_bytes())
    art = resource(ART_NAME)
    if not art.is_file():
        raise DeckModeError("The installer is missing its Moonlight cover image.")
    write_atomic(PROGRAM_DIR / ART_NAME, art.read_bytes())
    if action == "unchanged":
        print("Sunshine app is already current; checking that Sunshine reloads it.")
        reload_sunshine(apps)
        return
    backup = PROGRAM_DIR / f"apps.backup.{datetime.now():%Y%m%d-%H%M%S}.{uuid.uuid4().hex[:6]}.json"
    backup.write_bytes(original)
    try:
        if apps.read_bytes() != original:
            raise DeckModeError("Sunshine apps.json changed during installation; retry to preserve the newer changes.")
        write_atomic(apps, (json.dumps(document, indent=4, ensure_ascii=False) + "\n").encode("utf-8"))
    except OSError:
        raise DeckModeError(f"Could not update {apps}; original is preserved at {backup}.")
    print(f"Sunshine app {action}. Backup: {backup}")
    try:
        reload_sunshine(apps)
    except (DeckModeError, OSError, subprocess.SubprocessError) as exc:
        raise DeckModeError(
            f"App was saved, but Sunshine did not restart cleanly: {exc}. "
            "Start Sunshine manually if it is stopped."
        ) from exc


def encode_config(paths: list, modes: list) -> dict:
    path_array = (win.PATH_INFO * len(paths))(*paths)
    mode_array = (win.MODE_INFO * len(modes))(*modes)
    return {
        "paths": base64.b64encode(bytes(path_array)).decode("ascii"),
        "modes": base64.b64encode(bytes(mode_array)).decode("ascii"),
        "path_count": len(paths), "mode_count": len(modes),
    }


def apply_config(api, saved: dict, flags: int) -> None:
    path_count, mode_count = saved["path_count"], saved["mode_count"]
    paths = (win.PATH_INFO * path_count).from_buffer_copy(base64.b64decode(saved["paths"]))
    modes = (win.MODE_INFO * mode_count).from_buffer_copy(base64.b64decode(saved["modes"]))
    error = api.SetDisplayConfig(path_count, paths, mode_count, modes,
                                 SDC_USE_SUPPLIED_DISPLAY_CONFIG | flags)
    if error:
        raise DeckModeError(f"Windows rejected the display layout (error {error}).")


def change_mode(api, name: str, chosen, action: str) -> None:
    chosen.dmFields |= win.DM_PELSWIDTH | win.DM_PELSHEIGHT | win.DM_DISPLAYFREQUENCY
    win.set_mode(api, name, chosen, win.CDS_TEST, f"Testing {action}")
    win.set_mode(api, name, chosen, 0, action)


def restore(api, state: dict) -> None:
    if state.get("version") != STATE_VERSION:
        raise DeckModeError("The saved session state has an unknown version.")
    if state["changed_topology"]:
        apply_config(api, state["configuration"], win.SDC_APPLY | SDC_ALLOW_CHANGES)
    primary, _, current = current_display(api)
    if primary.DeviceName != state["primary"]:
        raise DeckModeError("The main display changed during the session. Restore it in Windows Settings.")
    original = core.Mode(*state["original"])
    candidates = modes_for(api, state["primary"])
    match = next((mode for description, mode in candidates if description == original), None)
    if match is None:
        raise DeckModeError("The original display mode is no longer advertised; choose it in Windows Settings.")
    if (current.dmPelsWidth, current.dmPelsHeight,
            current.dmDisplayFrequency, current.dmBitsPerPel) != tuple(state["original"]):
        change_mode(api, state["primary"], match, "restoring the main display")


def start_session() -> None:
    api = win.windows_api()
    state_file = STATE_DIR / "session.json"
    if state_file.exists():
        prior = json.loads(state_file.read_text(encoding="utf-8"))
        primary, active, current = current_display(api)
        if (prior.get("version") == STATE_VERSION
                and primary.DeviceName == prior.get("primary")
                and len(query_config(api)[0]) == 1
                and [current.dmPelsWidth, current.dmPelsHeight] == prior.get("target")):
            print("Deck session is already active.")
            return
        raise DeckModeError(f"A prior session state exists at {state_file}. Run --session-stop first.")
    primary, active, current = current_display(api)
    selected, mode = choose_display_mode(api, primary.DeviceName, current)
    paths, modes = query_config(api)
    keep = [p for p in paths if win.source_name(api, p) == primary.DeviceName]
    if len(keep) != 1:
        raise DeckModeError("Cannot identify one unique path for the main display; no changes were made.")
    # Clone mode can have two active paths but only one distinct source name.
    change_topology = core.should_change_topology(len(paths))
    if change_topology:
        apply_config(api, encode_config(keep, modes), SDC_VALIDATE | SDC_ALLOW_CHANGES)
    original = core.Mode(current.dmPelsWidth, current.dmPelsHeight,
                         current.dmDisplayFrequency, current.dmBitsPerPel)
    state = {
        "version": STATE_VERSION,
        "primary": primary.DeviceName,
        "original": [original.width, original.height, original.refresh, original.depth],
        "target": [selected.width, selected.height],
        "changed_topology": change_topology,
        "configuration": encode_config(paths, modes),
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_atomic(state_file, json.dumps(state).encode("utf-8"))
    try:
        if change_topology:
            apply_config(api, encode_config(keep, modes), win.SDC_APPLY | SDC_ALLOW_CHANGES)
            selected_primary, selected_active, _ = current_display(api)
            if (selected_primary.DeviceName != primary.DeviceName
                    or len(selected_active) != 1 or len(query_config(api)[0]) != 1):
                raise DeckModeError("Windows did not keep the original main display as the only active display.")
        if (current.dmPelsWidth, current.dmPelsHeight) != (selected.width, selected.height):
            change_mode(api, primary.DeviceName, mode, "setting the 16:10 session resolution")
        win.wait_for_layout(api, 1, (selected.width, selected.height))
        if len(query_config(api)[0]) != 1:
            raise DeckModeError("More than one display path remained active.")
    except Exception:
        try:
            restore(api, state)
            state_file.unlink(missing_ok=True)
        except Exception as rollback:
            print(f"Automatic rollback failed: {rollback}", file=sys.stderr)
        raise
    print(f"Deck session ready at {selected.width}x{selected.height}.")


def stop_session() -> None:
    state_file = STATE_DIR / "session.json"
    if not state_file.exists():
        print("No saved Deck session; display was left unchanged.")
        return
    state = json.loads(state_file.read_text(encoding="utf-8"))
    api = win.windows_api()
    restore(api, state)
    state_file.unlink()
    try:
        os.startfile("steam://close/bigpicture")
    except OSError as exc:
        print(f"Desktop restored; Steam Big Picture could not be closed: {exc}")
    print("Original display layout restored.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="Read-only prerequisite check")
    action.add_argument("--version", action="store_true", help="Show version and exit")
    action.add_argument("--dry-run", action="store_true", help="Alias for --check")
    action.add_argument("--install", action="store_true", help="Install the Sunshine app")
    action.add_argument("--install-elevated", action="store_true", help=argparse.SUPPRESS)
    action.add_argument("--session-start", action="store_true", help=argparse.SUPPRESS)
    action.add_argument("--session-stop", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--apps-file", type=Path, help="Explicit Sunshine apps.json path")
    args = parser.parse_args()
    try:
        if args.version:
            print(VERSION)
        elif args.session_start:
            start_session()
        elif args.session_stop:
            stop_session()
        elif args.check or args.dry_run:
            report(check(args.apps_file))
        else:
            if not args.install_elevated:
                report(check(args.apps_file))
                if input("Install Moonlight Deck Mode in Sunshine? [y/N] ").strip().lower() != "y":
                    print("Cancelled; no changes made.")
                    return 0
            install(args.apps_file)
        return 0
    except (DeckModeError, win.DisplayError, ValueError, OSError, KeyError,
            subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
