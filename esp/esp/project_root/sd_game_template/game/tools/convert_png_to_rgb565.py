#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image


def rgb888_to_rgb565_le(r, g, b):
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    v = (r5 << 11) | (g6 << 5) | b5
    return bytes((v & 0xFF, (v >> 8) & 0xFF))


def rgb565_le_to_rgb888(lo, hi):
    v = (lo & 0xFF) | ((hi & 0xFF) << 8)
    r5 = (v >> 11) & 0x1F
    g6 = (v >> 5) & 0x3F
    b5 = v & 0x1F
    r = (r5 * 255 + 15) // 31
    g = (g6 * 255 + 31) // 63
    b = (b5 * 255 + 15) // 31
    return r, g, b


def convert_png_to_rgb565(src_path, dst_path):
    with Image.open(src_path) as src:
        img = src.convert("RGB")

    w, h = img.size
    pix = img.load()
    out = bytearray(w * h * 2)
    i = 0
    for y in range(h):
        for x in range(w):
            r, g, b = pix[x, y]
            le = rgb888_to_rgb565_le(r, g, b)
            out[i] = le[0]
            out[i + 1] = le[1]
            i += 2

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(out)
    return w, h, len(out)


def rgb565_to_png_preview(src_path, width, height, preview_path):
    raw = src_path.read_bytes()
    expected = int(width) * int(height) * 2
    if len(raw) != expected:
        raise ValueError("rgb565 size mismatch: got=%d expected=%d" % (len(raw), expected))

    out = Image.new("RGB", (int(width), int(height)))
    pix = out.load()
    i = 0
    for y in range(int(height)):
        for x in range(int(width)):
            lo = raw[i]
            hi = raw[i + 1]
            i += 2
            pix[x, y] = rgb565_le_to_rgb888(lo, hi)

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(preview_path, format="PNG")
    return preview_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert PNG -> raw RGB565 (little-endian, row-major, no header), with optional PNG preview decode."
    )
    parser.add_argument("src", type=Path, help="Source PNG path")
    parser.add_argument("dst", type=Path, help="Destination .rgb565 path")
    parser.add_argument("--preview", type=Path, default=None, help="Optional preview PNG path decoded from output .rgb565")
    parser.add_argument("--width", type=int, default=None, help="Preview decode width (default: source PNG width)")
    parser.add_argument("--height", type=int, default=None, help="Preview decode height (default: source PNG height)")
    args = parser.parse_args()

    w, h, size = convert_png_to_rgb565(args.src, args.dst)
    expected = w * h * 2
    if size != expected:
        raise SystemExit("size mismatch: got=%d expected=%d" % (size, expected))

    preview_path = None
    if args.preview is not None:
        pw = args.width if args.width is not None else w
        ph = args.height if args.height is not None else h
        preview_path = rgb565_to_png_preview(args.dst, pw, ph, args.preview)

    print("INPUT_SIZE=%dx%d" % (w, h))
    print("OUTPUT_RGB565=%s" % args.dst)
    print("OUTPUT_SIZE=%d" % size)
    print("EXPECTED_SIZE=%d" % expected)
    print("SIZE_MATCH=%s" % ("YES" if size == expected else "NO"))
    if preview_path is not None:
        print("PREVIEW_PNG=%s" % preview_path)


if __name__ == "__main__":
    main()
