#!/usr/bin/env python3
from pathlib import Path


def write_grid_rgb565(out_path, width=320, height=240):
    data = bytearray(width * height * 2)
    i = 0
    for y in range(height):
        for x in range(width):
            color = 0x0000
            if (x & 0x0F) == 0 or (y & 0x0F) == 0:
                color = 0x7BEF  # light gray grid
            if x == y:
                color = 0xFFE0  # yellow diagonal

            if x < 32 and y < 32:
                color = 0xF800  # red
            elif x >= (width - 32) and y < 32:
                color = 0x07E0  # green
            elif x < 32 and y >= (height - 32):
                color = 0x001F  # blue
            elif x >= (width - 32) and y >= (height - 32):
                color = 0xFFFF  # white

            data[i] = color & 0xFF
            data[i + 1] = (color >> 8) & 0xFF
            i += 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return len(data)


def main():
    out = Path("/workspace/esp/esp/project_root/sd_game_template/game/picture/backgound/test_grid.rgb565")
    size = write_grid_rgb565(out, 320, 240)
    print("OK path=%s size=%d" % (out, size))


if __name__ == "__main__":
    main()
