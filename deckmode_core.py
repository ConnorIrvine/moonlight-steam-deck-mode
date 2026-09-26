"""Pure decisions shared by the installer and Sunshine session commands."""

from __future__ import annotations

from dataclasses import dataclass


APP_NAME = "Moonlight Deck Mode"
MIN_HEIGHT = 800


@dataclass(frozen=True)
class Mode:
    width: int
    height: int
    refresh: int = 0
    depth: int = 32


def choose_mode(modes: list[Mode], current: Mode) -> Mode:
    """Choose the largest exact 16:10 mode at 800p or above.

    Repeated resolutions prefer the current refresh/depth, then the highest
    refresh. A higher refresh is never worth reducing the resolution.
    """
    eligible = [
        mode for mode in modes
        if mode.height >= MIN_HEIGHT
        and mode.width * 10 == mode.height * 16
        and mode.depth >= 32
    ]
    if not eligible:
        raise ValueError("The main display offers no 16:10 mode at 1280x800 or higher.")
    return max(
        eligible,
        key=lambda mode: (
            mode.width * mode.height,
            mode.refresh == current.refresh,
            mode.depth == current.depth,
            mode.refresh,
            mode.depth,
        ),
    )


def merge_app_list(document: dict, entry: dict) -> tuple[dict, str]:
    """Update only our named Sunshine app, preserving all other entries."""
    if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
        raise ValueError("Sunshine apps.json has no apps array.")
    apps = document["apps"]
    matches = [i for i, app in enumerate(apps)
               if isinstance(app, dict) and app.get("name") == APP_NAME]
    if len(matches) > 1:
        raise ValueError(f"Multiple {APP_NAME!r} entries exist; resolve them manually.")
    if matches:
        old = apps[matches[0]]
        if old == entry:
            return document, "unchanged"
        # Do not overwrite an app with the same name if it is not ours.
        if not old.get("working-dir", "").lower().endswith("moonlightdeckmode"):
            raise ValueError(f"An unrelated {APP_NAME!r} app already exists.")
        apps[matches[0]] = entry
        return document, "updated"
    apps.append(entry)
    return document, "added"


def should_change_topology(active_path_count: int) -> bool:
    """An existing one-screen setup stays one-screen on session exit."""
    if active_path_count < 1:
        raise ValueError("Windows reported no active displays.")
    return active_path_count > 1
