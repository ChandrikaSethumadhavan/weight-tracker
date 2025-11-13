from __future__ import annotations

import math
import random
import re
import struct
from pathlib import Path
from typing import List, Sequence, Tuple

import requests


class AssetManager:
    REMOTE_SOURCES = [
        # Friendly, license-friendly animations (Wikimedia Commons, CC BY-SA)
        "https://upload.wikimedia.org/wikipedia/commons/5/5f/Animated_Pushups.gif",
        "https://upload.wikimedia.org/wikipedia/commons/1/19/AerobicDance.gif",
    ]

    def __init__(self, assets_dir: Path, remote_urls: Sequence[str] | None = None) -> None:
        self.assets_dir = Path(assets_dir)
        self.gif_dir = self.assets_dir / "gifs"
        self.gif_dir.mkdir(parents=True, exist_ok=True)
        self.remote_urls = list(remote_urls or [])
        self._fetched = False
        self._placeholder_pixmap = None
        self._ensure_builtin()

    def ensure_gifs(self) -> List[Path]:
        if not self._fetched:
            self._fetched = True
            self._download_remote()
        custom: List[Path] = []
        builtin: List[Path] = []
        for path in self.gif_dir.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() != ".gif":
                continue
            if path.stat().st_size == 0:
                continue
            if path.name.lower() == "lively_orb.gif":
                builtin.append(path)
            else:
                custom.append(path)
        if not custom and not builtin:
            builtin = [self._ensure_builtin()]
        return custom + builtin

    def random_movie(self):
        try:
            from PyQt6 import QtGui
        except Exception:  # pragma: no cover - depends on PyQt installation
            return None

        gif_files = self.ensure_gifs()
        if not gif_files:
            return None
        preferred = [path for path in gif_files if path.name.lower() != "lively_orb.gif"]
        fallback = [path for path in gif_files if path.name.lower() == "lively_orb.gif"]
        pool = preferred if preferred else fallback
        random.shuffle(pool)
        for gif_path in pool:
            movie = QtGui.QMovie(gif_path.resolve().as_posix())
            if movie.isValid():
                movie.setCacheMode(QtGui.QMovie.CacheMode.CacheAll)
                movie.setSpeed(105)
                movie.start()
                return movie
        return None

    def placeholder_pixmap(self):
        try:
            from PyQt6 import QtCore, QtGui
        except Exception:  # pragma: no cover - depends on PyQt installation
            return None
        if self._placeholder_pixmap is not None:
            return self._placeholder_pixmap
        pixmap = QtGui.QPixmap(320, 320)
        pixmap.fill(QtGui.QColor("#1d1f33"))
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#ffb347"), 4))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#2f89fc")))
        painter.drawEllipse(70, 70, 180, 180)
        painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff")))
        font = QtGui.QFont("Segoe UI", 16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            pixmap.rect(),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            "Mascot\nloading...",
        )
        painter.end()
        self._placeholder_pixmap = pixmap
        return self._placeholder_pixmap

    # ------------------------------------------------------------------
    def _ensure_builtin(self) -> Path:
        target = self.gif_dir / "lively_orb.gif"
        if target.exists():
            return target
        factory = _MiniGifFactory()
        target.write_bytes(factory.build())
        return target

    def _download_remote(self) -> None:
        sources = self.remote_urls + self.REMOTE_SOURCES
        for url in sources:
            try:
                name = re.sub(r"[^a-z0-9]+", "-", url.split("/")[-1].split(".")[0].lower()).strip("-")
                if not name:
                    continue
                path = self.gif_dir / f"{name}.gif"
                if path.exists():
                    continue
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                path.write_bytes(response.content)
            except Exception:
                # Silent failure keeps the app offline-friendly.
                continue


