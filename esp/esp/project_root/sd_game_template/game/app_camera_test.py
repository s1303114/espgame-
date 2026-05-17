import config

try:
    import lgfx as _lgfx
except Exception:
    _lgfx = None

try:
    import os
except Exception:
    os = None

try:
    from time import ticks_diff, ticks_ms, ticks_us, sleep_ms
except Exception:
    from time import sleep as _sleep
    import time as _time

    def ticks_ms():
        return int(_time.time() * 1000)

    def ticks_diff(a, b):
        return a - b

    def ticks_us():
        return int(_time.time() * 1000000)

    def sleep_ms(ms):
        _sleep(ms / 1000)

try:
    import gc
except Exception:
    gc = None

try:
    from engine.font_zh import draw_digits_to_buf as _draw_digits_to_buf
    from engine.font_zh import get_digits_text_width as _get_digits_text_width
except Exception:
    _draw_digits_to_buf = None
    _get_digits_text_width = None


_boot_source_tag = "UNKNOWN"

_MODE_COLOR = "COLOR"
_MODE_PNG_SINGLE = "PNG_SINGLE"
_MODE_PNG_FULL = "PNG_FULL"
_MODE_FAR_ONLY = "FAR_ONLY"
_MODE_SINGLE_IMAGE_STRIP = "SINGLE_IMAGE_STRIP"
_MODE_SINGLE_IMAGE_DIRECT = "SINGLE_IMAGE_DIRECT"
_MODE_DIRECT_BG_ONLY = "DIRECT_BG_ONLY"
_MODE_DIRECT_RGB565_BG_ONLY = "DIRECT_RGB565_BG_ONLY"
_MODE_ROOT_FAR_RGB565_ONLY = "ROOT_FAR_RGB565_ONLY"
_MODE_BOARD_GENERATED_RGB565_TEST = "BOARD_GENERATED_RGB565_TEST"
_MODE_ROOT_RGB565_TEST_PATTERN = "ROOT_RGB565_TEST_PATTERN"
_MODE_BOARD_GENERATED_GRID_TEST = "BOARD_GENERATED_GRID_TEST"
_MODE_ROOT_RGB565_GRID_PATTERN = "ROOT_RGB565_GRID_PATTERN"
_MODE_BLIT_SINGLE_BLOCK_TEST = "BLIT_SINGLE_BLOCK_TEST"
_MODE_BLIT_FULL_BUFFER_TEST = "BLIT_FULL_BUFFER_TEST"
_MODE_BLIT_ROWS_GRID_TEST = "BLIT_ROWS_GRID_TEST"
_MODE_ROWS_SAFE_PROGRESSIVE = "ROWS_SAFE_PROGRESSIVE"
_MODE_ROWS_SAFE_NEAR_TILE_TEST = "ROWS_SAFE_NEAR_TILE_TEST"
_MODE_FULL_BUFFER_TEST = "FULL_BUFFER_TEST"
_MODE_SPI_TFT_SPEED_TEST = "SPI_TFT_SPEED_TEST"
_MODE_SPI_TFT_BULK_WAIT_TEST = "SPI_TFT_BULK_WAIT_TEST"


def _resolve_asset_path(path):
    p = str(path)
    if p.startswith("/"):
        return p
    if p.startswith("sd/"):
        return "/" + p
    return "/sd/" + p


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _fill_buffer_color565(buf, pixel_count, color):
    lo = int(color) & 0xFF
    hi = (int(color) >> 8) & 0xFF
    i = 0
    j = 0
    while i < pixel_count:
        buf[j] = lo
        buf[j + 1] = hi
        i += 1
        j += 2


def _fill_buffer_rect565(buf, buf_w, x, y, w, h, color):
    if w <= 0 or h <= 0:
        return
    lo = int(color) & 0xFF
    hi = (int(color) >> 8) & 0xFF
    row = 0
    while row < h:
        base = ((y + row) * buf_w + x) * 2
        col = 0
        while col < w:
            idx = base + (col * 2)
            buf[idx] = lo
            buf[idx + 1] = hi
            col += 1
        row += 1


def _fill_buffer_rect565_rowcopy(buf, buf_w, x, y, w, h, color, row_cache):
    if w <= 0 or h <= 0:
        return
    key = (w, int(color) & 0xFFFF)
    row_bytes = row_cache.get(key)
    if row_bytes is None:
        lo = int(color) & 0xFF
        hi = (int(color) >> 8) & 0xFF
        rb = bytearray(w * 2)
        i = 0
        while i < (w * 2):
            rb[i] = lo
            rb[i + 1] = hi
            i += 2
        row_bytes = bytes(rb)
        row_cache[key] = row_bytes
    row = 0
    while row < h:
        base = ((y + row) * buf_w + x) * 2
        buf[base : base + (w * 2)] = row_bytes
        row += 1


