#!/usr/bin/env python3
"""Create the two desktop shortcut icons without third-party packages."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


OUT = Path(__file__).with_name("icons")
SIZES = (256, 64, 32, 16)


def rounded(x, y, left, top, right, bottom, radius):
    if not (left <= x <= right and top <= y <= bottom):
        return False
    cx = min(max(x, left + radius), right - radius)
    cy = min(max(y, top + radius), bottom - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def circle(x, y, cx, cy, radius):
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def color_at(kind, x, y):
    if not rounded(x, y, 10, 10, 246, 246, 48):
        return (0, 0, 0, 0)
    background = (13, 22, 35, 255)
    if kind == "windows":
        if ((53 <= x <= 121 or 135 <= x <= 203)
                and (53 <= y <= 121 or 135 <= y <= 203)):
            return (0, 164, 239, 255)
        return background

    # A high-contrast Steam Deck silhouette, legible even at 32 pixels.
    if not rounded(x, y, 20, 67, 236, 189, 39):
        return background
    if not rounded(x, y, 27, 74, 229, 182, 33):
        return (230, 236, 244, 255)
    body = (31, 46, 65, 255)
    if rounded(x, y, 76, 83, 180, 173, 10):
        if rounded(x, y, 82, 89, 174, 167, 5):
            return (11, 24, 39, 255)
        return (102, 203, 252, 255)
    if circle(x, y, 51, 104, 15) or circle(x, y, 205, 147, 15):
        if circle(x, y, 51, 104, 9) or circle(x, y, 205, 147, 9):
            return body
        return (230, 236, 244, 255)
    if (47 <= x <= 55 and 132 <= y <= 158) or (38 <= x <= 64 and 141 <= y <= 149):
        return (230, 236, 244, 255)
    if any(circle(x, y, cx, cy, 5) for cx, cy in ((205, 94), (190, 109), (220, 109), (205, 124))):
        return (230, 236, 244, 255)
    return body


def png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def make_png(kind, size):
    rows = []
    for py in range(size):
        row = bytearray(b"\x00")
        for px in range(size):
            samples = [
                color_at(kind, (px + dx) * 256 / size, (py + dy) * 256 / size)
                for dy in (0.25, 0.75) for dx in (0.25, 0.75)
            ]
            alpha_sum = sum(c[3] for c in samples)
            if alpha_sum:
                rgb = [sum(c[i] * c[3] for c in samples) // alpha_sum for i in range(3)]
            else:
                rgb = [0, 0, 0]
            row.extend((*rgb, alpha_sum // 4))
        rows.append(row)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + png_chunk(b"IEND", b"")
    )


def make_ico(images):
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    offset = 6 + 16 * len(images)
    for size, png in images:
        entries.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset))
        offset += len(png)
    return header + entries + b"".join(png for _, png in images)


def main():
    OUT.mkdir(exist_ok=True)
    for kind, name in (("windows", "Windows"), ("deck", "SteamDeck")):
        images = [(size, make_png(kind, size)) for size in SIZES]
        (OUT / f"{name}.png").write_bytes(images[0][1])
        (OUT / f"{name}.ico").write_bytes(make_ico(images))
        print(OUT / f"{name}.ico")


if __name__ == "__main__":
    main()
