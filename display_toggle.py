#!/usr/bin/env python3
"""Toggle Windows between PC screen only at 1920x1200 and an extended desktop.

PC screen only keeps the current main display on this computer. In extended
mode, the main display is 2560x1440 and Windows restores its saved arrangement.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes


SINGLE_SIZE = (1920, 1200)
EXTENDED_MAIN_SIZE = (2560, 1440)

DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x00000008
ENUM_CURRENT_SETTINGS = -1
CDS_TEST = 0x00000002
DISP_CHANGE_SUCCESSFUL = 0
SDC_APPLY = 0x00000080
SDC_TOPOLOGY_INTERNAL = 0x00000001
SDC_TOPOLOGY_EXTEND = 0x00000004
QDC_ONLY_ACTIVE_PATHS = 0x00000002
DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1
DM_POSITION = 0x00000020
DM_BITSPERPEL = 0x00040000
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFREQUENCY = 0x00400000


class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class DISPLAY_SETTINGS(ctypes.Structure):
    _fields_ = [
        ("dmPosition", POINTL),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
    ]


class DEVMODE_UNION(ctypes.Union):
    _fields_ = [("display", DISPLAY_SETTINGS), ("padding", ctypes.c_byte * 16)]


class DEVMODEW(ctypes.Structure):
    _anonymous_ = ("settings",)
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("settings", DEVMODE_UNION),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT), ("Denominator", wintypes.UINT)]


class PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID), ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT), ("statusFlags", wintypes.UINT),
    ]


class PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID), ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT), ("outputTechnology", wintypes.UINT),
        ("rotation", wintypes.UINT), ("scaling", wintypes.UINT),
        ("refreshRate", RATIONAL), ("scanLineOrdering", wintypes.UINT),
        ("targetAvailable", wintypes.BOOL), ("statusFlags", wintypes.UINT),
    ]


class PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", PATH_SOURCE_INFO), ("targetInfo", PATH_TARGET_INFO),
        ("flags", wintypes.UINT),
    ]


class MODE_INFO(ctypes.Structure):
    # The largest DISPLAYCONFIG_MODE_INFO union member is 48 bytes.
    _fields_ = [
        ("infoType", wintypes.UINT), ("id", wintypes.UINT),
        ("adapterId", LUID), ("mode", ctypes.c_byte * 48),
    ]


class DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.UINT), ("size", wintypes.UINT),
        ("adapterId", LUID), ("id", wintypes.UINT),
    ]


class SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", wintypes.WCHAR * 32),
    ]


class DisplayError(RuntimeError):
    pass


def windows_api():
    if sys.platform != "win32":
        raise DisplayError("This program requires Windows.")
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.EnumDisplayDevicesW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD
    ]
    api.EnumDisplayDevicesW.restype = wintypes.BOOL
    api.EnumDisplaySettingsW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DEVMODEW)
    ]
    api.EnumDisplaySettingsW.restype = wintypes.BOOL
    api.ChangeDisplaySettingsExW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(DEVMODEW), wintypes.HWND,
        wintypes.DWORD, wintypes.LPVOID,
    ]
    api.ChangeDisplaySettingsExW.restype = wintypes.LONG
    api.SetDisplayConfig.argtypes = [
        wintypes.UINT, ctypes.POINTER(PATH_INFO),
        wintypes.UINT, ctypes.POINTER(MODE_INFO), wintypes.UINT,
    ]
    api.SetDisplayConfig.restype = wintypes.LONG
    api.GetDisplayConfigBufferSizes.argtypes = [
        wintypes.UINT, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)
    ]
    api.GetDisplayConfigBufferSizes.restype = wintypes.LONG
    api.QueryDisplayConfig.argtypes = [
        wintypes.UINT, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(PATH_INFO),
        ctypes.POINTER(wintypes.UINT), ctypes.POINTER(MODE_INFO),
        ctypes.POINTER(wintypes.UINT),
    ]
    api.QueryDisplayConfig.restype = wintypes.LONG
    api.DisplayConfigGetDeviceInfo.argtypes = [ctypes.POINTER(DEVICE_INFO_HEADER)]
    api.DisplayConfigGetDeviceInfo.restype = wintypes.LONG
    return api


def devices(api):
    result = []
    index = 0
    while True:
        device = DISPLAY_DEVICEW()
        device.cb = ctypes.sizeof(device)
        if not api.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        index += 1
        if device.StateFlags & DISPLAY_DEVICE_MIRRORING_DRIVER:
            continue
        if not device.DeviceName:
            continue
        result.append(device)
    return result


def current_mode(api, name):
    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(mode)
    if api.EnumDisplaySettingsW(name, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)):
        return mode
    return None


def mode_for_size(api, name, size, current):
    matches = []
    index = 0
    while True:
        mode = DEVMODEW()
        mode.dmSize = ctypes.sizeof(mode)
        if not api.EnumDisplaySettingsW(name, index, ctypes.byref(mode)):
            break
        if (mode.dmPelsWidth, mode.dmPelsHeight) == size:
            matches.append(mode)
        index += 1
    if not matches:
        raise DisplayError(
            f"{name} does not advertise {size[0]}x{size[1]}. "
            "Use 'py display_toggle.py --status' to check the display name."
        )
    # Keep the current refresh rate and color depth when possible.
    return max(
        matches,
        key=lambda m: (
            m.dmBitsPerPel == current.dmBitsPerPel,
            m.dmDisplayFrequency == current.dmDisplayFrequency,
            -abs(m.dmDisplayFrequency - current.dmDisplayFrequency),
        ),
    )


def primary_and_active(api):
    found = devices(api)
    primary = next(
        (d for d in found if d.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE), None
    )
    # EnumDisplayDevices can retain ATTACHED_TO_DESKTOP for a path that CCD
    # has disconnected. QueryDisplayConfig reports the actual active paths.
    active_names = {source_name(api, path) for path in active_paths(api)}
    active = [d for d in found if d.DeviceName in active_names]
    if primary is None or not any(d.DeviceName == primary.DeviceName for d in active):
        raise DisplayError("Windows did not report an active main display.")
    return primary, active


def result_or_error(result, action):
    if result != DISP_CHANGE_SUCCESSFUL:
        raise DisplayError(f"{action} failed with Windows display error {result}.")


def set_mode(api, name, mode, flags, action):
    result_or_error(
        api.ChangeDisplaySettingsExW(name, ctypes.byref(mode), None, flags, None),
        action,
    )


def active_paths(api):
    for _ in range(3):
        path_count = wintypes.UINT()
        mode_count = wintypes.UINT()
        error = api.GetDisplayConfigBufferSizes(
            QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count), ctypes.byref(mode_count)
        )
        if error:
            raise DisplayError(f"Could not query display paths (Windows error {error}).")
        paths = (PATH_INFO * path_count.value)()
        modes = (MODE_INFO * mode_count.value)()
        error = api.QueryDisplayConfig(
            QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count), paths,
            ctypes.byref(mode_count), modes, None,
        )
        if error == 0:
            return list(paths[:path_count.value])
        if error != 122:  # ERROR_INSUFFICIENT_BUFFER: displays changed mid-query.
            raise DisplayError(f"Could not read display paths (Windows error {error}).")
    raise DisplayError("Displays changed while reading their paths; try again.")


def source_name(api, path):
    name = SOURCE_DEVICE_NAME()
    name.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
    name.header.size = ctypes.sizeof(name)
    name.header.adapterId = path.sourceInfo.adapterId
    name.header.id = path.sourceInfo.id
    error = api.DisplayConfigGetDeviceInfo(ctypes.byref(name.header))
    if error:
        raise DisplayError(f"Could not identify a display path (Windows error {error}).")
    return name.viewGdiDeviceName


def wait_for_layout(api, display_count, size):
    deadline = time.monotonic() + 12
    while True:
        primary, active = primary_and_active(api)
        mode = current_mode(api, primary.DeviceName)
        if len(active) == display_count and mode and (mode.dmPelsWidth, mode.dmPelsHeight) == size:
            return
        if time.monotonic() >= deadline:
            raise DisplayError(
                f"Windows did not settle on {display_count} active display(s) "
                f"with the main display at {size[0]}x{size[1]}."
            )
        time.sleep(0.5)


def show_status(api):
    primary, active = primary_and_active(api)
    print(f"Active displays: {len(active)}")
    for device in devices(api):
        mode = current_mode(api, device.DeviceName)
        if not mode and not any(d.DeviceName == device.DeviceName for d in active):
            continue
        role = "main" if device.DeviceName == primary.DeviceName else "secondary"
        state = "active" if any(d.DeviceName == device.DeviceName for d in active) else "inactive"
        resolution = f"{mode.dmPelsWidth}x{mode.dmPelsHeight}" if mode else "unknown"
        print(f"  {device.DeviceName}: {device.DeviceString} - {resolution}, {role}, {state}")


def to_single(api, dry_run=False):
    primary, active = primary_and_active(api)
    current = current_mode(api, primary.DeviceName)
    if current is None:
        raise DisplayError("Could not read the main display's current mode.")
    if len(active) == 1 and (current.dmPelsWidth, current.dmPelsHeight) == SINGLE_SIZE:
        print("Steam Deck Mode is already active.")
        return
    target = mode_for_size(api, primary.DeviceName, SINGLE_SIZE, current)
    target.settings.display.dmPosition.x = 0
    target.settings.display.dmPosition.y = 0
    target.dmFields |= DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
    print(f"Keeping {primary.DeviceName} at {SINGLE_SIZE[0]}x{SINGLE_SIZE[1]}; disabling {len(active) - 1} other display(s).")
    if dry_run:
        return
    # Validate the exact requested resolution before modifying any displays.
    set_mode(api, primary.DeviceName, target, CDS_TEST, "Testing 1920x1200")
    if len(active) > 1:
        error = api.SetDisplayConfig(0, None, 0, None, SDC_APPLY | SDC_TOPOLOGY_INTERNAL)
        if error:
            raise DisplayError(f"Windows could not activate PC screen only mode (error {error}).")
        selected, selected_active = primary_and_active(api)
        if len(selected_active) != 1 or selected.DeviceName != primary.DeviceName:
            raise DisplayError("PC screen only did not select the expected main display.")
    # A registry-saving mode change can restore the extended topology here.
    set_mode(api, primary.DeviceName, target, 0, "Setting main display to 1920x1200")
    wait_for_layout(api, 1, SINGLE_SIZE)


def to_extend(api, dry_run=False):
    primary, active = primary_and_active(api)
    current = current_mode(api, primary.DeviceName)
    if current is None:
        raise DisplayError("Could not read the main display's current mode.")
    if len(active) > 1 and (current.dmPelsWidth, current.dmPelsHeight) == EXTENDED_MAIN_SIZE:
        print("Desktop Mode is already active.")
        return
    target = mode_for_size(api, primary.DeviceName, EXTENDED_MAIN_SIZE, current)
    target.dmFields |= DM_PELSWIDTH | DM_PELSHEIGHT
    print(f"Extending displays; setting {primary.DeviceName} to {EXTENDED_MAIN_SIZE[0]}x{EXTENDED_MAIN_SIZE[1]}.")
    if dry_run:
        return
    set_mode(api, primary.DeviceName, target, CDS_TEST, "Testing 2560x1440")
    if len(active) == 1:
        result = api.SetDisplayConfig(0, None, 0, None, SDC_APPLY | SDC_TOPOLOGY_EXTEND)
        if result:
            raise DisplayError(
                f"Windows could not restore the extended layout (error {result}). "
                "Arrange the displays once in Windows Settings, then try again."
            )
    # Refresh the device list: Windows may have reassigned which output is main.
    new_primary, new_active = primary_and_active(api)
    if new_primary.DeviceName != primary.DeviceName:
        raise DisplayError(
            "Windows selected a different main display when extending. "
            "Set the intended display as main in Windows Settings and retry."
        )
    if len(new_active) < 2:
        raise DisplayError("Windows did not enable another display in extended mode.")
    target.settings.display.dmPosition.x = 0
    target.settings.display.dmPosition.y = 0
    target.dmFields |= DM_POSITION
    set_mode(api, primary.DeviceName, target, 0, "Setting main display to 2560x1440")
    wait_for_layout(api, len(new_active), EXTENDED_MAIN_SIZE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--single", action="store_true", help="Use the main display only at 1920x1200")
    group.add_argument("--extend", action="store_true", help="Extend displays with the main one at 2560x1440")
    group.add_argument("--status", action="store_true", help="Show active displays without changing them")
    parser.add_argument("--dry-run", action="store_true", help="Check the requested mode without changing displays")
    args = parser.parse_args()
    try:
        api = windows_api()
        if args.status:
            show_status(api)
            return 0
        _, active = primary_and_active(api)
        if args.single or (not args.extend and len(active) > 1):
            to_single(api, args.dry_run)
        else:
            to_extend(api, args.dry_run)
        return 0
    except DisplayError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