class _MiniGifFactory:
    """Tiny GIF generator so we always have a playful mascot offline."""

    def __init__(self, size: int = 96) -> None:
        self.size = size
        self.palette = [
            (10, 16, 54),  # background
            (250, 141, 102),  # body
            (255, 221, 89),  # head
            (99, 205, 218),  # sweat drop
            (255, 255, 255),  # accent
        ]

    def build(self) -> bytes:
        writer = _GifWriter(self.size, self.size, self.palette)
        frames = 16
        for frame in range(frames):
            pixels = self._render_frame(frame, frames)
            writer.add_frame(pixels, delay=6)
        return writer.to_bytes()

    def _render_frame(self, frame: int, total: int) -> List[int]:
        pixels = [0] * (self.size * self.size)
        orbit = math.sin((frame / total) * math.tau)
        center_x = int(self.size // 2 + orbit * (self.size // 4))
        center_y = int(self.size // 2 + math.cos((frame / total) * math.tau) * (self.size // 6))
        body_radius = self.size // 6
        head_radius = body_radius // 2

        for y in range(self.size):
            for x in range(self.size):
                idx = y * self.size + x
                if (x - center_x) ** 2 + (y - center_y) ** 2 <= body_radius**2:
                    pixels[idx] = 1
                if (x - center_x) ** 2 + (y - (center_y - body_radius)) ** 2 <= head_radius**2:
                    pixels[idx] = 2

        # Sweat drop that appears when orbit is high
        drop_x = center_x + head_radius
        drop_y = center_y - body_radius - 4
        if orbit > 0:
            for y in range(drop_y, drop_y + 4):
                for x in range(drop_x, drop_x + 3):
                    if 0 <= x < self.size and 0 <= y < self.size:
                        pixels[y * self.size + x] = 3

        # Ground shadow
        ground_y = self.size - 15
        for x in range(self.size // 4, self.size - self.size // 4):
            idx = ground_y * self.size + x
            pixels[idx] = 4
        return pixels


class _GifWriter:
    def __init__(self, width: int, height: int, palette: Sequence[Tuple[int, int, int]]) -> None:
        self.width = width
        self.height = height
        self.palette = self._pad_palette(list(palette))
        self.frames: List[Tuple[List[int], int]] = []

    def _pad_palette(self, palette: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
        size = 1
        while size < len(palette):
            size *= 2
        palette = palette + [palette[-1]] * (size - len(palette))
        return palette

    def add_frame(self, pixels: List[int], delay: int = 8) -> None:
        if len(pixels) != self.width * self.height:
            raise ValueError("Pixel data has incorrect length.")
        self.frames.append((pixels, delay))

    def to_bytes(self) -> bytes:
        if not self.frames:
            raise ValueError("No frames provided.")
        palette_size = len(self.palette)
        color_depth = max(1, int(math.log2(palette_size)))
        gct_size_code = max(0, color_depth - 1)
        data = bytearray()
        data.extend(b"GIF89a")
        data.extend(struct.pack("<HH", self.width, self.height))
        packed = 0x80 | ((color_depth - 1) << 4) | gct_size_code
        data.append(packed)
        data.append(0)  # background index
        data.append(0)  # pixel aspect ratio
        for r, g, b in self.palette:
            data.extend(bytes([r, g, b]))
        # loop forever
        data.extend(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")

        min_code_size = max(2, int(math.ceil(math.log2(palette_size))))
        for pixels, delay in self.frames:
            data.extend(b"\x21\xF9\x04\x00")
            data.extend(struct.pack("<H", delay))
            data.extend(b"\x00\x00")
            data.extend(b"\x2C")
            data.extend(struct.pack("<HHHH", 0, 0, self.width, self.height))
            data.append(0x00)
            data.append(min_code_size)
            encoded = _lzw_encode(pixels, min_code_size)
            idx = 0
            while idx < len(encoded):
                chunk = encoded[idx : idx + 255]
                data.append(len(chunk))
                data.extend(chunk)
                idx += 255
            data.append(0x00)
        data.append(0x3B)
        return bytes(data)


def _lzw_encode(indices: List[int], min_code_size: int) -> bytes:
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    dictionary = {tuple([i]): i for i in range(clear_code)}
    dict_size = end_code + 1
    code_size = min_code_size + 1
    buffer = 0
    bits = 0
    out = bytearray()

    def write(code: int) -> None:
        nonlocal buffer, bits, out, code_size
        buffer |= code << bits
        bits += code_size
        while bits >= 8:
            out.append(buffer & 0xFF)
            buffer >>= 8
            bits -= 8

    write(clear_code)
    string: Tuple[int, ...] = ()
    for symbol in indices:
        candidate = string + (symbol,)
        if candidate in dictionary:
            string = candidate
            continue
        if string:
            write(dictionary[string])
        dictionary[candidate] = dict_size
        dict_size += 1
        if dict_size == (1 << code_size) and code_size < 12:
            code_size += 1
        string = (symbol,)
        if dict_size >= 4095:
            write(clear_code)
            dictionary = {tuple([i]): i for i in range(clear_code)}
            dict_size = end_code + 1
            code_size = min_code_size + 1
            string = ()
    if string:
        write(dictionary[string])
    write(end_code)
    if bits:
        out.append(buffer & 0xFF)
    return bytes(out)
