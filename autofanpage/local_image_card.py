from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path


def _clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def _seed_from_text(*parts: str) -> int:
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _blend(base: tuple[int, int, int], top: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return (
        _clamp(base[0] * (1 - alpha) + top[0] * alpha),
        _clamp(base[1] * (1 - alpha) + top[1] * alpha),
        _clamp(base[2] * (1 - alpha) + top[2] * alpha),
    )


def _fill_gradient(
    canvas: bytearray,
    *,
    width: int,
    height: int,
    seed: int,
) -> None:
    top = (
        10 + (seed % 18),
        22 + ((seed >> 8) % 18),
        34 + ((seed >> 16) % 22),
    )
    bottom = (
        20 + ((seed >> 24) % 16),
        34 + ((seed >> 32) % 18),
        56 + ((seed >> 40) % 20),
    )
    accent_a = (60, 130, 255)
    accent_b = (32, 211, 168)

    for y in range(height):
        mix = y / max(1, height - 1)
        row = [
            _clamp(top[channel] * (1 - mix) + bottom[channel] * mix)
            for channel in range(3)
        ]
        wave = ((y + seed) % 97) / 96.0
        row_color = _blend(tuple(row), accent_a if wave > 0.55 else accent_b, 0.04)
        for x in range(width):
            idx = (y * width + x) * 3
            canvas[idx:idx + 3] = bytes(row_color)


def _fill_rect(
    canvas: bytearray,
    *,
    width: int,
    height: int,
    left: int,
    top: int,
    rect_width: int,
    rect_height: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    right = min(width, left + rect_width)
    bottom = min(height, top + rect_height)
    for y in range(max(0, top), bottom):
        for x in range(max(0, left), right):
            idx = (y * width + x) * 3
            current = tuple(canvas[idx:idx + 3])
            canvas[idx:idx + 3] = bytes(_blend(current, color, alpha))


def _draw_layout(
    canvas: bytearray,
    *,
    width: int,
    height: int,
    seed: int,
) -> None:
    panel = (18, 27, 48)
    accent_a = (75, 161, 255)
    accent_b = (49, 214, 174)
    accent_c = (244, 114, 182)

    _fill_rect(
        canvas,
        width=width,
        height=height,
        left=int(width * 0.08),
        top=int(height * 0.08),
        rect_width=int(width * 0.46),
        rect_height=int(height * 0.18),
        color=panel,
        alpha=0.58,
    )
    _fill_rect(
        canvas,
        width=width,
        height=height,
        left=int(width * 0.08),
        top=int(height * 0.34),
        rect_width=int(width * 0.72),
        rect_height=int(height * 0.28),
        color=panel,
        alpha=0.50,
    )
    _fill_rect(
        canvas,
        width=width,
        height=height,
        left=int(width * 0.60),
        top=int(height * 0.66),
        rect_width=int(width * 0.25),
        rect_height=int(height * 0.18),
        color=panel,
        alpha=0.62,
    )

    colors = [accent_a, accent_b, accent_c, accent_a]
    cell_size = int(width * 0.11)
    gap = int(width * 0.02)
    start_x = int(width * 0.62)
    start_y = int(height * 0.70)
    for index, color in enumerate(colors):
        row = index // 2
        col = index % 2
        tint = _blend(color, (255, 255, 255), 0.08 + (((seed >> (index * 5)) & 7) / 100))
        _fill_rect(
            canvas,
            width=width,
            height=height,
            left=start_x + col * (cell_size + gap),
            top=start_y + row * (cell_size + gap),
            rect_width=cell_size,
            rect_height=cell_size,
            color=tint,
            alpha=0.72,
        )

    bar_y = int(height * 0.12)
    for index in range(4):
        _fill_rect(
            canvas,
            width=width,
            height=height,
            left=int(width * 0.10),
            top=bar_y + index * int(height * 0.03),
            rect_width=int(width * (0.18 + 0.07 * index)),
            rect_height=int(height * 0.012),
            color=accent_a if index % 2 == 0 else accent_b,
            alpha=0.78,
        )


def _write_png(output_path: Path, *, width: int, height: int, canvas: bytearray) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    row_stride = width * 3
    for y in range(height):
        start = y * row_stride
        rows.append(b"\x00" + bytes(canvas[start:start + row_stride]))
    raw = b"".join(rows)
    compressed = zlib.compress(raw, level=9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", compressed),
            chunk(b"IEND", b""),
        ]
    )
    output_path.write_bytes(png)


def render_local_editorial_card(
    *,
    output_path: Path,
    title: str,
    summary: str,
    theme_text: str,
    accent_text: str,
    width: int,
    height: int,
) -> Path:
    seed = _seed_from_text(title, summary, theme_text, accent_text)
    canvas = bytearray(width * height * 3)
    _fill_gradient(canvas, width=width, height=height, seed=seed)
    _draw_layout(canvas, width=width, height=height, seed=seed)
    _write_png(output_path, width=width, height=height, canvas=canvas)
    return output_path
