#!/usr/bin/env python3
from pathlib import Path


def write_rgb565_bars(out_path, width=320, height=240, bar_h=40):
    colors = (0xF800, 0x07E0, 0x001F, 0xFFFF, 0x8410, 0x0000)
    data = bytearray(width * height * 2)
    i = 0
    for y in range(height):
        band = y // bar_h
        if band < 0:
            band = 0
        if band >= len(colors):
            band = len(colors) - 1
        c = colors[band]
        lo = c & 0xFF
        hi = (c >> 8) & 0xFF
        for _x in range(width):
            data[i] = lo
            data[i + 1] = hi
            i += 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return len(data)


def main():
    out = Path("/workspace/esp/esp/project_root/sd_game_template/game/picture/backgound/test_bars.rgb565")
    size = write_rgb565_bars(out)
    print("OK path=%s size=%d" % (out, size))


if __name__ == "__main__":
    main()
