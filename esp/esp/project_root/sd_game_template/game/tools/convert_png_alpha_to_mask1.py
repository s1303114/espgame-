#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image


def convert_png_alpha_to_mask1(src_path: Path, dst_path: Path) -> int:
    with Image.open(src_path) as src:
        rgba = src.convert("RGBA")

    w, h = rgba.size
    if w != 32 or h != 32:
        raise ValueError("mask1 only supports 32x32 input, got %dx%d" % (w, h))

    alpha = rgba.getchannel("A")
    out = bytearray(128)  # 32 rows * 4 bytes
    y = 0
    while y < 32:
        x = 0
        while x < 32:
            a = alpha.getpixel((x, y))
            if a > 0:
                byte_index = y * 4 + (x // 8)
                bit_index = 7 - (x % 8)
                out[byte_index] |= (1 << bit_index)
            x += 1
        y += 1

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(out)
    return len(out)


def main():
    parser = argparse.ArgumentParser(
        description="Convert PNG alpha to 1-bit 32x32 mask (128 bytes, row-major, bit7=left pixel)."
    )
    parser.add_argument("src", type=Path, help="Source PNG path (32x32)")
    parser.add_argument("dst", type=Path, help="Destination .mask1 path")
    args = parser.parse_args()

    size = convert_png_alpha_to_mask1(args.src, args.dst)
    print("MASK1_PATH=%s" % args.dst)
    print("MASK1_SIZE=%d" % size)


if __name__ == "__main__":
    main()

