"""Render the project-owned SVG into PNG and a multi-resolution Windows ICO."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"无法渲染 {size} px 图标")
    buffer.close()
    return bytes(payload)


def write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries: list[bytes] = []
    blobs: list[bytes] = []
    for size, payload in images:
        encoded_size = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                encoded_size,
                encoded_size,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        blobs.append(payload)
        offset += len(payload)
    path.write_bytes(header + b"".join(entries) + b"".join(blobs))


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication(["fdtd-icon-generator"])
    del app
    source = PROJECT_DIR / "assets" / "fdtd_runner_icon.svg"
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError(f"无效的 SVG：{source}")
    images = [(size, render_png(renderer, size)) for size in (16, 24, 32, 48, 64, 128, 256)]
    write_ico(PROJECT_DIR / "assets" / "fdtd_runner.ico", images)
    preview = PROJECT_DIR / "docs" / "images" / "fdtd-runner-icon.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_bytes(images[-1][1])


if __name__ == "__main__":
    main()