def _clip_rect_screen_xywh(x, y, w, h, screen_w, screen_h):
    if w <= 0 or h <= 0:
        return None
    x0 = 0 if x < 0 else x
    y0 = 0 if y < 0 else y
    x1 = screen_w if (x + w) > screen_w else (x + w)
    y1 = screen_h if (y + h) > screen_h else (y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def _merge_rects_to_vertical_bands(rects):
    if not rects:
        return []
    iv = []
    i = 0
    while i < len(rects):
        ry0 = rects[i][1]
        ry1 = ry0 + rects[i][3]
        iv.append((ry0, ry1))
        i += 1
    iv.sort()
    merged = []
    cy0, cy1 = iv[0]
    i = 1
    while i < len(iv):
        ny0, ny1 = iv[i]
        if ny0 <= cy1:
            if ny1 > cy1:
                cy1 = ny1
        else:
            merged.append((cy0, cy1))
            cy0, cy1 = ny0, ny1
        i += 1
    merged.append((cy0, cy1))
    return merged


def _compose_floor_layer_rows(
    scene_buf,
    scene_w,
    scene_h,
    band_top,
    camera_x,
    floor_rgb_fp,
    floor_mask_fp,
    floor_w,
    floor_h,
    floor_screen_y,
    floor_scroll_factor,
    floor_scroll_x_offset,
    floor_runs_by_row,
    floor_rgb_data,
):
    if floor_runs_by_row is None:
        return
    if floor_rgb_data is None and floor_rgb_fp is None:
        return
    floor_src_x = int(camera_x * float(floor_scroll_factor)) + int(floor_scroll_x_offset)
    row_rgb = bytearray(scene_w * 2)
    row = 0
    while row < scene_h:
        screen_y = band_top + row
        src_y = screen_y - floor_screen_y
        if src_y < 0 or src_y >= floor_h:
            row += 1
            continue
        src_x0 = floor_src_x
        src_x1 = floor_src_x + scene_w
        read_x0 = src_x0 if src_x0 > 0 else 0
        read_x1 = src_x1 if src_x1 < floor_w else floor_w
        if read_x1 <= read_x0:
            row += 1
            continue

        visible_w = read_x1 - read_x0
        dst_x0 = read_x0 - src_x0
        rgb_off = ((src_y * floor_w) + read_x0) * 2
        if floor_rgb_data is not None:
            rgb_b0 = rgb_off
            rgb_b1 = rgb_b0 + (visible_w * 2)
            row_rgb[: visible_w * 2] = floor_rgb_data[rgb_b0:rgb_b1]
        else:
            floor_rgb_fp.seek(rgb_off)
            n1 = floor_rgb_fp.readinto(memoryview(row_rgb)[: visible_w * 2])
            if n1 != (visible_w * 2):
                row += 1
                continue

        runs = floor_runs_by_row[src_y]
        if not runs:
            row += 1
            continue

        i = 0
        while i < len(runs):
            run = runs[i]
            rx0 = run[0]
            rx1 = run[1]
            if rx1 <= read_x0:
                i += 1
                continue
            if rx0 >= read_x1:
                break
            ix0 = read_x0 if rx0 < read_x0 else rx0
            ix1 = read_x1 if rx1 > read_x1 else rx1
            if ix1 > ix0:
                src_b0 = (ix0 - read_x0) * 2
                src_b1 = (ix1 - read_x0) * 2
                dst_b0 = ((row * scene_w) + (dst_x0 + (ix0 - read_x0))) * 2
                scene_buf[dst_b0 : dst_b0 + (src_b1 - src_b0)] = row_rgb[src_b0:src_b1]
            i += 1
        row += 1


def _compose_floor_layer_strip_rows(
    scene_buf,
    scene_w,
    scene_h,
    band_top,
    strip_x,
    strip_w,
    camera_x,
    floor_rgb_fp,
    floor_w,
    floor_h,
    floor_screen_y,
    floor_scroll_factor,
    floor_scroll_x_offset,
    floor_runs_by_row,
    far_bg_buf,
    floor_rgb_data,
):
    if strip_w <= 0:
        return
    floor_src_x = int(camera_x * float(floor_scroll_factor)) + int(floor_scroll_x_offset)
    row_rgb = bytearray(strip_w * 2)
    row = 0
    row_bytes = scene_w * 2
    strip_bytes = strip_w * 2
    while row < scene_h:
        # Restore far background for this strip first.
        dst_b0 = row * row_bytes + (strip_x * 2)
        dst_b1 = dst_b0 + strip_bytes
        scene_buf[dst_b0:dst_b1] = far_bg_buf[dst_b0:dst_b1]

        screen_y = band_top + row
        src_y = screen_y - floor_screen_y
        if src_y < 0 or src_y >= floor_h:
            row += 1
            continue
        runs = floor_runs_by_row[src_y]
        if not runs:
            row += 1
            continue

        src_x0 = strip_x + floor_src_x
        src_x1 = src_x0 + strip_w
        read_x0 = src_x0 if src_x0 > 0 else 0
        read_x1 = src_x1 if src_x1 < floor_w else floor_w
        if read_x1 <= read_x0:
            row += 1
            continue

        visible_w = read_x1 - read_x0
        rgb_off = ((src_y * floor_w) + read_x0) * 2
        if floor_rgb_data is not None:
            rgb_b0 = rgb_off
            rgb_b1 = rgb_b0 + (visible_w * 2)
            row_rgb[: visible_w * 2] = floor_rgb_data[rgb_b0:rgb_b1]
        else:
            floor_rgb_fp.seek(rgb_off)
            n1 = floor_rgb_fp.readinto(memoryview(row_rgb)[: visible_w * 2])
            if n1 != (visible_w * 2):
                row += 1
                continue

        i = 0
        while i < len(runs):
            rx0 = runs[i][0]
            rx1 = runs[i][1]
            if rx1 <= read_x0:
                i += 1
                continue
            if rx0 >= read_x1:
                break
            ix0 = read_x0 if rx0 < read_x0 else rx0
            ix1 = read_x1 if rx1 > read_x1 else rx1
            if ix1 > ix0:
                src_b0 = (ix0 - read_x0) * 2
                src_b1 = (ix1 - read_x0) * 2
                # Convert floor source x back to screen strip x.
                sx0 = strip_x + (ix0 - src_x0)
                dst_b0 = ((row * scene_w) + sx0) * 2
                scene_buf[dst_b0 : dst_b0 + (src_b1 - src_b0)] = row_rgb[src_b0:src_b1]
            i += 1
        row += 1


def _build_floor_runs_by_row(mask_fp, floor_w, floor_h):
    row_bytes = (floor_w + 7) // 8
    row_mask = bytearray(row_bytes)
    out = []
    y = 0
    while y < floor_h:
        mask_fp.seek(y * row_bytes)
        n = mask_fp.readinto(row_mask)
        if n != row_bytes:
            out.append(())
            y += 1
            continue
        runs = []
        x = 0
        while x < floor_w:
            bi = x >> 3
            bb = 7 - (x & 7)
            if ((row_mask[bi] >> bb) & 1) == 0:
                x += 1
                continue
            x0 = x
            x += 1
            while x < floor_w:
                bi = x >> 3
                bb = 7 - (x & 7)
                if ((row_mask[bi] >> bb) & 1) == 0:
                    break
                x += 1
            runs.append((x0, x))
        out.append(tuple(runs))
        y += 1
    return tuple(out)


def _blit_scene_rect565_rows(scene_buf, scene_w, scene_h, band_top, rx, ry, rw, rh, tmp_buf):
    if rw <= 0 or rh <= 0:
        return tmp_buf, 0
    if rx < 0:
        rw += rx
        rx = 0
    if ry < 0:
        rh += ry
        ry = 0
    if rx + rw > scene_w:
        rw = scene_w - rx
    if ry + rh > scene_h:
        rh = scene_h - ry
    if rw <= 0 or rh <= 0:
        return tmp_buf, 0

    need = rw * rh * 2
    if tmp_buf is None or len(tmp_buf) < need:
        tmp_buf = bytearray(need)

    row_bytes = scene_w * 2
    copy_row_bytes = rw * 2
    dst_off = 0
    r = 0
    while r < rh:
        src_b0 = ((ry + r) * row_bytes) + (rx * 2)
        src_b1 = src_b0 + copy_row_bytes
        tmp_buf[dst_off : dst_off + copy_row_bytes] = scene_buf[src_b0:src_b1]
        dst_off += copy_row_bytes
        r += 1

    _lgfx.blit_rect565_rows(rx, band_top + ry, rw, rh, memoryview(tmp_buf)[:need])
    return tmp_buf, 1


def _blend_sprite32_mask1_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    dst_x,
    dst_y,
    sprite_rgb565,
    sprite_mask1,
):
    sprite_w = 32
    if dst_x < 0:
        dst_start_x = 0
        src_start_x = -dst_x
        visible_w = sprite_w - src_start_x
    else:
        dst_start_x = dst_x
        src_start_x = 0
        rem = scene_w - dst_x
        visible_w = sprite_w if sprite_w < rem else rem

    if visible_w <= 0:
        return
    src_end_x = src_start_x + visible_w
    sy = 0
    while sy < 32:
        dy = dst_y + sy
        if dy < 0 or dy >= scene_h:
            sy += 1
            continue
        sx = src_start_x
        dx = dst_start_x
        while sx < src_end_x:
            byte_index = sy * 4 + (sx // 8)
            bit_index = 7 - (sx % 8)
            visible = (sprite_mask1[byte_index] >> bit_index) & 1
            if visible:
                src_off = ((sy * 32) + sx) * 2
                dst_off = ((dy * scene_w) + dx) * 2
                scene_buf[dst_off] = sprite_rgb565[src_off]
                scene_buf[dst_off + 1] = sprite_rgb565[src_off + 1]
            sx += 1
            dx += 1
        sy += 1


def _build_sprite_segments_32(mask1):
    # Packed format: [row, x0, run_len, src_off_lo, src_off_hi]...
    segs = bytearray()
    sy = 0
    while sy < 32:
        sx = 0
        while sx < 32:
            byte_index = sy * 4 + (sx // 8)
            bit_index = 7 - (sx % 8)
            visible = (mask1[byte_index] >> bit_index) & 1
            if visible == 0:
                sx += 1
                continue
            x0 = sx
            sx += 1
            while sx < 32:
                b2 = sy * 4 + (sx // 8)
                k2 = 7 - (sx % 8)
                if ((mask1[b2] >> k2) & 1) == 0:
                    break
                sx += 1
            run_len = sx - x0
            src_off = ((sy * 32) + x0) * 2
            segs.append(sy & 0xFF)
            segs.append(x0 & 0xFF)
            segs.append(run_len & 0xFF)
            segs.append(src_off & 0xFF)
            segs.append((src_off >> 8) & 0xFF)
        sy += 1
    return bytes(segs)


def _blend_sprite_segments_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    dst_x,
    dst_y,
    sprite_rgb565,
    sprite_segments,
):
    i = 0
    n = len(sprite_segments)
    while i + 4 < n:
        sy = sprite_segments[i]
        x0 = sprite_segments[i + 1]
        run_len = sprite_segments[i + 2]
        src_off = sprite_segments[i + 3] | (sprite_segments[i + 4] << 8)
        dy = dst_y + sy
        if dy < 0 or dy >= scene_h:
            i += 5
            continue
        rx0 = dst_x + x0
        rx1 = rx0 + run_len
        if rx1 <= 0 or rx0 >= scene_w:
            i += 5
            continue
        clip_l = 0
        clip_r = 0
        if rx0 < 0:
            clip_l = -rx0
            rx0 = 0
        if rx1 > scene_w:
            clip_r = rx1 - scene_w
            rx1 = scene_w
        copy_px = run_len - clip_l - clip_r
        if copy_px > 0:
            dst_off = ((dy * scene_w) + rx0) * 2
            src2 = src_off + (clip_l * 2)
            scene_buf[dst_off : dst_off + (copy_px * 2)] = sprite_rgb565[src2 : src2 + (copy_px * 2)]
        i += 5


def _compose_grid_chunk565(buf, screen_w, screen_h, strip_y, strip_h):
    line_color = 0x7BEF  # light gray
    diag_color = 0xFFE0  # yellow
    i = 0
    row = 0
    while row < strip_h:
        y = strip_y + row
        col = 0
        while col < screen_w:
            x = col
            color = 0x0000

            if (x & 0x0F) == 0 or (y & 0x0F) == 0:
                color = line_color
            if x == y:
                color = diag_color

            # Corner blocks override lines/diagonal.
            if x < 32 and y < 32:
                color = 0xF800  # red
            elif x >= (screen_w - 32) and y < 32:
                color = 0x07E0  # green
            elif x < 32 and y >= (screen_h - 32):
                color = 0x001F  # blue
            elif x >= (screen_w - 32) and y >= (screen_h - 32):
                color = 0xFFFF  # white

            buf[i] = color & 0xFF
            buf[i + 1] = (color >> 8) & 0xFF
            i += 2
            col += 1
        row += 1


def _compose_block_32x32_quads(buf):
    # 32x32: TL red, TR green, BL blue, BR white
    i = 0
    y = 0
    while y < 32:
        x = 0
        while x < 32:
            if y < 16:
                color = 0xF800 if x < 16 else 0x07E0
            else:
                color = 0x001F if x < 16 else 0xFFFF
            buf[i] = color & 0xFF
            buf[i + 1] = (color >> 8) & 0xFF
            i += 2
            x += 1
        y += 1


def _compose_full_grid_320x240(buf):
    _compose_grid_chunk565(buf, 320, 240, 0, 240)


def _normalize_mode(v):
    m = str(v).upper()
    if m in (
        _MODE_COLOR,
        _MODE_PNG_SINGLE,
        _MODE_PNG_FULL,
        _MODE_FAR_ONLY,
        _MODE_SINGLE_IMAGE_STRIP,
        _MODE_SINGLE_IMAGE_DIRECT,
        _MODE_DIRECT_BG_ONLY,
        _MODE_DIRECT_RGB565_BG_ONLY,
        _MODE_ROOT_FAR_RGB565_ONLY,
        _MODE_BOARD_GENERATED_RGB565_TEST,
        _MODE_ROOT_RGB565_TEST_PATTERN,
        _MODE_BOARD_GENERATED_GRID_TEST,
        _MODE_ROOT_RGB565_GRID_PATTERN,
        _MODE_BLIT_SINGLE_BLOCK_TEST,
        _MODE_BLIT_FULL_BUFFER_TEST,
        _MODE_BLIT_ROWS_GRID_TEST,
        _MODE_ROWS_SAFE_PROGRESSIVE,
        _MODE_ROWS_SAFE_NEAR_TILE_TEST,
        _MODE_FULL_BUFFER_TEST,
        _MODE_SPI_TFT_SPEED_TEST,
        _MODE_SPI_TFT_BULK_WAIT_TEST,
    ):
        return m
    return _MODE_PNG_FULL


class _CameraTestRuntime:
    __slots__ = (
        "map_w",
        "map_h",
        "player_x",
        "player_y",
        "player_w",
        "player_h",
        "player_vx",
        "camera_x",
        "prev_camera_x",
        "camera_anchor",
        "strip_h",
        "stripbuf",
        "submit_count",
        "submit_violation",
        "blits_last_frame",
        "max_blits_in_frame",
        "input_system",
        "prev_player_rect",
        "mode",
        "png_single_stage",
        "draw_count",
    )

    def __init__(self):
        self.map_w = int(getattr(config, "CAMERA_TEST_MAP_W", 960))
        self.map_h = int(getattr(config, "CAMERA_TEST_MAP_H", 240))
        self.player_w = int(getattr(config, "CAMERA_TEST_PLAYER_W", 12))
        self.player_h = int(getattr(config, "CAMERA_TEST_PLAYER_H", 16))
        self.player_x = int(getattr(config, "CAMERA_TEST_PLAYER_START_X", 32))
        self.player_y = int(getattr(config, "CAMERA_TEST_PLAYER_START_Y", self.map_h - self.player_h - 16))
        self.player_vx = 0
        self.camera_x = 0
        self.prev_camera_x = -1
        self.camera_anchor = config.SCREEN_W // 2

        self.mode = _normalize_mode(getattr(config, "CAMERA_TEST_MODE", _MODE_PNG_FULL))
        self.png_single_stage = int(getattr(config, "CAMERA_TEST_PNG_SINGLE_STAGE", 1))
        if self.png_single_stage < 1:
            self.png_single_stage = 1
        if self.png_single_stage > 3:
            self.png_single_stage = 3

        self.strip_h = int(getattr(config, "CAMERA_TEST_STRIP_H", 30))
        if self.strip_h < 1:
            self.strip_h = 1
        if self.strip_h > config.SCREEN_H:
            self.strip_h = config.SCREEN_H
        self.stripbuf = bytearray(config.SCREEN_W * self.strip_h * 2)

        self.submit_count = 0
        self.submit_violation = False
        self.blits_last_frame = 0
        self.max_blits_in_frame = 0
        self.input_system = None
        self.prev_player_rect = None
        self.draw_count = 0

        try:
            from engine.input import InputSystem

            self.input_system = InputSystem()
        except Exception:
            self.input_system = None

    def _camera_max_x(self):
        v = self.map_w - config.SCREEN_W
        return v if v > 0 else 0

    def _read_axis(self, now_ms):
        if self.input_system is None:
            # Fallback scripted motion for environments without input.
            phase = (now_ms // 1000) % 4
            if phase in (0, 1):
                return 60
            return -60
        self.input_system.update(now_ms)
        return int(getattr(self.input_system, "joy_x_axis", 0))

    def update(self, now_ms):
        if self.mode in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT):
            return

        axis = self._read_axis(now_ms)
        if axis > 20:
            self.player_vx = int(getattr(config, "PLAYER_SPEED_X", 2))
        elif axis < -20:
            self.player_vx = -int(getattr(config, "PLAYER_SPEED_X", 2))
        else:
            self.player_vx = 0

        self.player_x += self.player_vx
        max_player_x = self.map_w - self.player_w
        if max_player_x < 0:
            max_player_x = 0
        self.player_x = _clamp(self.player_x, 0, max_player_x)

        self.prev_camera_x = self.camera_x
        self.camera_x = _clamp(self.player_x - self.camera_anchor, 0, self._camera_max_x())

    def _draw_tilemap_ground(self, strip_view, strip_y, strip_h):
        ground_y = self.map_h - 16
        y0 = strip_y if strip_y > ground_y else ground_y
        y1 = (strip_y + strip_h) if (strip_y + strip_h) < self.map_h else self.map_h
        if y1 <= y0:
            return
        _fill_buffer_rect565(
            strip_view,
            config.SCREEN_W,
            0,
            y0 - strip_y,
            config.SCREEN_W,
            y1 - y0,
            config.COLOR_TILE_SOLID,
        )

    def _draw_player(self, strip_view, strip_y, strip_h):
        px0 = self.player_x - self.camera_x
        py0 = self.player_y
        px1 = px0 + self.player_w
        py1 = py0 + self.player_h
        sx0 = 0 if px0 < 0 else px0
        sy0 = strip_y if py0 < strip_y else py0
        sx1 = config.SCREEN_W if px1 > config.SCREEN_W else px1
        sy1 = (strip_y + strip_h) if py1 > (strip_y + strip_h) else py1
        if sx1 <= sx0 or sy1 <= sy0:
            return
        _fill_buffer_rect565(
            strip_view,
            config.SCREEN_W,
            sx0,
            sy0 - strip_y,
            sx1 - sx0,
            sy1 - sy0,
            config.COLOR_PLAYER,
        )

    def _compose_color_layer(self, strip_view, strip_y, strip_h, layer_x, layer_w, color):
        x0 = layer_x
        x1 = layer_x + layer_w
        if x0 < 0:
            x0 = 0
        if x1 > config.SCREEN_W:
            x1 = config.SCREEN_W
        if x1 <= x0:
            return
        _fill_buffer_rect565(strip_view, config.SCREEN_W, x0, 0, x1 - x0, strip_h, color)

    def _compose_bg_color(self, strip_view, strip_y, strip_h, far_x, mid_x, near_x):
        try:
            self._compose_color_layer(strip_view, strip_y, strip_h, far_x, 320, 0x39E7)   # gray
            self._compose_color_layer(strip_view, strip_y, strip_h, mid_x, 640, 0x07E0)   # green
            self._compose_color_layer(strip_view, strip_y, strip_h, near_x, 960, 0x001F)  # blue
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_COLOR_RENDER")

    def _compose_bg_png_full(self, strip_view, strip_y, strip_h, far_x, mid_x, near_x):
        try:
            _lgfx.png_over_rect565(
                getattr(config, "CAMERA_TEST_BG_FAR"),
                -far_x,
                strip_y,
                config.SCREEN_W,
                strip_h,
                strip_view,
            )
            _lgfx.png_over_rect565(
                getattr(config, "CAMERA_TEST_BG_MID"),
                -mid_x,
                strip_y,
                config.SCREEN_W,
                strip_h,
                strip_view,
            )
            _lgfx.png_over_rect565(
                getattr(config, "CAMERA_TEST_BG_NEAR"),
                -near_x,
                strip_y,
                config.SCREEN_W,
                strip_h,
                strip_view,
            )
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_PNG_LAYER")

    def _compose_bg_png_single(self, strip_view, strip_y, strip_h, far_x, mid_x, near_x):
        try:
            stage = self.png_single_stage
            # Stage 1: near only.
            if stage >= 3:
                _lgfx.png_over_rect565(
                    getattr(config, "CAMERA_TEST_BG_FAR"),
                    -far_x,
                    strip_y,
                    config.SCREEN_W,
                    strip_h,
                    strip_view,
                )
            if stage >= 2:
                _lgfx.png_over_rect565(
                    getattr(config, "CAMERA_TEST_BG_MID"),
                    -mid_x,
                    strip_y,
                    config.SCREEN_W,
                    strip_h,
                    strip_view,
                )
            _lgfx.png_over_rect565(
                getattr(config, "CAMERA_TEST_BG_NEAR"),
                -near_x,
                strip_y,
                config.SCREEN_W,
                strip_h,
                strip_view,
            )
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_PNG_LAYER")

    def _compose_bg_far_only(self, strip_view, strip_y, strip_h):
        try:
            _lgfx.png_over_rect565(
                getattr(config, "CAMERA_TEST_BG_FAR"),
                0,
                strip_y,
                config.SCREEN_W,
                strip_h,
                strip_view,
            )
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_PNG_LAYER")

    def _compose_bg_single_image_strip(self, strip_view, strip_y, strip_h):
        try:
            _lgfx.png_rect565(
                getattr(config, "CAMERA_TEST_BG_FAR"),
                0,
                strip_y,
                config.SCREEN_W,
                strip_h,
                strip_view,
            )
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_PNG_LAYER")

    def _compose_strip(self, strip_idx, strip_y, strip_h):
        strip_bytes = config.SCREEN_W * strip_h * 2
        strip_view = memoryview(self.stripbuf)[:strip_bytes]

        print(
            "CAMERA_TEST_STRIP idx=%d x=%d y=%d w=%d h=%d"
            % (strip_idx, 0, strip_y, config.SCREEN_W, strip_h)
        )

        clear_ok = False
        compose_ok = False
        submit_ok = False
        try:
            _fill_buffer_color565(strip_view, config.SCREEN_W * strip_h, config.COLOR_BG)
            clear_ok = True
            print("CAMERA_TEST_STRIP_CLEAR_OK idx=%d" % strip_idx)

            far_x = 0
            mid_x = -(self.camera_x // 2)
            near_x = -self.camera_x

            if self.mode == _MODE_SINGLE_IMAGE_STRIP:
                self._compose_bg_single_image_strip(strip_view, strip_y, strip_h)
            elif self.mode == _MODE_COLOR:
                self._compose_bg_color(strip_view, strip_y, strip_h, far_x, mid_x, near_x)
            elif self.mode == _MODE_FAR_ONLY:
                self._compose_bg_far_only(strip_view, strip_y, strip_h)
            elif self.mode == _MODE_PNG_SINGLE:
                self._compose_bg_png_single(strip_view, strip_y, strip_h, far_x, mid_x, near_x)
            else:
                self._compose_bg_png_full(strip_view, strip_y, strip_h, far_x, mid_x, near_x)

            if self.mode not in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT):
                self._draw_tilemap_ground(strip_view, strip_y, strip_h)
                self._draw_player(strip_view, strip_y, strip_h)
            compose_ok = True
            print("CAMERA_TEST_STRIP_COMPOSE_OK idx=%d" % strip_idx)

            _lgfx.blit_rect565(0, strip_y, config.SCREEN_W, strip_h, strip_view)
            submit_ok = True
            print("CAMERA_TEST_STRIP_SUBMIT_OK idx=%d" % strip_idx)
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_STRIP_COMPOSE")
        finally:
            if not clear_ok:
                print("CAMERA_TEST_FAIL_STRIP_COMPOSE idx=%d reason=clear" % strip_idx)
            if clear_ok and not compose_ok:
                print("CAMERA_TEST_FAIL_STRIP_COMPOSE idx=%d reason=compose" % strip_idx)
            if compose_ok and not submit_ok:
                print("CAMERA_TEST_FAIL_STRIP_COMPOSE idx=%d reason=submit" % strip_idx)

    def _draw_single_image_direct(self):
        block_candidates = (240, 120, 80, 60, 40, 30, 24, 20, 16, 12, 8)
        buf = None
        block_h = 0
        i = 0
        while i < len(block_candidates):
            candidate = block_candidates[i]
            if candidate > config.SCREEN_H:
                candidate = config.SCREEN_H
            if candidate < 1:
                candidate = 1
            try:
                buf = bytearray(config.SCREEN_W * candidate * 2)
                block_h = candidate
                break
            except Exception:
                buf = None
                i += 1

        if buf is None:
            raise RuntimeError("CAMERA_TEST_FAIL_SINGLE_IMAGE_DIRECT_ALLOC")

        blits = 0
        y = 0
        try:
            while y < config.SCREEN_H:
                h = block_h
                if y + h > config.SCREEN_H:
                    h = config.SCREEN_H - y
                view = memoryview(buf)[: config.SCREEN_W * h * 2]
                _lgfx.png_rect565(
                    getattr(config, "CAMERA_TEST_BG_FAR"),
                    0,
                    y,
                    config.SCREEN_W,
                    h,
                    view,
                )
                _lgfx.blit_rect565(0, y, config.SCREEN_W, h, view)
                blits += 1
                y += h
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_PNG_LAYER")

        return blits

    def draw(self):
        if self.mode == _MODE_SINGLE_IMAGE_DIRECT:
            direct_blits = self._draw_single_image_direct()
            self.blits_last_frame = direct_blits
            if self.max_blits_in_frame < direct_blits:
                self.max_blits_in_frame = direct_blits
            self.submit_count += direct_blits
            self.submit_violation = False
            self.draw_count += 1
            print("CAMERA_TEST_DRAW_OK frame=%d blits=%d" % (self.draw_count, direct_blits))
            print("CAMERA_TEST_SINGLE_IMAGE_DRAW_OK frame=%d" % self.draw_count)
            return

        if self.mode == _MODE_SINGLE_IMAGE_STRIP:
            submits_this_frame = 0
            y = 0
            strip_idx = 0
            while y < config.SCREEN_H:
                sh = self.strip_h
                if y + sh > config.SCREEN_H:
                    sh = config.SCREEN_H - y
                self._compose_strip(strip_idx, y, sh)
                submits_this_frame += 1
                y += sh
                strip_idx += 1

            if submits_this_frame <= 0:
                raise RuntimeError("CAMERA_TEST_FAIL_MULTI_SUBMIT")

            self.blits_last_frame = submits_this_frame
            if submits_this_frame > self.max_blits_in_frame:
                self.max_blits_in_frame = submits_this_frame
            self.submit_count += submits_this_frame
            self.submit_violation = False
            self.draw_count += 1
            print("CAMERA_TEST_DRAW_OK frame=%d blits=%d" % (self.draw_count, submits_this_frame))
            print("CAMERA_TEST_SINGLE_IMAGE_DRAW_OK frame=%d" % self.draw_count)
            return

        camera_moved = self.camera_x != self.prev_camera_x
        do_redraw = camera_moved

        if not do_redraw:
            curr = (
                self.player_x - self.camera_x,
                self.player_y,
                self.player_w,
                self.player_h,
            )
            do_redraw = self.prev_player_rect != curr
            self.prev_player_rect = curr
        else:
            self.prev_player_rect = (
                self.player_x - self.camera_x,
                self.player_y,
                self.player_w,
                self.player_h,
            )

        if not do_redraw:
            return

        submits_this_frame = 0
        y = 0
        strip_idx = 0
        while y < config.SCREEN_H:
            sh = self.strip_h
            if y + sh > config.SCREEN_H:
                sh = config.SCREEN_H - y
            self._compose_strip(strip_idx, y, sh)
            submits_this_frame += 1
            y += sh
            strip_idx += 1

        if submits_this_frame <= 0:
            raise RuntimeError("CAMERA_TEST_FAIL_MULTI_SUBMIT")

        self.blits_last_frame = submits_this_frame
        if submits_this_frame > self.max_blits_in_frame:
            self.max_blits_in_frame = submits_this_frame
        self.submit_count += submits_this_frame
        self.submit_violation = False
        self.draw_count += 1
        print("CAMERA_TEST_DRAW_OK frame=%d blits=%d" % (self.draw_count, submits_this_frame))
        if self.mode == _MODE_FAR_ONLY:
            print("CAMERA_TEST_FAR_ONLY_DRAW_OK frame=%d" % self.draw_count)


def _ensure_prerequisites(mode, png_single_stage):
    if _lgfx is None:
        raise RuntimeError("CAMERA_TEST_FAIL_NO_LGFX")
    if not hasattr(_lgfx, "blit_rect565"):
        raise RuntimeError("CAMERA_TEST_FAIL_NO_BLIT")
    if os is None:
        raise RuntimeError("CAMERA_TEST_FAIL_NO_OS")

    needs_png = mode not in (
        _MODE_COLOR,
        _MODE_DIRECT_RGB565_BG_ONLY,
        _MODE_ROOT_FAR_RGB565_ONLY,
        _MODE_BOARD_GENERATED_RGB565_TEST,
        _MODE_ROOT_RGB565_TEST_PATTERN,
        _MODE_BOARD_GENERATED_GRID_TEST,
        _MODE_ROOT_RGB565_GRID_PATTERN,
        _MODE_BLIT_SINGLE_BLOCK_TEST,
        _MODE_BLIT_FULL_BUFFER_TEST,
        _MODE_BLIT_ROWS_GRID_TEST,
        _MODE_ROWS_SAFE_PROGRESSIVE,
        _MODE_ROWS_SAFE_NEAR_TILE_TEST,
        _MODE_FULL_BUFFER_TEST,
        _MODE_SPI_TFT_SPEED_TEST,
        _MODE_SPI_TFT_BULK_WAIT_TEST,
    )
    if mode == _MODE_BLIT_ROWS_GRID_TEST and not hasattr(_lgfx, "blit_rect565_rows"):
        raise RuntimeError("CAMERA_TEST_FAIL_NO_BLIT_ROWS")
    if needs_png:
        if mode == _MODE_DIRECT_BG_ONLY:
            if not hasattr(_lgfx, "draw_png_mem"):
                raise RuntimeError("CAMERA_TEST_FAIL_NO_DRAW_PNG_MEM")
        elif mode in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT):
            if not hasattr(_lgfx, "png_rect565"):
                raise RuntimeError("CAMERA_TEST_FAIL_NO_PNG_RECT565")
        else:
            if not hasattr(_lgfx, "png_over_rect565"):
                raise RuntimeError("CAMERA_TEST_FAIL_NO_PNG_OVER_RECT565")

    if needs_png:
        if mode in (_MODE_FAR_ONLY, _MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT, _MODE_DIRECT_BG_ONLY):
            required = [getattr(config, "CAMERA_TEST_BG_FAR")]
        else:
            required = [getattr(config, "CAMERA_TEST_BG_NEAR")]
            if mode == _MODE_PNG_FULL or png_single_stage >= 2:
                required.append(getattr(config, "CAMERA_TEST_BG_MID"))
            if mode == _MODE_PNG_FULL or png_single_stage >= 3:
                required.append(getattr(config, "CAMERA_TEST_BG_FAR"))

        i = 0
        while i < len(required):
            p = required[i]
            try:
                os.stat(p)
            except Exception:
                raise RuntimeError("CAMERA_TEST_FAIL_MISSING_ASSET:%s" % p)
            i += 1

    if mode == _MODE_DIRECT_RGB565_BG_ONLY:
        far_raw = getattr(config, "CAMERA_TEST_BG_FAR_RGB565")
        try:
            st = os.stat(far_raw)
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_MISSING_RGB565:%s" % far_raw)
        expected = int(getattr(config, "CAMERA_TEST_FAR_W", 320)) * int(getattr(config, "CAMERA_TEST_MAP_H", 240)) * 2
        actual = int(st[6]) if len(st) > 6 else -1
        if actual != expected:
            raise RuntimeError("CAMERA_TEST_FAIL_RGB565_SIZE:%d!=%d" % (actual, expected))

    if mode == _MODE_ROOT_FAR_RGB565_ONLY:
        far_raw = str(getattr(config, "CAMERA_TEST_ROOT_BG_FAR_RGB565", "/bg_far.rgb565"))
        try:
            st = os.stat(far_raw)
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_MISSING_RGB565")
        expected = int(config.SCREEN_W) * int(config.SCREEN_H) * 2
        actual = int(st[6]) if len(st) > 6 else -1
        if actual != expected:
            raise RuntimeError("CAMERA_TEST_FAIL_RGB565_SIZE")

    if mode == _MODE_ROOT_RGB565_TEST_PATTERN:
        test_raw = str(getattr(config, "CAMERA_TEST_ROOT_TEST_BARS_RGB565", "/test_bars.rgb565"))
        try:
            st = os.stat(test_raw)
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_MISSING_RGB565")
        expected = int(config.SCREEN_W) * int(config.SCREEN_H) * 2
        actual = int(st[6]) if len(st) > 6 else -1
        if actual != expected:
            raise RuntimeError("CAMERA_TEST_FAIL_RGB565_SIZE")

    if mode == _MODE_ROOT_RGB565_GRID_PATTERN:
        test_raw = str(getattr(config, "CAMERA_TEST_ROOT_TEST_GRID_RGB565", "/test_grid.rgb565"))
        try:
            st = os.stat(test_raw)
        except Exception:
            raise RuntimeError("CAMERA_TEST_FAIL_MISSING_RGB565")
        expected = int(config.SCREEN_W) * int(config.SCREEN_H) * 2
        actual = int(st[6]) if len(st) > 6 else -1
        if actual != expected:
            raise RuntimeError("CAMERA_TEST_FAIL_RGB565_SIZE")

    # Hard-locked v1 geometry.
    if int(getattr(config, "CAMERA_TEST_MAP_W", 960)) != 960:
        raise RuntimeError("CAMERA_TEST_FAIL_MAP_W")
    if int(getattr(config, "CAMERA_TEST_MAP_H", 240)) != 240:
        raise RuntimeError("CAMERA_TEST_FAIL_MAP_H")
    if int(getattr(config, "CAMERA_TEST_FAR_W", 320)) != 320:
        raise RuntimeError("CAMERA_TEST_FAIL_FAR_W")
    if int(getattr(config, "CAMERA_TEST_MID_W", 640)) != 640:
        raise RuntimeError("CAMERA_TEST_FAIL_MID_W")
    if int(getattr(config, "CAMERA_TEST_NEAR_W", 960)) != 960:
        raise RuntimeError("CAMERA_TEST_FAIL_NEAR_W")


def run(max_frames=None):
    mode = _normalize_mode(getattr(config, "CAMERA_TEST_MODE", _MODE_PNG_FULL))
    png_single_stage = int(getattr(config, "CAMERA_TEST_PNG_SINGLE_STAGE", 1))
    if png_single_stage < 1:
        png_single_stage = 1
    if png_single_stage > 3:
        png_single_stage = 3

    _ensure_prerequisites(mode, png_single_stage)

    print("APP_RUN_START_PHASE_CAMERA_TEST")
    print("CAMERA_TEST_START")
    print("CAMERA_TEST_BOOT_SOURCE=%s" % _boot_source_tag)
    print("CAMERA_TEST_MODE=%s" % mode)
    if mode == _MODE_ROWS_SAFE_PROGRESSIVE:
        print("CAMERA_ROWS_SAFE_POLICY_ACTIVE")
    if mode == _MODE_FULL_BUFFER_TEST:
        print("FULL_BUFFER_TEST_START")
    if mode in (_MODE_SPI_TFT_SPEED_TEST, _MODE_SPI_TFT_BULK_WAIT_TEST):
        print("SPI_TFT_SPEED_TEST_START")
    if mode == _MODE_ROWS_SAFE_NEAR_TILE_TEST:
        print("CAMERA_TEST_NEAR_START")
    if mode == _MODE_BLIT_SINGLE_BLOCK_TEST:
        print("BLIT_SINGLE_BLOCK_START")
    if mode == _MODE_BLIT_FULL_BUFFER_TEST:
        print("BLIT_FULL_BUFFER_START")
    if mode == _MODE_BLIT_ROWS_GRID_TEST:
        print("BLIT_ROWS_GRID_START")
    if mode == _MODE_BOARD_GENERATED_GRID_TEST:
        print("CAMERA_TEST_BOARD_GRID_START")
    if mode == _MODE_ROOT_RGB565_GRID_PATTERN:
        print("CAMERA_TEST_ROOT_GRID_START")
    if mode == _MODE_BOARD_GENERATED_RGB565_TEST:
        print("CAMERA_TEST_BOARD_GENERATED_START")
    if mode == _MODE_ROOT_RGB565_TEST_PATTERN:
        print("CAMERA_TEST_ROOT_PATTERN_START")
    if mode == _MODE_ROOT_FAR_RGB565_ONLY:
        print("CAMERA_TEST_ROOT_FAR_START")
    if mode == _MODE_DIRECT_RGB565_BG_ONLY:
        print("CAMERA_TEST_DIRECT_RGB565_BG_START")
    if mode == _MODE_DIRECT_BG_ONLY:
        print("CAMERA_TEST_DIRECT_BG_START")
    if mode in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT):
        print("CAMERA_TEST_SINGLE_IMAGE_START")
    if mode == _MODE_FAR_ONLY:
        print("CAMERA_TEST_FAR_ONLY_START")
    if mode == _MODE_PNG_SINGLE:
        print("CAMERA_TEST_PNG_SINGLE_STAGE=%d" % png_single_stage)

    _lgfx.init()
    try:
        _lgfx.rotation(1)
    except Exception:
        pass

    if mode == _MODE_ROWS_SAFE_NEAR_TILE_TEST:
        if not hasattr(_lgfx, "blit_rect565_rows"):
            print("CAMERA_TEST_NEAR_FAIL_NO_BLIT_ROWS")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_NO_BLIT_ROWS")

        far_raw = str(getattr(config, "CAMERA_TEST_ROOT_BG_FAR_RGB565", "/bg_far.rgb565"))
        try:
            st = os.stat(far_raw)
        except Exception:
            print("CAMERA_TEST_NEAR_FAIL_MISSING_RGB565")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_MISSING_RGB565")

        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        expected = sw * sh * 2
        actual = int(st[6]) if len(st) > 6 else -1
        if actual != expected:
            print("CAMERA_TEST_NEAR_FAIL_RGB565_SIZE")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_RGB565_SIZE")

        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        row_bytes = sw * 2
        try:
            buf = bytearray(row_bytes * chunk_h)
        except Exception:
            print("CAMERA_TEST_NEAR_FAIL_ALLOC")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_ALLOC")

        try:
            from engine.input import InputSystem

            input_system = InputSystem()
        except Exception:
            print("CAMERA_TEST_NEAR_FAIL_NO_INPUT")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_NO_INPUT")

        player_w = int(getattr(config, "CAMERA_TEST_PLAYER_W", 12))
        player_h = int(getattr(config, "CAMERA_TEST_PLAYER_H", 16))
        player_x = int(getattr(config, "CAMERA_TEST_PLAYER_START_X", 32))
        default_player_y = sh - player_h - 16
        player_y = int(getattr(config, "CAMERA_TEST_PLAYER_START_Y", default_player_y))
        map_w = int(getattr(config, "CAMERA_TEST_MAP_W", 960))
        screen_half = sw // 2
        max_player_x = map_w - player_w
        if max_player_x < 0:
            max_player_x = 0
        camera_max = map_w - sw
        if camera_max < 0:
            camera_max = 0
        player_x = _clamp(player_x, 0, max_player_x)
        speed = int(getattr(config, "PLAYER_SPEED_X", 2))
        dbg_every = int(getattr(config, "CAMERA_TEST_NEAR_DBG_EVERY", 60))
        if dbg_every < 1:
            dbg_every = 60

        ground_h = 16
        ground_y0 = sh - ground_h
        band_top = player_y
        if band_top < 0:
            band_top = 0
        if band_top > ground_y0:
            band_top = ground_y0
        far_band_h = ground_y0 - band_top
        scene_h = sh - band_top
        if far_band_h <= 0 or scene_h <= 0:
            print("CAMERA_TEST_NEAR_FAIL_PLAYER_BAND")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_PLAYER_BAND")

        near_objects = [
            (56, 214, 24, 8, 0xF800),   # red
            (148, 220, 20, 8, 0xFFE0),  # yellow
            (236, 228, 16, 8, 0x07FF),  # cyan
        ]
        row_fill_cache = {}

        # Draw far once (fixed x=0) then cache active rows.
        with open(far_raw, "rb") as ff:
            y = 0
            while y < sh:
                h = chunk_h
                if y + h > sh:
                    h = sh - y
                need = row_bytes * h
                view = memoryview(buf)[:need]
                n = ff.readinto(view)
                if n != need:
                    print("CAMERA_TEST_NEAR_FAIL_READ")
                    raise RuntimeError("CAMERA_TEST_NEAR_FAIL_READ")
                _lgfx.blit_rect565_rows(0, y, sw, h, view)
                y += h

        far_band_buf = bytearray(sw * far_band_h * 2)
        with open(far_raw, "rb") as far_bg:
            row = 0
            while row < far_band_h:
                src_off = ((band_top + row) * sw) * 2
                far_bg.seek(src_off)
                row_off = row * sw * 2
                row_view = memoryview(far_band_buf)[row_off : row_off + (sw * 2)]
                n = far_bg.readinto(row_view)
                if n != (sw * 2):
                    print("CAMERA_TEST_NEAR_FAIL_READ")
                    raise RuntimeError("CAMERA_TEST_NEAR_FAIL_READ")
                row += 1

        ground_rows = []
        phase_off = 0
        while phase_off < 32:
            row_buf = bytearray(row_bytes)
            gx = 0
            i = 0
            while gx < sw:
                phase = ((phase_off + gx) // 16) & 1
                color = config.COLOR_TILE_SOLID if phase == 0 else 0x31A6
                row_buf[i] = color & 0xFF
                row_buf[i + 1] = (color >> 8) & 0xFF
                i += 2
                gx += 1
            ground_rows.append(row_buf)
            phase_off += 1

        scene_buf = bytearray(sw * scene_h * 2)
        far_len = len(far_band_buf)
        frame = 0
        drew_once = False
        last_tick = ticks_ms()
        perf_window_start = last_tick

        while True:
            now = ticks_ms()
            elapsed = ticks_diff(now, last_tick)
            if elapsed < config.FRAME_MS:
                sleep_ms(config.FRAME_MS - elapsed)
                continue
            last_tick = now

            input_system.update(now)
            input_lr = int(getattr(input_system, "joy_x_axis", 0))
            if input_lr > 20:
                player_x += speed
            elif input_lr < -20:
                player_x -= speed
            player_x = _clamp(player_x, 0, max_player_x)
            player_center_x = player_x + (player_w // 2)
            target_camera_x = player_center_x - screen_half
            camera_x = _clamp(target_camera_x, 0, camera_max)
            player_screen_x = player_x - camera_x

            scene_buf[:far_len] = far_band_buf
            g_row = ground_rows[camera_x & 31]
            gy = 0
            while gy < ground_h:
                off = (far_band_h + gy) * row_bytes
                scene_buf[off : off + row_bytes] = g_row
                gy += 1

            visible_count = 0
            first_screen_x = -9999
            first_world_x = -9999
            first_y = -9999
            first_w = -9999
            first_h = -9999
            collect_detail = (frame == 0)
            obj_debug_lines = [] if collect_detail else None
            i = 0
            while i < len(near_objects):
                world_x, oy, ow, oh, ocolor = near_objects[i]
                sx = int(world_x) - camera_x
                ex = sx + int(ow)
                sy = int(oy) - band_top
                ey = sy + int(oh)
                rx0 = 0 if sx < 0 else sx
                ry0 = 0 if sy < 0 else sy
                rx1 = sw if ex > sw else ex
                ry1 = scene_h if ey > scene_h else ey
                visible = 1 if (rx1 > rx0 and ry1 > ry0) else 0
                if collect_detail:
                    obj_debug_lines.append(
                        "CAMERA_NEAR_OBJ idx=%d world_x=%d screen_x=%d y=%d w=%d h=%d visible=%d"
                        % (i, int(world_x), sx, int(oy), int(ow), int(oh), visible)
                    )
                if visible:
                    visible_count += 1
                    if first_screen_x == -9999:
                        first_world_x = int(world_x)
                        first_screen_x = sx
                        first_y = int(oy)
                        first_w = int(ow)
                        first_h = int(oh)
                    _fill_buffer_rect565_rowcopy(
                        scene_buf,
                        sw,
                        rx0,
                        ry0,
                        rx1 - rx0,
                        ry1 - ry0,
                        ocolor,
                        row_fill_cache,
                    )
                i += 1

            px0 = player_screen_x
            py0 = player_y - band_top
            px1 = px0 + player_w
            py1 = py0 + player_h
            sx0 = 0 if px0 < 0 else px0
            sy0 = 0 if py0 < 0 else py0
            sx1 = sw if px1 > sw else px1
            sy1 = scene_h if py1 > scene_h else py1
            if sx1 > sx0 and sy1 > sy0:
                _fill_buffer_rect565_rowcopy(
                    scene_buf,
                    sw,
                    sx0,
                    sy0,
                    sx1 - sx0,
                    sy1 - sy0,
                    config.COLOR_PLAYER,
                    row_fill_cache,
                )

            _lgfx.blit_rect565_rows(0, band_top, sw, scene_h, scene_buf)

            frame += 1
            if not drew_once:
                print("CAMERA_TEST_NEAR_DRAW_OK")
                print("CAMERA_TEST_NEAR_HOLD")
                print("CAMERA_NEAR_VISIBLE_COUNT=%d" % visible_count)
                print("CAMERA_NEAR_FIRST_SCREEN_X=%d" % first_screen_x)
                print(
                    "CAMERA_NEAR_FIRST world_x=%d screen_x=%d y=%d w=%d h=%d"
                    % (first_world_x, first_screen_x, first_y, first_w, first_h)
                )
                if visible_count == 0:
                    print("CAMERA_TEST_NEAR_FAIL_NOT_VISIBLE")
                j = 0
                while j < len(obj_debug_lines):
                    print(obj_debug_lines[j])
                    j += 1
                drew_once = True

            if (frame % dbg_every) == 0:
                win_ms = ticks_diff(now, perf_window_start)
                if win_ms <= 0:
                    win_ms = 1
                avg_ms = win_ms / dbg_every
                fps = 1000.0 / avg_ms
                print("CAMERA_NEAR_VISIBLE_COUNT=%d" % visible_count)
                print("CAMERA_NEAR_FIRST_SCREEN_X=%d" % first_screen_x)
                if visible_count == 0:
                    print("CAMERA_TEST_NEAR_FAIL_NOT_VISIBLE")
                print("CAMERA_STEP_NEAR_PERF frame_ms=%.2f fps=%.2f" % (avg_ms, fps))
                perf_window_start = now

            if max_frames is not None and frame >= int(max_frames):
                break

        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode in (_MODE_SPI_TFT_SPEED_TEST, _MODE_SPI_TFT_BULK_WAIT_TEST):
        if not hasattr(_lgfx, "blit_rect565_rows"):
            print("SPI_TFT_FAIL_NO_ROWS_API")
            raise RuntimeError("SPI_TFT_FAIL_NO_ROWS_API")
        # Mainline lock: force full-screen bulk path only.
        path = "BULK_WAIT_DIRECT"

        if path in ("BULK_WAIT_DIRECT", "CHUNK_WAIT_DIRECT_16") and not hasattr(_lgfx, "blit_rect565_wait"):
            print("SPI_TFT_FAIL_NO_BULK_WAIT_API")
            raise RuntimeError("SPI_TFT_FAIL_NO_BULK_WAIT_API")
        if path in ("CHUNK_WAIT_COPY_16", "CHUNK_WAIT_COPY_32") and not hasattr(_lgfx, "blit_rect565_wait_copy"):
            print("SPI_TFT_FAIL_NO_BULK_WAIT_COPY_API")
            raise RuntimeError("SPI_TFT_FAIL_NO_BULK_WAIT_COPY_API")
        if path in ("CHUNK_WAIT_COPY_COMPAT_1", "CHUNK_WAIT_COPY_COMPAT_2", "CHUNK_WAIT_COPY_COMPAT_4", "CHUNK_WAIT_COPY_COMPAT_8") and not hasattr(_lgfx, "blit_rect565_wait_copy_compat"):
            print("SPI_TFT_FAIL_NO_BULK_WAIT_COPY_COMPAT_API")
            raise RuntimeError("SPI_TFT_FAIL_NO_BULK_WAIT_COPY_COMPAT_API")

        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        frame_bytes = sw * sh * 2
        try:
            frame_buf = bytearray(frame_bytes)
            fill_buf = bytearray(frame_bytes)
        except Exception:
            print("SPI_TFT_FAIL_ALLOC")
            raise RuntimeError("SPI_TFT_FAIL_ALLOC")

        print("SPI_TFT_PATH=%s" % path)
        print("SPI_TFT_ALLOC_OK")
        if path in ("BULK_WAIT_DIRECT", "CHUNK_WAIT_DIRECT_16", "CHUNK_WAIT_COPY_16", "CHUNK_WAIT_COPY_32"):
            print("SPI_TFT_EXPERIMENTAL_PATH_H_GT_1")
        if path in ("ROWS_STATIC_GRID", "CHUNK_WAIT_COPY_COMPAT_1", "CHUNK_WAIT_COPY_COMPAT_2", "CHUNK_WAIT_COPY_COMPAT_4", "CHUNK_WAIT_COPY_COMPAT_8"):
            print("SPI_TFT_SAFE_PATH_ROWS_COMPAT")

        # Prebuild two patterns to expose row/column errors and tearing quickly.
        _fill_buffer_color565(fill_buf, sw * sh, 0x0000)
        _compose_full_grid_320x240(frame_buf)

        frame = 0
        dbg_every = int(getattr(config, "CAMERA_SPI_TEST_DBG_EVERY", 60))
        if dbg_every < 1:
            dbg_every = 60
        last_tick = ticks_ms()
        perf_window_start = last_tick
        drew_once = False

        while True:
            now = ticks_ms()
            elapsed = ticks_diff(now, last_tick)
            if elapsed < config.FRAME_MS:
                sleep_ms(config.FRAME_MS - elapsed)
                continue
            last_tick = now

            # STATIC_GRID only: avoid pattern toggling during transport-path diagnostics.
            buf = frame_buf

            try:
                if path == "ROWS_STATIC_GRID":
                    _lgfx.blit_rect565_rows(0, 0, sw, sh, buf)
                elif path == "BULK_WAIT_DIRECT":
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                elif path == "CHUNK_WAIT_DIRECT_16":
                    chunk_h = 16
                    mv = memoryview(buf)
                    row_bytes = sw * 2
                    y = 0
                    while y < sh:
                        h = chunk_h
                        if y + h > sh:
                            h = sh - y
                        off = y * row_bytes
                        end = off + (h * row_bytes)
                        _lgfx.blit_rect565_wait(0, y, sw, h, mv[off:end])
                        y += h
                elif path == "CHUNK_WAIT_COPY_16":
                    _lgfx.blit_rect565_wait_copy(0, 0, sw, sh, buf, 16)
                elif path == "CHUNK_WAIT_COPY_32":
                    _lgfx.blit_rect565_wait_copy(0, 0, sw, sh, buf, 32)
                elif path == "CHUNK_WAIT_COPY_COMPAT_1":
                    _lgfx.blit_rect565_wait_copy_compat(0, 0, sw, sh, buf, sw, 0, 0, 1)
                elif path == "CHUNK_WAIT_COPY_COMPAT_2":
                    _lgfx.blit_rect565_wait_copy_compat(0, 0, sw, sh, buf, sw, 0, 0, 2)
                elif path == "CHUNK_WAIT_COPY_COMPAT_4":
                    _lgfx.blit_rect565_wait_copy_compat(0, 0, sw, sh, buf, sw, 0, 0, 4)
                elif path == "CHUNK_WAIT_COPY_COMPAT_8":
                    _lgfx.blit_rect565_wait_copy_compat(0, 0, sw, sh, buf, sw, 0, 0, 8)
                else:
                    _lgfx.blit_rect565_rows(0, 0, sw, sh, buf)
            except Exception:
                print("SPI_TFT_FAIL_DRAW")
                raise RuntimeError("SPI_TFT_FAIL_DRAW")

            frame += 1
            if not drew_once:
                print("SPI_TFT_DRAW_OK")
                drew_once = True

            if (frame % dbg_every) == 0:
                win_ms = ticks_diff(now, perf_window_start)
                if win_ms <= 0:
                    win_ms = 1
                avg_ms = win_ms / dbg_every
                fps = 1000.0 / avg_ms
                print("SPI_TFT_PERF frame_ms=%.2f fps=%.2f" % (avg_ms, fps))
                perf_window_start = now

            if max_frames is not None and frame >= int(max_frames):
                break

        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_FULL_BUFFER_TEST:
        if not hasattr(_lgfx, "blit_rect565_rows"):
            print("FULL_BUFFER_FAIL_DRAW")
            raise RuntimeError("FULL_BUFFER_FAIL_DRAW")

        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        frame_bytes = sw * sh * 2
        row_bytes = sw * 2
        dbg_every = int(getattr(config, "FULL_BUFFER_DBG_EVERY", 60))
        if dbg_every < 1:
            dbg_every = 60

        enable_world = bool(getattr(config, "FULL_BUFFER_ENABLE_WORLD", True))
        enable_sprite = bool(getattr(config, "FULL_BUFFER_ENABLE_SPRITE", True))
        enable_hud = bool(getattr(config, "FULL_BUFFER_ENABLE_HUD", True))

        try:
            frame_buf = bytearray(frame_bytes)
            far_cache = bytearray(frame_bytes)
        except Exception:
            print("FULL_BUFFER_FAIL_ALLOC")
            raise RuntimeError("FULL_BUFFER_FAIL_ALLOC")
        print("FULL_BUFFER_ALLOC_OK")

        far_raw = str(getattr(config, "CAMERA_TEST_ROOT_BG_FAR_RGB565", "/bg_far.rgb565"))
        try:
            st = os.stat(far_raw)
        except Exception:
            print("FULL_BUFFER_FAIL_FAR_SIZE")
            raise RuntimeError("FULL_BUFFER_FAIL_FAR_SIZE")
        size = int(st[6]) if len(st) > 6 else -1
        if size != frame_bytes:
            print("FULL_BUFFER_FAIL_FAR_SIZE")
            raise RuntimeError("FULL_BUFFER_FAIL_FAR_SIZE")
        with open(far_raw, "rb") as ff:
            n = ff.readinto(far_cache)
            if n != frame_bytes:
                print("FULL_BUFFER_FAIL_FAR_SIZE")
                raise RuntimeError("FULL_BUFFER_FAIL_FAR_SIZE")
        print("FULL_BUFFER_FAR_CACHE_OK")

        try:
            from engine.input import InputSystem

            input_system = InputSystem()
        except Exception:
            input_system = None

        map_w = int(getattr(config, "CAMERA_TEST_MAP_W", 960))
        player_w = int(getattr(config, "CAMERA_TEST_PLAYER_W", 12))
        player_h = int(getattr(config, "CAMERA_TEST_PLAYER_H", 16))
        player_x = int(getattr(config, "CAMERA_TEST_PLAYER_START_X", 32))
        default_player_y = sh - player_h - 16
        player_y = int(getattr(config, "CAMERA_TEST_PLAYER_START_Y", default_player_y))
        speed = int(getattr(config, "PLAYER_SPEED_X", 2))
        max_player_x = map_w - player_w
        if max_player_x < 0:
            max_player_x = 0
        camera_max = map_w - sw
        if camera_max < 0:
            camera_max = 0
        player_x = _clamp(player_x, 0, max_player_x)
        screen_half = sw // 2
        camera_x = 0
        facing = 1
        anim_counter = 0
        anim_idx = 0

        draw_off_x = int(getattr(config, "PLAYER_DRAW_OFFSET_X", -((32 - player_w) // 2)))
        draw_off_y = int(getattr(config, "PLAYER_DRAW_OFFSET_Y", -(32 - player_h)))
        sprite_w = 32
        sprite_h = 32
        sprite_left = []
        sprite_right = []
        sprite_mask_left = []
        sprite_mask_right = []
        c_compose_ok_logged = False

        if enable_sprite:
            if not hasattr(_lgfx, "compose_masked_rgb565"):
                print("FULL_BUFFER_FAIL_NO_C_API")
                raise RuntimeError("FULL_BUFFER_FAIL_NO_C_API")
            side = "left"
            while side in ("left", "right"):
                i = 0
                while i < 4:
                    rgb_path = "/player_walk_%s_%d.rgb565" % (side, i)
                    mask_path = "/player_walk_%s_%d.mask1" % (side, i)
                    try:
                        with open(rgb_path, "rb") as rf:
                            rb = rf.read()
                        with open(mask_path, "rb") as mf:
                            mb = mf.read()
                    except Exception:
                        print("FULL_BUFFER_FAIL_DRAW")
                        raise RuntimeError("FULL_BUFFER_FAIL_DRAW")
                    if len(rb) != 2048 or len(mb) != 128:
                        print("FULL_BUFFER_FAIL_DRAW")
                        raise RuntimeError("FULL_BUFFER_FAIL_DRAW")
                    if side == "left":
                        sprite_left.append(rb)
                        sprite_mask_left.append(mb)
                    else:
                        sprite_right.append(rb)
                        sprite_mask_right.append(mb)
                    i += 1
                side = "right" if side == "left" else "done"

        hud_fps_text = "0"
        hud_coord_text = "0,0"
        if enable_hud and (_draw_digits_to_buf is None or _get_digits_text_width is None):
            print("FULL_BUFFER_FAIL_DRAW")
            raise RuntimeError("FULL_BUFFER_FAIL_DRAW")

        frame = 0
        drew_once = False
        last_tick = ticks_ms()
        perf_window_start = last_tick
        while True:
            now = ticks_ms()
            elapsed = ticks_diff(now, last_tick)
            if elapsed < config.FRAME_MS:
                sleep_ms(config.FRAME_MS - elapsed)
                continue
            last_tick = now

            input_lr = 0
            if input_system is not None:
                input_system.update(now)
                input_lr = int(getattr(input_system, "joy_x_axis", 0))
            if input_lr > 20:
                player_x += speed
                facing = 1
            elif input_lr < -20:
                player_x -= speed
                facing = -1
            player_x = _clamp(player_x, 0, max_player_x)
            player_center_x = player_x + (player_w // 2)
            target_camera_x = player_center_x - screen_half
            camera_x = _clamp(target_camera_x, 0, camera_max)
            player_screen_x = player_x - camera_x

            if enable_sprite:
                moving = 1 if (input_lr > 20 or input_lr < -20) else 0
                if moving:
                    anim_counter += 1
                    anim_idx = (anim_counter // 4) & 0x03
                else:
                    anim_counter = 0
                    anim_idx = 0

            frame_buf[:] = far_cache

            if enable_world:
                ground_h = 16
                ground_y0 = sh - ground_h
                phase_off = camera_x & 31
                gy = 0
                while gy < ground_h:
                    row_y = ground_y0 + gy
                    row_off = row_y * row_bytes
                    gx = 0
                    gi = row_off
                    while gx < sw:
                        phase = ((phase_off + gx) // 16) & 1
                        color = config.COLOR_TILE_SOLID if phase == 0 else 0x31A6
                        frame_buf[gi] = color & 0xFF
                        frame_buf[gi + 1] = (color >> 8) & 0xFF
                        gi += 2
                        gx += 1
                    gy += 1

            if enable_sprite:
                sprite_x = player_screen_x + draw_off_x
                sprite_y = player_y + draw_off_y
                if facing < 0:
                    spr_rgb = sprite_left[anim_idx]
                    spr_mask = sprite_mask_left[anim_idx]
                else:
                    spr_rgb = sprite_right[anim_idx]
                    spr_mask = sprite_mask_right[anim_idx]
                try:
                    _lgfx.compose_masked_rgb565(
                        frame_buf,
                        sw,
                        sh,
                        sprite_x,
                        sprite_y,
                        spr_rgb,
                        spr_mask,
                        sprite_w,
                        sprite_h,
                    )
                except Exception:
                    print("FULL_BUFFER_FAIL_DRAW")
                    raise RuntimeError("FULL_BUFFER_FAIL_DRAW")
                if not c_compose_ok_logged:
                    print("FULL_BUFFER_PLAYER_C_API_OK")
                    c_compose_ok_logged = True

            if enable_hud:
                if (frame % 15) == 0:
                    hud_coord_text = "%d,%d" % (player_x, player_y)
                _draw_digits_to_buf(frame_buf, sw, sh, 4, 4, hud_fps_text, 0xFFFF)
                coord_w = _get_digits_text_width(hud_coord_text)
                coord_x = sw - coord_w - 4
                if coord_x < 0:
                    coord_x = 0
                _draw_digits_to_buf(frame_buf, sw, sh, coord_x, 4, hud_coord_text, 0xFFFF)

            try:
                _lgfx.blit_rect565_rows(0, 0, sw, sh, frame_buf)
            except Exception:
                print("FULL_BUFFER_FAIL_DRAW")
                raise RuntimeError("FULL_BUFFER_FAIL_DRAW")

            frame += 1
            if not drew_once:
                if enable_hud:
                    print("FULL_BUFFER_HUD_OK")
                print("FULL_BUFFER_DRAW_OK")
                drew_once = True

            if (frame % dbg_every) == 0:
                win_ms = ticks_diff(now, perf_window_start)
                if win_ms <= 0:
                    win_ms = 1
                avg_ms = win_ms / dbg_every
                fps = 1000.0 / avg_ms
                if fps < 20.0:
                    print("FULL_BUFFER_FAIL_PERF")
                fps_i = int(fps + 0.5)
                if fps_i < 0:
                    fps_i = 0
                hud_fps_text = str(fps_i)
                print("FULL_BUFFER_PERF frame_ms=%.2f fps=%.2f" % (avg_ms, fps))
                perf_window_start = now

            if max_frames is not None and frame >= int(max_frames):
                break

        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_ROWS_SAFE_PROGRESSIVE:
        step = int(getattr(config, "CAMERA_TEST_STEP", 1))
        if step < 1 or step > 5:
            print("CAMERA_TEST_STEP=%d_FAIL_RANGE" % step)
            raise RuntimeError("CAMERA_TEST_STEP_FAIL_RANGE")

        # Step dispatcher is fixed to 1..5.
        if step == 1:
            print("CAMERA_TEST_STEP=1_START")
        elif step == 2:
            print("CAMERA_TEST_STEP=2_START")
        elif step == 3:
            print("CAMERA_TEST_STEP=3_START")
        elif step == 4:
            print("CAMERA_TEST_STEP=4_START")
        else:
            print("CAMERA_TEST_STEP=%d_FAIL_NOT_IMPLEMENTED" % step)
            raise RuntimeError("CAMERA_TEST_STEP_NOT_IMPLEMENTED")

        if not hasattr(_lgfx, "blit_rect565_rows"):
            if step == 1:
                print("CAMERA_TEST_STEP=1_FAIL_NO_BLIT_ROWS")
                raise RuntimeError("CAMERA_TEST_STEP1_FAIL_NO_BLIT_ROWS")
            if step == 2:
                print("CAMERA_TEST_STEP=2_FAIL_NO_BLIT_ROWS")
                raise RuntimeError("CAMERA_TEST_STEP2_FAIL_NO_BLIT_ROWS")
            if step == 3:
                print("CAMERA_TEST_STEP=3_FAIL_NO_BLIT_ROWS")
                raise RuntimeError("CAMERA_TEST_STEP3_FAIL_NO_BLIT_ROWS")
            print("CAMERA_TEST_STEP=4_FAIL_NO_BLIT_ROWS")
            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_NO_BLIT_ROWS")

        far_raw = str(getattr(config, "CAMERA_TEST_ROOT_BG_FAR_RGB565", "/bg_far.rgb565"))
        try:
            st = os.stat(far_raw)
        except Exception:
            if step == 1:
                print("CAMERA_TEST_STEP=1_FAIL_MISSING_RGB565")
                raise RuntimeError("CAMERA_TEST_STEP1_FAIL_MISSING_RGB565")
            if step == 2:
                print("CAMERA_TEST_STEP=2_FAIL_MISSING_RGB565")
                raise RuntimeError("CAMERA_TEST_STEP2_FAIL_MISSING_RGB565")
            if step == 3:
                print("CAMERA_TEST_STEP=3_FAIL_MISSING_RGB565")
                raise RuntimeError("CAMERA_TEST_STEP3_FAIL_MISSING_RGB565")
            print("CAMERA_TEST_STEP=4_FAIL_MISSING_RGB565")
            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_MISSING_RGB565")

        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        expected = sw * sh * 2
        actual = int(st[6]) if len(st) > 6 else -1
        if actual != expected:
            if step == 1:
                print("CAMERA_TEST_STEP=1_FAIL_RGB565_SIZE")
                raise RuntimeError("CAMERA_TEST_STEP1_FAIL_RGB565_SIZE")
            if step == 2:
                print("CAMERA_TEST_STEP=2_FAIL_RGB565_SIZE")
                raise RuntimeError("CAMERA_TEST_STEP2_FAIL_RGB565_SIZE")
            if step == 3:
                print("CAMERA_TEST_STEP=3_FAIL_RGB565_SIZE")
                raise RuntimeError("CAMERA_TEST_STEP3_FAIL_RGB565_SIZE")
            print("CAMERA_TEST_STEP=4_FAIL_RGB565_SIZE")
            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_RGB565_SIZE")

        _lgfx.fill(0x0000)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh

        row_bytes = sw * 2
        try:
            buf = bytearray(row_bytes * chunk_h)
        except Exception:
            if step == 1:
                print("CAMERA_TEST_STEP=1_FAIL_ALLOC")
                raise RuntimeError("CAMERA_TEST_STEP1_FAIL_ALLOC")
            if step == 2:
                print("CAMERA_TEST_STEP=2_FAIL_ALLOC")
                raise RuntimeError("CAMERA_TEST_STEP2_FAIL_ALLOC")
            if step == 3:
                print("CAMERA_TEST_STEP=3_FAIL_ALLOC")
                raise RuntimeError("CAMERA_TEST_STEP3_FAIL_ALLOC")
            print("CAMERA_TEST_STEP=4_FAIL_ALLOC")
            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_ALLOC")

        # Shared world overlays.
        ground_y = sh - 16
        player_w = int(getattr(config, "CAMERA_TEST_PLAYER_W", 12))
        player_h = int(getattr(config, "CAMERA_TEST_PLAYER_H", 16))
        player_x = int(getattr(config, "CAMERA_TEST_PLAYER_START_X", 32))
        default_player_y = sh - player_h - 16
        player_y = int(getattr(config, "CAMERA_TEST_PLAYER_START_Y", default_player_y))
        # STEP=3/4: single-layer far runtime loop (rows-safe), camera_x affects player/world only.
        if step == 3 or step == 4:
            step_tag = int(step)
            perf_prefix = "CAMERA_STEP3"
            if step_tag == 4:
                perf_prefix = "CAMERA_STEP4"
            try:
                from engine.input import InputSystem

                input_system = InputSystem()
            except Exception:
                print("CAMERA_TEST_STEP=%d_FAIL_NO_INPUT" % step_tag)
                raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_NO_INPUT" % step_tag)

            map_w = int(getattr(config, "CAMERA_TEST_MAP_W", 960))
            screen_half = sw // 2
            max_player_x = map_w - player_w
            if max_player_x < 0:
                max_player_x = 0
            camera_max = map_w - sw
            if camera_max < 0:
                camera_max = 0
            player_x = int(getattr(config, "CAMERA_TEST_PLAYER_START_X", 32))
            player_x = _clamp(player_x, 0, max_player_x)
            speed = int(getattr(config, "PLAYER_SPEED_X", 2))
            dbg_key = "CAMERA_TEST_STEP3_DBG_EVERY"
            if step_tag == 4:
                dbg_key = "CAMERA_TEST_STEP4_DBG_EVERY"
            dbg_every = int(getattr(config, dbg_key, 60))
            if dbg_every < 1:
                dbg_every = 60

            use_sprite_player = step_tag == 4 and bool(getattr(config, "CAMERA_PLAYER_SPRITE_ENABLED", True))
            sprite_draw_mode = str(getattr(config, "CAMERA_PLAYER_SPRITE_DRAW_MODE", "COMPOSE")).upper()
            if sprite_draw_mode not in ("COMPOSE", "DIRECT_SMALL_RECT"):
                sprite_draw_mode = "COMPOSE"
            sprite_compose_impl = str(getattr(config, "CAMERA_PLAYER_SPRITE_COMPOSE_IMPL", "PYTHON")).upper()
            if sprite_compose_impl not in ("PYTHON", "C_API"):
                sprite_compose_impl = "PYTHON"
            sprite_left = None
            sprite_right = None
            sprite_mask_left = None
            sprite_mask_right = None
            sprite_seg_left = None
            sprite_seg_right = None
            coord_hud_enabled = (
                step_tag == 4
                and bool(getattr(config, "CAMERA_TOP_HUD_ENABLED", True))
                and _draw_digits_to_buf is not None
                and _get_digits_text_width is not None
            )
            coord_hud_color = 0xFFFF
            coord_hud_text = "0,0"
            coord_hud_logged = False
            coord_update_every = int(getattr(config, "CAMERA_TEST_COORD_UPDATE_EVERY", 15))
            if coord_update_every < 1:
                coord_update_every = 15
            top_hud_w = int(getattr(config, "CAMERA_TEST_TOP_HUD_W", 112))
            top_hud_h = int(getattr(config, "CAMERA_TEST_TOP_HUD_H", 16))
            if top_hud_w < 64:
                top_hud_w = 64
            if top_hud_w > sw:
                top_hud_w = sw
            if top_hud_h < 14:
                top_hud_h = 14
            if top_hud_h > 24:
                top_hud_h = 24
            top_hud_bg = 0x0000
            top_hud_buf = None
            top_hud_fps_text = "0"
            top_hud_coord_x = 0
            top_hud_last_key = None
            sprite_buf = None
            sprite_tmp_buf = None
            facing = 1  # 1=right, -1=left
            anim_counter = 0
            anim_idx = 0
            boundary_clamp_last = 0
            c_compose_ok_logged = False
            if use_sprite_player:
                draw_off_x = int(getattr(config, "PLAYER_DRAW_OFFSET_X", -((32 - player_w) // 2)))
                draw_off_y = int(getattr(config, "PLAYER_DRAW_OFFSET_Y", -(32 - player_h)))
                sprite_w = int(getattr(config, "CAMERA_TEST_PLAYER_SPRITE_W", 32))
                sprite_h = int(getattr(config, "CAMERA_TEST_PLAYER_SPRITE_H", 32))
                sprite_left = []
                sprite_right = []
                sprite_mask_left = []
                sprite_mask_right = []
                sprite_seg_left = []
                sprite_seg_right = []
            if coord_hud_enabled:
                print("TOP_HUD_SMALL_RECT_EXCEPTION")
                print("CAMERA_COORD_HUD_READY")
                print("CAMERA_TOP_HUD_READY")

            # Draw far once (fixed x=0) via streamed chunks (no full-frame allocation).
            with open(far_raw, "rb") as ff:
                y = 0
                while y < sh:
                    h = chunk_h
                    if y + h > sh:
                        h = sh - y
                    need = row_bytes * h
                    view = memoryview(buf)[:need]
                    n = ff.readinto(view)
                    if n != need:
                        print("CAMERA_TEST_STEP=%d_FAIL_READ" % step_tag)
                        raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_READ" % step_tag)
                    _lgfx.blit_rect565_rows(0, y, sw, h, view)
                    y += h

            ground_h = 16
            ground_y0 = sh - ground_h
            sprite_logic_y = player_y
            if use_sprite_player and sprite_draw_mode == "COMPOSE":
                sprite_logic_y = player_y + draw_off_y
            band_top = player_y if player_y < sprite_logic_y else sprite_logic_y
            if band_top < 0:
                band_top = 0
            if band_top > ground_y0:
                band_top = ground_y0
            # Allocate runtime compose buffer as early as possible to maximize contiguous heap.
            # COMPOSE may need a taller band for full 32x32 sprite; if allocation fails,
            # shrink band from top until allocation succeeds (still COMPOSE path).
            scene_buf = None
            while True:
                far_band_h = ground_y0 - band_top
                scene_h = sh - band_top
                if far_band_h <= 0 or scene_h <= 0:
                    print("CAMERA_TEST_STEP=%d_FAIL_PLAYER_BAND" % step_tag)
                    raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_PLAYER_BAND" % step_tag)
                if gc is not None:
                    gc.collect()
                try:
                    scene_buf = bytearray(sw * scene_h * 2)
                    break
                except MemoryError:
                    if not (use_sprite_player and sprite_draw_mode == "COMPOSE"):
                        raise
                    if band_top >= player_y:
                        raise
                    band_top += 2
            if use_sprite_player and sprite_draw_mode == "COMPOSE":
                print("CAMERA_COMPOSE_BAND_TOP=%d" % band_top)

            far_band_buf = None
            far_runtime_file = None
            # STEP=3 keeps far rows cached in RAM.
            # STEP=4 sprite mode keeps memory lower by streaming far upper-band rows each frame.
            if use_sprite_player:
                far_runtime_file = open(far_raw, "rb")
            else:
                far_band_buf = bytearray(sw * far_band_h * 2)
                with open(far_raw, "rb") as far_bg:
                    row = 0
                    while row < far_band_h:
                        src_off = ((band_top + row) * sw) * 2
                        far_bg.seek(src_off)
                        row_off = row * sw * 2
                        row_view = memoryview(far_band_buf)[row_off : row_off + (sw * 2)]
                        n = far_bg.readinto(row_view)
                        if n != (sw * 2):
                            print("CAMERA_TEST_STEP=%d_FAIL_READ" % step_tag)
                            raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_READ" % step_tag)
                        row += 1

            # Keep memory low in STEP=4 with sprites: build one phase row per frame.
            row_bytes = sw * 2
            ground_row_buf = bytearray(row_bytes)

            # Release setup scratch buffer.
            buf = None
            if coord_hud_enabled:
                try:
                    top_hud_buf = bytearray(top_hud_w * top_hud_h * 2)
                except Exception:
                    print("CAMERA_TEST_STEP=4_FAIL_ALLOC")
                    raise RuntimeError("CAMERA_TEST_STEP4_FAIL_ALLOC")
            if use_sprite_player and sprite_draw_mode == "DIRECT_SMALL_RECT":
                try:
                    sprite_buf = bytearray(32 * 32 * 2)
                    sprite_tmp_buf = bytearray(32 * 32 * 2)
                    print("CAMERA_PLAYER_SPRITE_DRAW_MODE=DIRECT_SMALL_RECT")
                    print("CAMERA_PLAYER_SPRITE_SMALL_RECT_EXCEPTION")
                except Exception:
                    print("CAMERA_TEST_STEP=4_FAIL_ALLOC")
                    raise RuntimeError("CAMERA_TEST_STEP4_FAIL_ALLOC")
            elif use_sprite_player:
                print("CAMERA_PLAYER_SPRITE_DRAW_MODE=COMPOSE")
                print("CAMERA_PLAYER_SPRITE_COMPOSE_IMPL=%s" % sprite_compose_impl)
            if use_sprite_player:
                side = "left"
                while side in ("left", "right"):
                    i = 0
                    while i < 4:
                        rgb_path = "/player_walk_%s_%d.rgb565" % (side, i)
                        mask_path = "/player_walk_%s_%d.mask1" % (side, i)
                        try:
                            with open(rgb_path, "rb") as rf:
                                rb = rf.read()
                            with open(mask_path, "rb") as mf:
                                mb = mf.read()
                        except Exception:
                            print("CAMERA_TEST_STEP=4_FAIL_PLAYER_ASSET")
                            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_PLAYER_ASSET")
                        if len(rb) != 2048:
                            print("CAMERA_TEST_STEP=4_FAIL_PLAYER_RGB565_SIZE")
                            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_PLAYER_RGB565_SIZE")
                        if len(mb) != 128:
                            print("CAMERA_TEST_STEP=4_FAIL_PLAYER_MASK1_SIZE")
                            raise RuntimeError("CAMERA_TEST_STEP4_FAIL_PLAYER_MASK1_SIZE")
                        if side == "left":
                            sprite_left.append(rb)
                            if sprite_draw_mode == "COMPOSE":
                                sprite_mask_left.append(mb)
                            else:
                                sprite_seg_left.append(_build_sprite_segments_32(mb))
                        else:
                            sprite_right.append(rb)
                            if sprite_draw_mode == "COMPOSE":
                                sprite_mask_right.append(mb)
                            else:
                                sprite_seg_right.append(_build_sprite_segments_32(mb))
                        i += 1
                    side = "right" if side == "left" else "done"
                print("CAMERA_PLAYER_SPRITE_READY=1")
            player_screen_x = player_x
            camera_x = 0
            frame = 0
            drew_once = False
            prev_sprite_x = None
            prev_sprite_y = None
            last_tick = ticks_ms()
            perf_window_start = last_tick
            far_len = 0 if far_band_buf is None else len(far_band_buf)
            profile_every = int(getattr(config, "CAMERA_TEST_STEP4_PROFILE_EVERY", 60))
            if profile_every < 1:
                profile_every = 60
            prof_update_us = 0
            prof_bg_us = 0
            prof_world_us = 0
            prof_sprite_us = 0
            prof_hud_us = 0
            prof_submit_us = 0
            prof_total_us = 0
            prof_pace_us = 0
            dirty_rect_experiment = (
                step_tag == 4 and bool(getattr(config, "CAMERA_DIRTY_RECT_EXPERIMENT", False))
            )
            dirty_fallback_on_camera_move = bool(
                getattr(config, "CAMERA_DIRTY_FALLBACK_ON_CAMERA_MOVE", True)
            )
            dirty_band_full_width = bool(getattr(config, "CAMERA_DIRTY_BAND_FULL_WIDTH", True))
            dirty_prev_sprite_x = None
            dirty_prev_sprite_y = None
            prev_camera_x = camera_x
            dirty_us_acc = 0
            fallback_us_acc = 0
            submit_acc = 0
            dirty_last_rects_count = 0
            dirty_last_bands_count = 0
            dirty_last_camera_static = 1
            floor_layer_enabled = bool(getattr(config, "FLOOR_LAYER_ENABLED", False))
            floor_rgb_fp = None
            floor_mask_fp = None
            floor_rgb_data = None
            floor_mask_data = None
            floor_w = int(getattr(config, "FLOOR_LAYER_W", 0))
            floor_h = int(getattr(config, "FLOOR_LAYER_H", 0))
            floor_screen_y = int(getattr(config, "FLOOR_LAYER_SCREEN_Y", sh - floor_h))
            floor_scroll_factor = float(getattr(config, "FLOOR_SCROLL_FACTOR", 1.0))
            floor_scroll_x_offset = int(getattr(config, "FLOOR_SCROLL_X_OFFSET", 0))
            floor_runs_by_row = None
            floor_use_c_compose = False
            if floor_layer_enabled and floor_w > 0 and floor_h > 0:
                try:
                    floor_rgb_path = _resolve_asset_path(getattr(config, "FLOOR_LAYER_RGB565_PATH", ""))
                    floor_mask_path = _resolve_asset_path(getattr(config, "FLOOR_LAYER_MASK_PATH", ""))
                    floor_rgb_fp = open(floor_rgb_path, "rb")
                    floor_mask_fp = open(floor_mask_path, "rb")
                    floor_runs_by_row = _build_floor_runs_by_row(floor_mask_fp, floor_w, floor_h)
                    try:
                        floor_mask_fp.seek(0)
                        floor_mask_data = floor_mask_fp.read()
                    except Exception:
                        floor_mask_data = None
                    # Try RAM-caching floor RGB to avoid per-frame file seek/read when camera scrolls.
                    try:
                        if gc is not None:
                            gc.collect()
                        floor_rgb_data = floor_rgb_fp.read()
                        if floor_rgb_data is None or len(floor_rgb_data) != (floor_w * floor_h * 2):
                            floor_rgb_data = None
                            print("FLOOR_LAYER_RGB_CACHE_SKIP")
                        else:
                            print("FLOOR_LAYER_RGB_CACHE_READY")
                            try:
                                floor_rgb_fp.close()
                            except Exception:
                                pass
                            floor_rgb_fp = None
                    except Exception:
                        floor_rgb_data = None
                        print("FLOOR_LAYER_RGB_CACHE_FAIL")
                    if (
                        floor_rgb_data is not None
                        and floor_mask_data is not None
                        and bool(getattr(config, "FLOOR_USE_C_COMPOSE", False))
                        and hasattr(_lgfx, "compose_masked_rgb565")
                    ):
                        floor_use_c_compose = True
                        print("FLOOR_LAYER_COMPOSE_C_READY")
                    print("FLOOR_LAYER_READY")
                except Exception:
                    floor_rgb_fp = None
                    floor_mask_fp = None
                    floor_rgb_data = None
                    floor_mask_data = None
                    floor_runs_by_row = None
                    floor_use_c_compose = False
                    print("FLOOR_LAYER_DISABLED_OPEN_FAIL")
            if floor_runs_by_row is not None and (floor_rgb_data is not None or floor_rgb_fp is not None):
                # Ensure the full map layer is visible (not only lower compose band).
                band_top = 0
                far_band_h = sh - band_top
                scene_h = sh - band_top
                if gc is not None:
                    gc.collect()
                try:
                    scene_buf = bytearray(sw * scene_h * 2)
                except Exception:
                    print("FLOOR_LAYER_FULL_SCENE_ALLOC_FAIL")
                    raise RuntimeError("FLOOR_LAYER_FULL_SCENE_ALLOC_FAIL")
                # Prefer RAM-cached far band to avoid per-frame file streaming.
                try:
                    far_band_buf = bytearray(sw * far_band_h * 2)
                    with open(far_raw, "rb") as far_bg:
                        row = 0
                        while row < far_band_h:
                            src_off = ((band_top + row) * sw) * 2
                            far_bg.seek(src_off)
                            row_off = row * sw * 2
                            row_view = memoryview(far_band_buf)[row_off : row_off + (sw * 2)]
                            n = far_bg.readinto(row_view)
                            if n != (sw * 2):
                                print("CAMERA_TEST_STEP=%d_FAIL_READ" % step_tag)
                                raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_READ" % step_tag)
                            row += 1
                    far_len = len(far_band_buf)
                    if far_runtime_file is not None:
                        try:
                            far_runtime_file.close()
                        except Exception:
                            pass
                        far_runtime_file = None
                except Exception:
                    # Fallback to runtime streaming only when allocation truly fails.
                    far_band_buf = None
                    far_len = 0
                    if use_sprite_player:
                        if far_runtime_file is not None:
                            try:
                                far_runtime_file.close()
                            except Exception:
                                pass
                        far_runtime_file = open(far_raw, "rb")
            floor_bg_cache = None
            floor_bg_cached_camera_x = -2147483648
            floor_bg_cache_ready = False
            partial_submit_tmp = None
            if floor_use_c_compose:
                floor_bg_cache = None
            elif floor_runs_by_row is not None and (floor_rgb_fp is not None or floor_rgb_data is not None):
                try:
                    floor_bg_cache = bytearray(sw * scene_h * 2)
                except Exception:
                    floor_bg_cache = None
            dirty_log_countdown = 0
            if dirty_rect_experiment:
                print("DIRTY_RECT_EXPERIMENT_ON")

            while True:
                now = ticks_ms()
                elapsed = ticks_diff(now, last_tick)
                if elapsed < config.FRAME_MS:
                    sleep_left = config.FRAME_MS - elapsed
                    if sleep_left > 0:
                        prof_pace_us += sleep_left * 1000
                    sleep_ms(sleep_left)
                    continue
                last_tick = now
                frame_start_us = ticks_us()

                seg_t0 = ticks_us()
                input_system.update(now)
                input_lr = int(getattr(input_system, "joy_x_axis", 0))
                if input_lr > 20:
                    player_x += speed
                    facing = 1
                elif input_lr < -20:
                    player_x -= speed
                    facing = -1
                player_x = _clamp(player_x, 0, max_player_x)
                player_center_x = player_x + (player_w // 2)
                target_camera_x = player_center_x - screen_half
                camera_x = _clamp(target_camera_x, 0, camera_max)
                player_screen_x = player_x - camera_x
                if use_sprite_player and sprite_draw_mode == "COMPOSE":
                    min_screen_x = 0
                    if draw_off_x < 0:
                        min_screen_x = -draw_off_x
                    max_screen_x = sw - sprite_w - draw_off_x
                    if max_screen_x < min_screen_x:
                        max_screen_x = min_screen_x
                    clamped_screen_x = _clamp(player_screen_x, min_screen_x, max_screen_x)
                    clamp_applied = 1 if clamped_screen_x != player_screen_x else 0
                    if clamp_applied:
                        player_screen_x = clamped_screen_x
                        player_x = player_screen_x + camera_x
                        player_x = _clamp(player_x, 0, max_player_x)
                        player_screen_x = player_x - camera_x
                    boundary_clamp_last = clamp_applied
                moving = 1 if (input_lr > 20 or input_lr < -20) else 0
                if use_sprite_player:
                    if moving:
                        anim_counter += 1
                        anim_idx = (anim_counter // 4) & 0x03
                    else:
                        anim_counter = 0
                        anim_idx = 0
                prof_update_us += ticks_diff(ticks_us(), seg_t0)

                # Compose dynamic band: far upper area + camera-phased ground + player.
                seg_t0 = ticks_us()
                camera_dx = camera_x - floor_bg_cached_camera_x
                camera_move_strip = None
                if floor_use_c_compose:
                    if far_band_buf is not None:
                        scene_buf[:far_len] = far_band_buf
                    else:
                        row = 0
                        while row < far_band_h:
                            src_off = ((band_top + row) * sw) * 2
                            far_runtime_file.seek(src_off)
                            dst_off = row * row_bytes
                            row_view = memoryview(scene_buf)[dst_off : dst_off + row_bytes]
                            n = far_runtime_file.readinto(row_view)
                            if n != row_bytes:
                                print("CAMERA_TEST_STEP=%d_FAIL_READ" % step_tag)
                                raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_READ" % step_tag)
                            row += 1
                    floor_src_x = int(camera_x * floor_scroll_factor) + int(floor_scroll_x_offset)
                    prev_floor_x = floor_bg_cached_camera_x
                    try:
                        _lgfx.compose_masked_rgb565(
                            scene_buf,
                            sw,
                            scene_h,
                            -floor_src_x,
                            floor_screen_y - band_top,
                            floor_rgb_data,
                            floor_mask_data,
                            floor_w,
                            floor_h,
                        )
                        prev_floor_x = floor_bg_cached_camera_x
                        floor_bg_cached_camera_x = camera_x
                    except Exception:
                        floor_use_c_compose = False
                        print("FLOOR_LAYER_COMPOSE_C_FAIL")
                    dx_submit = camera_x - prev_floor_x
                    if drew_once and dx_submit != 0 and abs(dx_submit) < sw:
                        strip_w = dx_submit if dx_submit > 0 else -dx_submit
                        if dx_submit > 0:
                            camera_move_strip = (sw - strip_w, strip_w, 0, scene_h)
                        else:
                            camera_move_strip = (0, strip_w, 0, scene_h)
                elif floor_bg_cache is not None and floor_bg_cache_ready:
                    dx = camera_dx
                    if dx == 0:
                        scene_buf[:] = floor_bg_cache
                    elif abs(dx) < sw and far_band_buf is not None:
                        shift_px = dx if dx > 0 else -dx
                        shift_bytes = shift_px * 2
                        row_bytes_local = sw * 2
                        row_idx = 0
                        if dx > 0:
                            while row_idx < scene_h:
                                b0 = row_idx * row_bytes_local
                                floor_bg_cache[b0 : b0 + (row_bytes_local - shift_bytes)] = floor_bg_cache[
                                    b0 + shift_bytes : b0 + row_bytes_local
                                ]
                                row_idx += 1
                            _compose_floor_layer_strip_rows(
                                floor_bg_cache,
                                sw,
                                scene_h,
                                band_top,
                                sw - shift_px,
                                shift_px,
                                camera_x,
                                floor_rgb_fp,
                                floor_w,
                                floor_h,
                                floor_screen_y,
                                floor_scroll_factor,
                                floor_scroll_x_offset,
                                floor_runs_by_row,
                                far_band_buf,
                                floor_rgb_data,
                            )
                            camera_move_strip = (sw - shift_px, shift_px, 0, scene_h)
                        else:
                            while row_idx < scene_h:
                                b0 = row_idx * row_bytes_local
                                floor_bg_cache[b0 + shift_bytes : b0 + row_bytes_local] = floor_bg_cache[
                                    b0 : b0 + (row_bytes_local - shift_bytes)
                                ]
                                row_idx += 1
                            _compose_floor_layer_strip_rows(
                                floor_bg_cache,
                                sw,
                                scene_h,
                                band_top,
                                0,
                                shift_px,
                                camera_x,
                                floor_rgb_fp,
                                floor_w,
                                floor_h,
                                floor_screen_y,
                                floor_scroll_factor,
                                floor_scroll_x_offset,
                                floor_runs_by_row,
                                far_band_buf,
                                floor_rgb_data,
                            )
                            camera_move_strip = (0, shift_px, 0, scene_h)
                        floor_bg_cached_camera_x = camera_x
                        scene_buf[:] = floor_bg_cache
                    else:
                        # Rebuild cache in full when camera changes.
                        # This is slower in theory than strip-delta, but more stable on MicroPython.
                        scene_buf[:far_len] = far_band_buf
                        _compose_floor_layer_rows(
                            scene_buf,
                            sw,
                            scene_h,
                            band_top,
                            camera_x,
                            floor_rgb_fp,
                            floor_mask_fp,
                            floor_w,
                            floor_h,
                            floor_screen_y,
                            floor_scroll_factor,
                            floor_scroll_x_offset,
                            floor_runs_by_row,
                            floor_rgb_data,
                        )
                        floor_bg_cache[:] = scene_buf
                        floor_bg_cached_camera_x = camera_x
                        scene_buf[:] = floor_bg_cache
                else:
                    if far_band_buf is not None:
                        scene_buf[:far_len] = far_band_buf
                    else:
                        row = 0
                        while row < far_band_h:
                            src_off = ((band_top + row) * sw) * 2
                            far_runtime_file.seek(src_off)
                            dst_off = row * row_bytes
                            row_view = memoryview(scene_buf)[dst_off : dst_off + row_bytes]
                            n = far_runtime_file.readinto(row_view)
                            if n != row_bytes:
                                print("CAMERA_TEST_STEP=%d_FAIL_READ" % step_tag)
                                raise RuntimeError("CAMERA_TEST_STEP%d_FAIL_READ" % step_tag)
                            row += 1

                    if (floor_rgb_data is not None or floor_rgb_fp is not None) and floor_runs_by_row is not None:
                        _compose_floor_layer_rows(
                            scene_buf,
                            sw,
                            scene_h,
                            band_top,
                            camera_x,
                            floor_rgb_fp,
                            floor_mask_fp,
                            floor_w,
                            floor_h,
                            floor_screen_y,
                            floor_scroll_factor,
                            floor_scroll_x_offset,
                            floor_runs_by_row,
                            floor_rgb_data,
                        )
                    if floor_bg_cache is not None:
                        floor_bg_cache[:] = scene_buf
                        floor_bg_cached_camera_x = camera_x
                        floor_bg_cache_ready = True
                prof_bg_us += ticks_diff(ticks_us(), seg_t0)

                seg_t0 = ticks_us()
                if floor_runs_by_row is None or (floor_rgb_fp is None and floor_rgb_data is None):
                    phase_off = camera_x & 31
                    gx = 0
                    gi = 0
                    while gx < sw:
                        phase = ((phase_off + gx) // 16) & 1
                        color = config.COLOR_TILE_SOLID if phase == 0 else 0x31A6
                        ground_row_buf[gi] = color & 0xFF
                        ground_row_buf[gi + 1] = (color >> 8) & 0xFF
                        gi += 2
                        gx += 1
                    gy = 0
                    while gy < ground_h:
                        off = (far_band_h + gy) * row_bytes
                        scene_buf[off : off + row_bytes] = ground_row_buf
                        gy += 1
                prof_world_us += ticks_diff(ticks_us(), seg_t0)

                seg_t0 = ticks_us()
                spr_x = 0
                spr_y = 0
                if use_sprite_player:
                    sprite_x = player_screen_x + draw_off_x
                    sprite_y = player_y + draw_off_y
                    spr_x = sprite_x
                    spr_y = sprite_y - band_top
                    if facing < 0:
                        spr_rgb = sprite_left[anim_idx]
                        if sprite_draw_mode == "COMPOSE":
                            spr_mask = sprite_mask_left[anim_idx]
                        else:
                            spr_seg = sprite_seg_left[anim_idx]
                    else:
                        spr_rgb = sprite_right[anim_idx]
                        if sprite_draw_mode == "COMPOSE":
                            spr_mask = sprite_mask_right[anim_idx]
                        else:
                            spr_seg = sprite_seg_right[anim_idx]
                    if sprite_draw_mode == "COMPOSE":
                        if sprite_compose_impl == "C_API":
                            if not hasattr(_lgfx, "compose_masked_rgb565"):
                                print("CAMERA_PLAYER_SPRITE_FAIL_NO_C_API")
                                raise RuntimeError("CAMERA_PLAYER_SPRITE_FAIL_NO_C_API")
                            try:
                                _lgfx.compose_masked_rgb565(
                                    scene_buf,
                                    sw,
                                    scene_h,
                                    spr_x,
                                    spr_y,
                                    spr_rgb,
                                    spr_mask,
                                    sprite_w,
                                    sprite_h,
                                )
                                if not c_compose_ok_logged:
                                    print("CAMERA_PLAYER_SPRITE_C_COMPOSE_OK")
                                    c_compose_ok_logged = True
                            except Exception:
                                print("CAMERA_PLAYER_SPRITE_FAIL_C_COMPOSE")
                                raise RuntimeError("CAMERA_PLAYER_SPRITE_FAIL_C_COMPOSE")
                        else:
                            _blend_sprite32_mask1_into_scene(
                                scene_buf,
                                sw,
                                scene_h,
                                spr_x,
                                spr_y,
                                spr_rgb,
                                spr_mask,
                            )
                else:
                    px0 = player_screen_x
                    py0 = player_y - band_top
                    px1 = px0 + player_w
                    py1 = py0 + player_h
                    sx0 = 0 if px0 < 0 else px0
                    sy0 = 0 if py0 < 0 else py0
                    sx1 = sw if px1 > sw else px1
                    sy1 = scene_h if py1 > scene_h else py1
                    if sx1 > sx0 and sy1 > sy0:
                        _fill_buffer_rect565(
                            scene_buf,
                            sw,
                            sx0,
                            sy0,
                            sx1 - sx0,
                            sy1 - sy0,
                            config.COLOR_PLAYER,
                        )
                prof_sprite_us += ticks_diff(ticks_us(), seg_t0)

                camera_static = 1 if camera_x == prev_camera_x else 0
                dirty_last_camera_static = camera_static
                use_dirty_path = (
                    dirty_rect_experiment
                    and use_sprite_player
                    and sprite_draw_mode == "COMPOSE"
                    and (camera_static == 1 or not dirty_fallback_on_camera_move)
                    and drew_once
                )

                if use_dirty_path:
                    dirty_t0 = ticks_us()
                    rects = []
                    if dirty_prev_sprite_x is not None and dirty_prev_sprite_y is not None:
                        c = _clip_rect_screen_xywh(dirty_prev_sprite_x, dirty_prev_sprite_y, sprite_w, sprite_h, sw, sh)
                        if c is not None:
                            rects.append((c[0], c[1], c[2], c[3], "player_old_rect"))
                    c = _clip_rect_screen_xywh(sprite_x, sprite_y, sprite_w, sprite_h, sw, sh)
                    if c is not None:
                        rects.append((c[0], c[1], c[2], c[3], "player_new_rect"))
                    dirty_last_rects_count = len(rects)
                    bands = _merge_rects_to_vertical_bands(rects)
                    dirty_last_bands_count = len(bands)
                    bi = 0
                    while bi < len(bands):
                        by0, by1 = bands[bi]
                        ry0 = by0 - band_top
                        ry1 = by1 - band_top
                        if ry0 < 0:
                            ry0 = 0
                        if ry1 > scene_h:
                            ry1 = scene_h
                        if ry1 > ry0:
                            submit_t0 = ticks_us()
                            off = ry0 * row_bytes
                            h = ry1 - ry0
                            view = memoryview(scene_buf)[off : off + (h * row_bytes)]
                            _lgfx.blit_rect565_rows(0, band_top + ry0, sw, h, view)
                            us = ticks_diff(ticks_us(), submit_t0)
                            submit_acc += us
                            prof_submit_us += us
                        bi += 1
                    dirty_us_acc += ticks_diff(ticks_us(), dirty_t0)
                    if dirty_log_countdown <= 0:
                        print("DIRTY_DRAW_OK")
                        dirty_log_countdown = 30
                elif camera_move_strip is not None:
                    # Camera scrolling still needs full-scene present; submit full rows-safe scene.
                    submit_t0 = ticks_us()
                    seg_h = int(getattr(config, "CAMERA_TEST_STRIP_H", 30))
                    if seg_h < 1:
                        seg_h = 1
                    if seg_h > scene_h:
                        seg_h = scene_h
                    sy = 0
                    while sy < scene_h:
                        h = seg_h
                        if sy + h > scene_h:
                            h = scene_h - sy
                        off = sy * row_bytes
                        view = memoryview(scene_buf)[off : off + (h * row_bytes)]
                        _lgfx.blit_rect565_rows(0, band_top + sy, sw, h, view)
                        sy += h
                    us = ticks_diff(ticks_us(), submit_t0)
                    submit_acc += us
                    prof_submit_us += us
                    fallback_us_acc += us
                    dirty_last_rects_count = 2
                    dirty_last_bands_count = 1
                    dirty_last_camera_static = 0
                    if dirty_log_countdown <= 0:
                        print("DIRTY_SCROLL_FULL_OK")
                        dirty_log_countdown = 30
                else:
                    if dirty_rect_experiment and camera_static == 0 and dirty_log_countdown <= 0:
                        print("DIRTY_FALLBACK_CAMERA_MOVE")
                        dirty_log_countdown = 30
                    fallback_t0 = ticks_us()
                    submit_t0 = ticks_us()
                    # Keep rows-safe segmented submit to avoid diagonal tearing on full-frame updates.
                    seg_h = int(getattr(config, "CAMERA_TEST_STRIP_H", 30))
                    if seg_h < 1:
                        seg_h = 1
                    if seg_h > scene_h:
                        seg_h = scene_h
                    sy = 0
                    while sy < scene_h:
                        h = seg_h
                        if sy + h > scene_h:
                            h = scene_h - sy
                        off = sy * row_bytes
                        view = memoryview(scene_buf)[off : off + (h * row_bytes)]
                        _lgfx.blit_rect565_rows(0, band_top + sy, sw, h, view)
                        sy += h
                    us = ticks_diff(ticks_us(), submit_t0)
                    submit_acc += us
                    prof_submit_us += us
                    fallback_us_acc += ticks_diff(ticks_us(), fallback_t0)
                if dirty_log_countdown > 0:
                    dirty_log_countdown -= 1

                prev_camera_x = camera_x
                if use_sprite_player:
                    dirty_prev_sprite_x = sprite_x
                    dirty_prev_sprite_y = sprite_y

                if use_sprite_player and sprite_draw_mode == "DIRECT_SMALL_RECT":
                    print("CAMERA_TEST_STEP=4_FAIL_DIRECT_SMALL_RECT_DISABLED")
                    raise RuntimeError("CAMERA_TEST_STEP4_FAIL_DIRECT_SMALL_RECT_DISABLED")

                if coord_hud_enabled and ((frame == 0) or ((frame % coord_update_every) == 0)):
                    seg_t0 = ticks_us()
                    # Use latest perf snapshot when available; initial frame uses 0.
                    coord_hud_text = "%d,%d" % (player_x, player_y)
                    coord_w = _get_digits_text_width(coord_hud_text)
                    top_hud_coord_x = sw - coord_w - 4
                    if top_hud_coord_x < 0:
                        top_hud_coord_x = 0
                    hud_key = top_hud_fps_text + "|" + coord_hud_text
                    if hud_key == top_hud_last_key:
                        pass
                    else:
                        top_hud_last_key = hud_key
                        # Left segment: FPS at fixed top-left.
                        _fill_buffer_color565(top_hud_buf, top_hud_w * top_hud_h, top_hud_bg)
                        _draw_digits_to_buf(top_hud_buf, top_hud_w, top_hud_h, 4, 4, top_hud_fps_text, coord_hud_color)
                        _lgfx.blit_rect565_rows(0, 0, top_hud_w, top_hud_h, top_hud_buf)
                        # Right segment: coord right-aligned at screen edge using same small buffer.
                        right_x = sw - top_hud_w
                        if right_x < 0:
                            right_x = 0
                        coord_local_x = top_hud_w - coord_w - 4
                        if coord_local_x < 0:
                            coord_local_x = 0
                        _fill_buffer_color565(top_hud_buf, top_hud_w * top_hud_h, top_hud_bg)
                        _draw_digits_to_buf(
                            top_hud_buf,
                            top_hud_w,
                            top_hud_h,
                            coord_local_x,
                            4,
                            coord_hud_text,
                            coord_hud_color,
                        )
                        _lgfx.blit_rect565_rows(right_x, 0, top_hud_w, top_hud_h, top_hud_buf)
                    prof_hud_us += ticks_diff(ticks_us(), seg_t0)

                prof_total_us += ticks_diff(ticks_us(), frame_start_us)

                frame += 1
                if not drew_once:
                    if use_sprite_player:
                        clip_top = 0
                        clip_bottom = 0
                        src_start_x = 0
                        dst_start_x = 0
                        visible_w = 32
                        if sprite_x < 0:
                            dst_start_x = 0
                            src_start_x = -sprite_x
                            visible_w = 32 - src_start_x
                        else:
                            dst_start_x = sprite_x
                            rem = sw - sprite_x
                            visible_w = 32 if 32 < rem else rem
                        if visible_w < 0:
                            visible_w = 0
                        if spr_y < 0:
                            clip_top = -spr_y
                        if (spr_y + 32) > scene_h:
                            clip_bottom = (spr_y + 32) - scene_h
                        print(
                            "PLAYER_SPRITE_POS player_screen_x=%d sprite_x=%d sprite_y=%d offset_x=%d offset_y=%d"
                            % (player_screen_x, sprite_x, sprite_y, draw_off_x, draw_off_y)
                        )
                        print(
                            "PLAYER_SPRITE_CLIP top=%d bottom=%d"
                            % (clip_top, clip_bottom)
                        )
                        print(
                            "PLAYER_SPRITE_CLIP_LEFT=%d src_start_x=%d dst_start_x=%d visible_w=%d"
                            % (1 if sprite_x < 0 else 0, src_start_x, dst_start_x, visible_w)
                        )
                    print("CAMERA_TEST_STEP=%d_DRAW_OK" % step_tag)
                    print("CAMERA_TEST_STEP=%d_HOLD" % step_tag)
                    if coord_hud_enabled and not coord_hud_logged:
                        print("CAMERA_TOP_HUD_DRAW_OK")
                        print("CAMERA_TOP_HUD_POS fps_x=4 fps_y=4 coord_x=%d coord_y=4" % top_hud_coord_x)
                        print("CAMERA_TOP_HUD_VALUE fps=%s coord=%s" % (top_hud_fps_text, coord_hud_text))
                        coord_hud_logged = True
                    drew_once = True

                if (frame % dbg_every) == 0:
                    win_ms = ticks_diff(now, perf_window_start)
                    if win_ms <= 0:
                        win_ms = 1
                    avg_ms = win_ms / dbg_every
                    fps = 1000.0 / avg_ms
                    fps_i = int(fps + 0.5)
                    if fps_i < 0:
                        fps_i = 0
                    top_hud_fps_text = str(fps_i)
                    if coord_hud_enabled:
                        print("CAMERA_TOP_HUD_VALUE fps=%s coord=%s" % (top_hud_fps_text, coord_hud_text))
                    if use_sprite_player:
                        print(
                            "CAMERA_PLAYER_ANIM frame=%d facing=%s idx=%d moving=%d"
                            % (frame, "L" if facing < 0 else "R", anim_idx, moving)
                        )
                        print(
                            "CAMERA_PLAYER_SPRITE_PERF frame_ms=%.2f fps=%.2f"
                            % (avg_ms, fps)
                        )
                    print(
                        "%s_DBG frame=%d player_x=%d camera_x=%d input_lr=%d"
                        % (perf_prefix, frame, player_x, camera_x, input_lr)
                    )
                    if use_sprite_player and sprite_draw_mode == "COMPOSE":
                        min_screen_x = 0
                        if draw_off_x < 0:
                            min_screen_x = -draw_off_x
                        print(
                            "PLAYER_BOUNDARY_DBG player_x=%d camera_x=%d player_screen_x=%d sprite_x=%d min_screen_x=%d"
                            % (player_x, camera_x, player_screen_x, player_screen_x + draw_off_x, min_screen_x)
                        )
                        print("PLAYER_BOUNDARY_CLAMP_APPLIED=%d" % boundary_clamp_last)
                    if dirty_rect_experiment:
                        print("DIRTY_CAMERA_STATIC=%d" % dirty_last_camera_static)
                        print("DIRTY_RECTS_COUNT=%d" % dirty_last_rects_count)
                        print("DIRTY_BANDS_COUNT=%d" % dirty_last_bands_count)
                    print("%s_PERF frame_ms=%.2f fps=%.2f" % (perf_prefix, avg_ms, fps))
                    perf_window_start = now

                if (frame % profile_every) == 0:
                    n = profile_every
                    avg_update_us = prof_update_us // n
                    avg_bg_us = prof_bg_us // n
                    avg_world_us = prof_world_us // n
                    avg_sprite_us = prof_sprite_us // n
                    avg_hud_us = prof_hud_us // n
                    avg_submit_us = prof_submit_us // n
                    avg_total_us = prof_total_us // n
                    avg_pace_us = prof_pace_us // n
                    avg_other_us = avg_total_us - (
                        avg_update_us + avg_bg_us + avg_world_us + avg_sprite_us + avg_hud_us + avg_submit_us
                    )
                    if avg_other_us < 0:
                        avg_other_us = 0
                    fps_prof = 0.0
                    if avg_total_us > 0:
                        fps_prof = 1000000.0 / avg_total_us
                    print("PROFILE update_us=%d" % avg_update_us)
                    print("PROFILE bg_us=%d" % avg_bg_us)
                    print("PROFILE world_us=%d" % avg_world_us)
                    print("PROFILE sprite_us=%d" % avg_sprite_us)
                    print("PROFILE hud_us=%d" % avg_hud_us)
                    print("PROFILE submit_us=%d" % avg_submit_us)
                    print("PROFILE pacing_us=%d" % avg_pace_us)
                    print("PROFILE other_us=%d" % avg_other_us)
                    print("PROFILE total_us=%d" % avg_total_us)
                    print("PROFILE fps=%.2f" % fps_prof)
                    if dirty_rect_experiment:
                        n_dirty = profile_every
                        avg_dirty_us = dirty_us_acc // n_dirty
                        avg_fallback_us = fallback_us_acc // n_dirty
                        avg_submit_path_us = submit_acc // n_dirty
                        print("DIRTY_CAMERA_STATIC=%d" % dirty_last_camera_static)
                        print("DIRTY_RECTS_COUNT=%d" % dirty_last_rects_count)
                        print("DIRTY_BANDS_COUNT=%d" % dirty_last_bands_count)
                        print(
                            "DIRTY_PROFILE dirty_us=%d fallback_us=%d submit_us=%d total_us=%d fps=%.2f"
                            % (avg_dirty_us, avg_fallback_us, avg_submit_path_us, avg_total_us, fps_prof)
                        )
                        dirty_us_acc = 0
                        fallback_us_acc = 0
                        submit_acc = 0
                    prof_update_us = 0
                    prof_bg_us = 0
                    prof_world_us = 0
                    prof_sprite_us = 0
                    prof_hud_us = 0
                    prof_submit_us = 0
                    prof_total_us = 0
                    prof_pace_us = 0

                if max_frames is not None and frame >= int(max_frames):
                    break

            if far_runtime_file is not None:
                try:
                    far_runtime_file.close()
                except Exception:
                    pass
            if floor_rgb_fp is not None:
                try:
                    floor_rgb_fp.close()
                except Exception:
                    pass
            if floor_mask_fp is not None:
                try:
                    floor_mask_fp.close()
                except Exception:
                    pass

            print("CAMERA_TEST_END")
            print("APP_RUN_END_PHASE_CAMERA_TEST")
            return

        # STEP=1/2 keep one-shot draw and hold behavior.
        camera_x = 0
        with open(far_raw, "rb") as f:
            y = 0
            while y < sh:
                h = chunk_h
                if y + h > sh:
                    h = sh - y
                need = row_bytes * h
                view = memoryview(buf)[:need]
                n = f.readinto(view)
                if n != need:
                    if step == 1:
                        print("CAMERA_TEST_STEP=1_FAIL_READ")
                        raise RuntimeError("CAMERA_TEST_STEP1_FAIL_READ")
                    print("CAMERA_TEST_STEP=2_FAIL_READ")
                    raise RuntimeError("CAMERA_TEST_STEP2_FAIL_READ")

                if step == 2:
                    gy0 = y if y > ground_y else ground_y
                    gy1 = (y + h) if (y + h) < sh else sh
                    if gy1 > gy0:
                        _fill_buffer_rect565(
                            view,
                            sw,
                            0,
                            gy0 - y,
                            sw,
                            gy1 - gy0,
                            config.COLOR_TILE_SOLID,
                        )

                    px0 = player_x - camera_x
                    py0 = player_y
                    px1 = px0 + player_w
                    py1 = py0 + player_h
                    sx0 = 0 if px0 < 0 else px0
                    sy0 = y if py0 < y else py0
                    sx1 = sw if px1 > sw else px1
                    sy1 = (y + h) if py1 > (y + h) else py1
                    if sx1 > sx0 and sy1 > sy0:
                        _fill_buffer_rect565(
                            view,
                            sw,
                            sx0,
                            sy0 - y,
                            sx1 - sx0,
                            sy1 - sy0,
                            config.COLOR_PLAYER,
                        )
                _lgfx.blit_rect565_rows(0, y, sw, h, view)
                y += h

        if step == 1:
            print("CAMERA_TEST_STEP=1_DRAW_OK")
            print("CAMERA_TEST_STEP=1_HOLD")
        else:
            print("CAMERA_TEST_STEP=2_DRAW_OK")
            print("CAMERA_TEST_STEP=2_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_BLIT_SINGLE_BLOCK_TEST:
        _lgfx.fill(0x0000)
        buf = bytearray(32 * 32 * 2)
        _compose_block_32x32_quads(buf)
        _lgfx.blit_rect565(32, 32, 32, 32, buf)
        print("BLIT_SINGLE_BLOCK_OK")
        print("BLIT_SINGLE_BLOCK_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_BLIT_FULL_BUFFER_TEST:
        _lgfx.fill(0x0000)
        try:
            buf = bytearray(320 * 240 * 2)
        except Exception:
            print("BLIT_FULL_BUFFER_FAIL_MEM")
            raise RuntimeError("BLIT_FULL_BUFFER_FAIL_MEM")
        _compose_full_grid_320x240(buf)
        _lgfx.blit_rect565(0, 0, 320, 240, buf)
        print("BLIT_FULL_BUFFER_OK")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_BLIT_ROWS_GRID_TEST:
        _lgfx.fill(0x0000)
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        row_bytes = sw * 2
        try:
            buf = bytearray(row_bytes * chunk_h)
        except Exception:
            print("BLIT_ROWS_GRID_FAIL_MEM")
            raise RuntimeError("BLIT_ROWS_GRID_FAIL_MEM")
        y = 0
        while y < sh:
            h = chunk_h
            if y + h > sh:
                h = sh - y
            view = memoryview(buf)[: row_bytes * h]
            _compose_grid_chunk565(view, sw, sh, y, h)
            _lgfx.blit_rect565_rows(0, y, sw, h, view)
            y += h
        print("BLIT_ROWS_GRID_OK")
        print("BLIT_ROWS_GRID_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_BOARD_GENERATED_GRID_TEST:
        _lgfx.fill(0x0000)
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        row_bytes = sw * 2
        buf = bytearray(row_bytes * chunk_h)
        y = 0
        while y < sh:
            h = chunk_h
            if y + h > sh:
                h = sh - y
            view = memoryview(buf)[: row_bytes * h]
            _compose_grid_chunk565(view, sw, sh, y, h)
            _lgfx.blit_rect565(0, y, sw, h, view)
            y += h
        print("CAMERA_TEST_BOARD_GRID_DRAW_OK")
        print("CAMERA_TEST_BOARD_GRID_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_ROOT_RGB565_GRID_PATTERN:
        _lgfx.fill(0x0000)
        test_raw = str(getattr(config, "CAMERA_TEST_ROOT_TEST_GRID_RGB565", "/test_grid.rgb565"))
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        row_bytes = sw * 2
        buf = bytearray(row_bytes * chunk_h)
        with open(test_raw, "rb") as f:
            y = 0
            while y < sh:
                h = chunk_h
                if y + h > sh:
                    h = sh - y
                need = row_bytes * h
                view = memoryview(buf)[:need]
                n = f.readinto(view)
                if n != need:
                    raise RuntimeError("CAMERA_TEST_FAIL_RGB565_READ:%d!=%d" % (n if n is not None else -1, need))
                _lgfx.blit_rect565(0, y, sw, h, view)
                y += h
        print("CAMERA_TEST_ROOT_GRID_DRAW_OK")
        print("CAMERA_TEST_ROOT_GRID_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_BOARD_GENERATED_RGB565_TEST:
        _lgfx.fill(0x0000)
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = 40
        row_bytes = sw * 2
        buf = bytearray(row_bytes * chunk_h)
        colors = (0xF800, 0x07E0, 0x001F, 0xFFFF, 0x8410, 0x0000)
        idx = 0
        y = 0
        while y < sh:
            h = chunk_h
            if y + h > sh:
                h = sh - y
            color = colors[idx] if idx < len(colors) else 0x0000
            view = memoryview(buf)[: row_bytes * h]
            _fill_buffer_color565(view, sw * h, color)
            _lgfx.blit_rect565(0, y, sw, h, view)
            y += h
            idx += 1
        print("CAMERA_TEST_BOARD_GENERATED_DRAW_OK")
        print("CAMERA_TEST_BOARD_GENERATED_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_ROOT_RGB565_TEST_PATTERN:
        _lgfx.fill(0x0000)
        test_raw = str(getattr(config, "CAMERA_TEST_ROOT_TEST_BARS_RGB565", "/test_bars.rgb565"))
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        row_bytes = sw * 2
        buf = bytearray(row_bytes * chunk_h)
        with open(test_raw, "rb") as f:
            y = 0
            while y < sh:
                h = chunk_h
                if y + h > sh:
                    h = sh - y
                need = row_bytes * h
                view = memoryview(buf)[:need]
                n = f.readinto(view)
                if n != need:
                    raise RuntimeError("CAMERA_TEST_FAIL_RGB565_READ:%d!=%d" % (n if n is not None else -1, need))
                _lgfx.blit_rect565(0, y, sw, h, view)
                y += h
        print("CAMERA_TEST_ROOT_PATTERN_DRAW_OK")
        print("CAMERA_TEST_ROOT_PATTERN_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_ROOT_FAR_RGB565_ONLY:
        if not hasattr(_lgfx, "blit_rect565_rows"):
            raise RuntimeError("CAMERA_TEST_FAIL_NO_BLIT_ROWS")
        _lgfx.fill(0x0000)
        far_raw = str(getattr(config, "CAMERA_TEST_ROOT_BG_FAR_RGB565", "/bg_far.rgb565"))
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        row_bytes = sw * 2
        buf = bytearray(row_bytes * chunk_h)
        print("CAMERA_TEST_ROOT_FAR_SIZE_OK")
        with open(far_raw, "rb") as f:
            y = 0
            while y < sh:
                h = chunk_h
                if y + h > sh:
                    h = sh - y
                need = row_bytes * h
                view = memoryview(buf)[:need]
                n = f.readinto(view)
                if n != need:
                    raise RuntimeError("CAMERA_TEST_FAIL_RGB565_READ:%d!=%d" % (n if n is not None else -1, need))
                _lgfx.blit_rect565_rows(0, y, sw, h, view)
                y += h
        print("CAMERA_TEST_ROOT_FAR_DRAW_OK")
        print("CAMERA_TEST_ROOT_FAR_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_DIRECT_BG_ONLY:
        _lgfx.fill(0x0000)
        _lgfx.draw_png_mem(getattr(config, "CAMERA_TEST_BG_FAR"), 0, 0)
        print("CAMERA_TEST_DIRECT_BG_OK")
        print("CAMERA_TEST_DIRECT_BG_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    if mode == _MODE_DIRECT_RGB565_BG_ONLY:
        _lgfx.fill(0x0000)
        far_raw = getattr(config, "CAMERA_TEST_BG_FAR_RGB565")
        sw = int(config.SCREEN_W)
        sh = int(config.SCREEN_H)
        chunk_h = int(getattr(config, "CAMERA_TEST_RGB565_CHUNK_H", 40))
        if chunk_h < 1:
            chunk_h = 1
        if chunk_h > sh:
            chunk_h = sh
        print("CAMERA_TEST_DIRECT_RGB565_BG_CHUNK_H=%d" % chunk_h)
        row_bytes = sw * 2
        buf = bytearray(row_bytes * chunk_h)
        with open(far_raw, "rb") as f:
            y = 0
            while y < sh:
                h = chunk_h
                if y + h > sh:
                    h = sh - y
                need = row_bytes * h
                view = memoryview(buf)[:need]
                n = f.readinto(view)
                if n != need:
                    raise RuntimeError("CAMERA_TEST_FAIL_RGB565_READ:%d!=%d" % (n if n is not None else -1, need))
                _lgfx.blit_rect565(0, y, sw, h, view)
                y += h
        print("CAMERA_TEST_DIRECT_RGB565_BG_OK")
        print("CAMERA_TEST_DIRECT_RGB565_BG_HOLD")
        if max_frames is None:
            while True:
                sleep_ms(1000)
        else:
            hold_frames = int(max_frames)
            if hold_frames < 1:
                hold_frames = 1
            i = 0
            while i < hold_frames:
                sleep_ms(config.FRAME_MS)
                i += 1
        print("CAMERA_TEST_END")
        print("APP_RUN_END_PHASE_CAMERA_TEST")
        return

    runtime = _CameraTestRuntime()
    print("CAMERA_TEST_STRIP_H=%d" % runtime.strip_h)
    runtime.draw()

    if mode in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT):
        frame_limit = 0
    elif max_frames is None:
        frame_limit = int(getattr(config, "CAMERA_TEST_MANUAL_FRAMES", 900))
    else:
        frame_limit = int(max_frames)

    if mode not in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT) and frame_limit < 1:
        frame_limit = 1

    frames = 0
    last_tick = ticks_ms()
    while frames < frame_limit:
        now = ticks_ms()
        elapsed = ticks_diff(now, last_tick)
        if elapsed < config.FRAME_MS:
            sleep_ms(config.FRAME_MS - elapsed)
            continue
        last_tick = now
        runtime.update(now)
        runtime.draw()
        frames += 1

    print("CAMERA_TEST_SUBMIT_COUNT=%d" % runtime.submit_count)
    print("CAMERA_TEST_BLITS_LAST_FRAME=%d" % runtime.blits_last_frame)
    print("CAMERA_TEST_MAX_BLITS_IN_FRAME=%d" % runtime.max_blits_in_frame)
    if mode in (_MODE_SINGLE_IMAGE_STRIP, _MODE_SINGLE_IMAGE_DIRECT):
        print("CAMERA_TEST_SINGLE_IMAGE_END")
    if mode == _MODE_FAR_ONLY:
        print("CAMERA_TEST_FAR_ONLY_END")
    print("CAMERA_TEST_END")
    print("APP_RUN_END_PHASE_CAMERA_TEST")
