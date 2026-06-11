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


def rgb888_to_rgb565_wire(r, g, b):
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    v = (r5 << 11) | (g6 << 5) | b5
    return bytes(((v >> 8) & 0xFF, v & 0xFF))


def rgb565_le_to_rgb888(lo, hi):
    v = (lo & 0xFF) | ((hi & 0xFF) << 8)
    r5 = (v >> 11) & 0x1F
    g6 = (v >> 5) & 0x3F
    b5 = v & 0x1F
    r = (r5 * 255 + 15) // 31
    g = (g6 * 255 + 31) // 63
    b = (b5 * 255 + 15) // 31
    return r, g, b


def parse_rgb565(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.lower().startswith("0x"):
        return int(text, 16) & 0xFFFF
    return int(text) & 0xFFFF


def rgb565_to_bytes(value, byte_order="le"):
    value &= 0xFFFF
    if byte_order == "wire":
        return bytes(((value >> 8) & 0xFF, value & 0xFF))
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def convert_png_to_rgb565(src_path, dst_path, byte_order="le", alpha_colorkey=None, alpha_threshold=1):
    with Image.open(src_path) as src:
        has_alpha = src.mode in ("RGBA", "LA") or (src.mode == "P" and "transparency" in src.info)
        img = src.convert("RGBA" if has_alpha else "RGB")

    if byte_order not in ("le", "wire"):
        raise ValueError("byte_order must be le or wire")
    encode = rgb888_to_rgb565_wire if byte_order == "wire" else rgb888_to_rgb565_le

    w, h = img.size
    pix = img.load()
    out = bytearray(w * h * 2)
    i = 0
    key_px = rgb565_to_bytes(alpha_colorkey, byte_order) if alpha_colorkey is not None else None
    for y in range(h):
        for x in range(w):
            if has_alpha:
                r, g, b, a = pix[x, y]
                if key_px is not None and a < alpha_threshold:
                    px = key_px
                else:
                    px = encode(r, g, b)
            else:
                r, g, b = pix[x, y]
                px = encode(r, g, b)
            out[i] = px[0]
            out[i + 1] = px[1]
            i += 2

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(out)
    return w, h, len(out)


def rgb565_to_png_preview(src_path, width, height, preview_path, byte_order="le"):
    raw = src_path.read_bytes()
    expected = int(width) * int(height) * 2
    if len(raw) != expected:
        raise ValueError("rgb565 size mismatch: got=%d expected=%d" % (len(raw), expected))

    out = Image.new("RGB", (int(width), int(height)))
    pix = out.load()
    i = 0
    for y in range(int(height)):
        for x in range(int(width)):
            b0 = raw[i]
            b1 = raw[i + 1]
            i += 2
            if byte_order == "wire":
                pix[x, y] = rgb565_le_to_rgb888(b1, b0)
            else:
                pix[x, y] = rgb565_le_to_rgb888(b0, b1)

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(preview_path, format="PNG")
    return preview_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert PNG -> raw RGB565 (row-major, no header), with optional PNG preview decode."
    )
    parser.add_argument("src", type=Path, help="Source PNG path")
    parser.add_argument("dst", type=Path, help="Destination .rgb565 path")
    parser.add_argument("--preview", type=Path, default=None, help="Optional preview PNG path decoded from output .rgb565")
    parser.add_argument("--width", type=int, default=None, help="Preview decode width (default: source PNG width)")
    parser.add_argument("--height", type=int, default=None, help="Preview decode height (default: source PNG height)")
    parser.add_argument("--byte-order", choices=("le", "wire"), default="le", help="Output byte order: le for little-endian, wire for panel byte order")
    parser.add_argument("--alpha-colorkey", default=None, help="RGB565 value used for fully transparent pixels, e.g. 0xF81F")
    parser.add_argument("--alpha-threshold", type=int, default=1, help="Alpha values below this threshold become the colorkey")
    args = parser.parse_args()

    alpha_colorkey = parse_rgb565(args.alpha_colorkey) if args.alpha_colorkey is not None else None
    w, h, size = convert_png_to_rgb565(args.src, args.dst, args.byte_order, alpha_colorkey, args.alpha_threshold)
    expected = w * h * 2
    if size != expected:
        raise SystemExit("size mismatch: got=%d expected=%d" % (size, expected))

    preview_path = None
    if args.preview is not None:
        pw = args.width if args.width is not None else w
        ph = args.height if args.height is not None else h
        preview_path = rgb565_to_png_preview(args.dst, pw, ph, args.preview, args.byte_order)

    print("INPUT_SIZE=%dx%d" % (w, h))
    print("OUTPUT_RGB565=%s" % args.dst)
    print("BYTE_ORDER=%s" % args.byte_order)
    if alpha_colorkey is not None:
        print("ALPHA_COLORKEY=0x%04X" % alpha_colorkey)
    print("OUTPUT_SIZE=%d" % size)
    print("EXPECTED_SIZE=%d" % expected)
    print("SIZE_MATCH=%s" % ("YES" if size == expected else "NO"))
    if preview_path is not None:
        print("PREVIEW_PNG=%s" % preview_path)


if __name__ == "__main__":
    main()
