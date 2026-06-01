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
    import ujson as json
except Exception:
    try:
        import json
    except Exception:
        json = None

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
_MODE_BLIT_WAIT_GRID_TEST = "BLIT_WAIT_GRID_TEST"
_MODE_ROWS_SAFE_PROGRESSIVE = "ROWS_SAFE_PROGRESSIVE"
_MODE_ROWS_SAFE_NEAR_TILE_TEST = "ROWS_SAFE_NEAR_TILE_TEST"
_MODE_FULL_BUFFER_TEST = "FULL_BUFFER_TEST"
_MODE_SPI_TFT_SPEED_TEST = "SPI_TFT_SPEED_TEST"
_MODE_SPI_TFT_BULK_WAIT_TEST = "SPI_TFT_BULK_WAIT_TEST"

_ENEMY_STATE_IDLE = 0
_ENEMY_STATE_WALK = 1
_ENEMY_STATE_SHOOT = 2
_BULLET_DEBUG_LIMIT = 12
_bullet_debug_count = 0
_bullet_debug_last_active_ms = -1000000
_enemy_native_update_disabled = False
_ENEMY_STATE_KEYS = ("facing", "state", "anim_counter", "shoot_cooldown", "shot_fired", "vel_y")
_ENEMY_ROW_STRIDE = 12
_ENEMY_STATE_STRIDE = 8
_BULLET_STATE_STRIDE = 16
_OBJECT_SOLID_STRIDE = 8


def _buf_get_i16_le(buf, off):
    val = buf[off] | (buf[off + 1] << 8)
    if val & 0x8000:
        val -= 0x10000
    return val


def _buf_set_i16_le(buf, off, value):
    iv = int(value)
    if iv < -32768:
        iv = -32768
    if iv > 32767:
        iv = 32767
    uv = iv & 0xFFFF
    buf[off] = uv & 0xFF
    buf[off + 1] = (uv >> 8) & 0xFF


class _PackedEnemyStateView:
    def __init__(self, owner, index):
        self._owner = owner
        self._index = index

    def _base(self):
        return self._index * _ENEMY_STATE_STRIDE

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
        base = self._base()
        buf = self._owner._buf
        if key == "facing":
            return 1 if buf[base] else -1
        if key == "state":
            return buf[base + 1]
        if key == "anim_counter":
            return _buf_get_i16_le(buf, base + 2)
        if key == "shoot_cooldown":
            return _buf_get_i16_le(buf, base + 4)
        if key == "shot_fired":
            return buf[base + 6]
        if key == "vel_y":
            raw = buf[base + 7]
            return raw - 256 if raw >= 128 else raw
        raise KeyError(key)

    def __setitem__(self, key, value):
        base = self._base()
        buf = self._owner._buf
        if key == "facing":
            buf[base] = 1 if int(value) >= 0 else 0
            return
        if key == "state":
            buf[base + 1] = int(value) & 0xFF
            return
        if key == "anim_counter":
            _buf_set_i16_le(buf, base + 2, value)
            return
        if key == "shoot_cooldown":
            _buf_set_i16_le(buf, base + 4, value)
            return
        if key == "shot_fired":
            buf[base + 6] = int(value) & 0xFF
            return
        if key == "vel_y":
            buf[base + 7] = int(value) & 0xFF
            return
        raise KeyError(key)


class _PackedEnemyStates:
    def __init__(self, count):
        self._count = int(count)
        self._buf = bytearray(self._count * _ENEMY_STATE_STRIDE)

    def __len__(self):
        return self._count

    def __bool__(self):
        return self._count > 0

    def __getitem__(self, index):
        ii = int(index)
        if ii < 0 or ii >= self._count:
            raise IndexError(index)
        return _PackedEnemyStateView(self, ii)


class _PackedBulletView:
    def __init__(self, owner, index):
        self._owner = owner
        self._index = index

    def __len__(self):
        return 8

    def _base(self):
        return self._index * _BULLET_STATE_STRIDE

    def _get_one(self, item):
        base = self._base()
        return _buf_get_i16_le(self._owner._buf, base + (item * 2))

    def _set_one(self, item, value):
        base = self._base()
        _buf_set_i16_le(self._owner._buf, base + (item * 2), value)

    def __getitem__(self, item):
        if isinstance(item, slice):
            start, stop, step = item.indices(8)
            out = []
            i = start
            while i < stop:
                out.append(self._get_one(i))
                i += step
            return out
        ii = int(item)
        if ii < 0 or ii >= 8:
            raise IndexError(item)
        return self._get_one(ii)

    def __setitem__(self, item, value):
        ii = int(item)
        if ii < 0 or ii >= 8:
            raise IndexError(item)
        self._set_one(ii, value)


class _PackedEnemyBullets:
    def __init__(self):
        self._count = 0
        self._buf = bytearray()

    def __len__(self):
        return self._count

    def __bool__(self):
        return self._count > 0

    def __getitem__(self, index):
        ii = int(index)
        if ii < 0 or ii >= self._count:
            raise IndexError(index)
        return _PackedBulletView(self, ii)

    def ensure_capacity(self, count):
        target = int(count)
        if target <= self._count:
            return
        need = (target - self._count) * _BULLET_STATE_STRIDE
        self._buf.extend(bytearray(need))
        self._count = target

    def append_row(self, values):
        base = self._count * _BULLET_STATE_STRIDE
        self._buf.extend(bytearray(_BULLET_STATE_STRIDE))
        i = 0
        while i < 8:
            _buf_set_i16_le(self._buf, base + (i * 2), values[i] if i < len(values) else 0)
            i += 1
        self._count += 1

    def clear(self):
        self._buf = bytearray()
        self._count = 0


def _bullet_debug(tag, text):
    global _bullet_debug_count
    if _bullet_debug_count >= _BULLET_DEBUG_LIMIT:
        return
    print("%s %s" % (tag, text))
    _bullet_debug_count += 1


def _bullet_debug_active(enemy_bullets, camera_x, screen_w, screen_h):
    global _bullet_debug_last_active_ms
    if not enemy_bullets:
        return
    now = ticks_ms()
    if ticks_diff(now, _bullet_debug_last_active_ms) < 500:
        return
    bi = 0
    while bi < len(enemy_bullets):
        bullet = enemy_bullets[bi]
        if bullet[6]:
            bx = int(bullet[0])
            by = int(bullet[1])
            vx = int(bullet[2])
            bw = int(bullet[4])
            bh = int(bullet[5])
            _bullet_debug_last_active_ms = now
            print(
                "BULLET_ACTIVE idx=%d wx=%d wy=%d sx=%d sy=%d vx=%d wh=%d,%d cam=%d screen=%d,%d"
                % (
                    bi,
                    bx,
                    by,
                    bx - int(camera_x),
                    by,
                    vx,
                    bw,
                    bh,
                    int(camera_x),
                    int(screen_w),
                    int(screen_h),
                )
            )
            return
        bi += 1


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

    _lgfx.blit_rect565_wait(rx, band_top + ry, rw, rh, memoryview(tmp_buf)[:need])
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

def _blit_sprite_colorkey_into_scene(scene_buf, scene_w, scene_h, dst_x, dst_y, sprite_rgb565, key_b0, key_b1, sprite_w=32, sprite_h=32):
    if dst_x >= scene_w or dst_y >= scene_h or (dst_x + sprite_w) <= 0 or (dst_y + sprite_h) <= 0:
        return
    src_x0 = 0
    src_y0 = 0
    dst_x0 = dst_x
    dst_y0 = dst_y
    copy_w = sprite_w
    copy_h = sprite_h
    if dst_x0 < 0:
        src_x0 = -dst_x0
        copy_w -= src_x0
        dst_x0 = 0
    if dst_y0 < 0:
        src_y0 = -dst_y0
        copy_h -= src_y0
        dst_y0 = 0
    if dst_x0 + copy_w > scene_w:
        copy_w = scene_w - dst_x0
    if dst_y0 + copy_h > scene_h:
        copy_h = scene_h - dst_y0
    if copy_w <= 0 or copy_h <= 0:
        return

    src_row_bytes = sprite_w * 2
    dst_row_bytes = scene_w * 2
    r = 0
    while r < copy_h:
        src_off = ((src_y0 + r) * src_row_bytes) + (src_x0 * 2)
        dst_off = ((dst_y0 + r) * dst_row_bytes) + (dst_x0 * 2)
        x = 0
        while x < copy_w:
            s0 = sprite_rgb565[src_off]
            s1 = sprite_rgb565[src_off + 1]
            if not (s0 == key_b0 and s1 == key_b1):
                scene_buf[dst_off] = s0
                scene_buf[dst_off + 1] = s1
            src_off += 2
            dst_off += 2
            x += 1
        r += 1


def _slice_player_spritesheet_frames(sheet_rgb565, sheet_w=128, frame_w=32, frame_h=32):
    expected = sheet_w * (frame_h * 2) * 2
    if len(sheet_rgb565) != expected:
        raise ValueError('spritesheet size mismatch')
    row_bytes = sheet_w * 2
    frame_bytes = frame_w * frame_h * 2
    right = []
    left = []
    for row_idx, out_list in ((0, right), (1, left)):
        base_y = row_idx * frame_h
        for f in range(4):
            base_x = f * frame_w
            fb = bytearray(frame_bytes)
            woff = 0
            for y in range(frame_h):
                src = ((base_y + y) * row_bytes) + (base_x * 2)
                fb[woff:woff + frame_w * 2] = sheet_rgb565[src:src + frame_w * 2]
                woff += frame_w * 2
            out_list.append(bytes(fb))
    return right, left


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


_TILEMAP_CSV = """0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,6,4,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,6,1,1,1,4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,4,0,0,0,0,0,0,0,0,0,6,1,4,0,0,0,0,0,0,0,0,0,0,0,9,3,3,3,5,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,5,0,0,0,0,0,0,0,0,0,7,2,8,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
2,2,2,2,2,2,2,2,2,2,2,3,5,0,0,0,0,0,0,0,0,0,0,0,0,9,3,5,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
3,3,3,3,3,3,3,3,3,3,5,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1
"""

def _parse_tilemap_csv(csv_text):
    rows = []
    for ln in csv_text.strip().splitlines():
        line = ln.strip()
        if not line:
            continue
        rows.append([int(x.strip()) for x in line.split(',') if x.strip() != ''])
    return rows

def _load_tilemap_rows(path):
    try:
        with open(path, 'r') as fp:
            text = fp.read()
    except Exception:
        return None
    try:
        return _parse_tilemap_csv(text)
    except Exception:
        return None

def _flatten_tilemap_rows(tile_rows):
    if not tile_rows:
        return None, 0, 0
    map_h = len(tile_rows)
    map_w = len(tile_rows[0]) if map_h > 0 else 0
    if map_w <= 0:
        return None, 0, 0
    out = bytearray(map_w * map_h)
    i = 0
    r = 0
    while r < map_h:
        row = tile_rows[r]
        c = 0
        while c < map_w:
            v = row[c]
            if v < 0:
                v = 0
            if v > 255:
                v = 255
            out[i] = v
            i += 1
            c += 1
        r += 1
    return out, map_w, map_h

def _parse_objects_csv_with_meta(text):
    rows = []
    meta_rows = []
    lines = text.strip().splitlines()
    if not lines:
        return rows, meta_rows
    header = [h.strip() for h in lines[0].split(",")]
    idx = {}
    i = 0
    while i < len(header):
        idx[header[i]] = i
        i += 1
    req = (
        "world_x",
        "world_y",
        "w",
        "h",
        "solid",
        "layer",
        "src_x",
        "src_y",
        "src_w",
        "src_h",
    )
    for k in req:
        if k not in idx:
            return [], []

    def _col(cols, key, default=""):
        pos = idx.get(key, -1)
        if pos < 0 or pos >= len(cols):
            return default
        return cols[pos].strip()

    def _to_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    li = 1
    while li < len(lines):
        line = lines[li].strip()
        li += 1
        if not line:
            continue
        cols = [c.strip() for c in line.split(",")]
        try:
            wx = _to_int(_col(cols, "world_x"))
            wy = _to_int(_col(cols, "world_y"))
            w = _to_int(_col(cols, "w"))
            h = _to_int(_col(cols, "h"))
            solid = 1 if _to_int(_col(cols, "solid")) != 0 else 0
            layer = _to_int(_col(cols, "layer"))
            if "visible" in idx:
                visible = 1 if _to_int(_col(cols, "visible")) != 0 else 0
            else:
                visible = 1
            sx = _to_int(_col(cols, "src_x"))
            sy = _to_int(_col(cols, "src_y"))
            sw = _to_int(_col(cols, "src_w"))
            sh = _to_int(_col(cols, "src_h"))
        except Exception:
            continue
        swappable = 1 if _to_int(_col(cols, "swappable")) != 0 else 0
        obj_type = _col(cols, "type", "")
        checkpoint = 1 if _to_int(_col(cols, "checkpoint"), 0) != 0 else 0
        if checkpoint == 0 and obj_type in ("checkpoint", "respawn_stone"):
            checkpoint = 1
        anim_id = _col(cols, "anim_id", "")
        rows.append([wx, wy, w, h, solid, layer, visible, swappable, sx, sy, sw, sh])
        meta_rows.append(
            {
                "id": _col(cols, "id", ""),
                "type": obj_type,
                "sprite": _col(cols, "sprite", ""),
                "gravity": _to_int(_col(cols, "gravity"), 0),
                "anim_id": anim_id,
                "checkpoint": checkpoint,
                "special_render": 1 if anim_id else 0,
            }
        )
    return rows, meta_rows


def _parse_objects_csv(text):
    rows, _meta_rows = _parse_objects_csv_with_meta(text)
    return rows


def _load_objects_rows(path):
    try:
        with open(path, "r") as fp:
            text = fp.read()
    except Exception:
        return []
    try:
        return _parse_objects_csv(text)
    except Exception:
        return []


def _load_objects_rows_and_meta(path):
    try:
        with open(path, "r") as fp:
            text = fp.read()
    except Exception:
        return [], []
    try:
        return _parse_objects_csv_with_meta(text)
    except Exception:
        return [], []


def _load_rgb565_blob(path, exp_bytes):
    try:
        with open(path, "rb") as fp:
            data = fp.read()
    except Exception:
        return None
    if data is None or len(data) != exp_bytes:
        return None
    return data


def _load_object_animations(path):
    if json is None:
        return {}
    try:
        with open(path, "r") as fp:
            raw = json.load(fp)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for anim_id in raw:
        spec = raw.get(anim_id)
        if not isinstance(spec, dict):
            continue
        rgb565_path = spec.get("sheet_rgb565") or spec.get("rgb565") or spec.get("path")
        frame_w = int(spec.get("frame_w", 0) or 0)
        frame_h = int(spec.get("frame_h", 0) or 0)
        frame_count = int(spec.get("frames", 0) or 0)
        fps = int(spec.get("fps", 0) or 0)
        if (not rgb565_path) or frame_w <= 0 or frame_h <= 0 or frame_count <= 0:
            continue
        abs_path = _resolve_asset_path(rgb565_path)
        sheet_w = int(spec.get("sheet_w", frame_w * frame_count) or (frame_w * frame_count))
        sheet_h = int(spec.get("sheet_h", frame_h) or frame_h)
        if sheet_w < (frame_w * frame_count) or sheet_h < frame_h:
            continue
        row_bytes = sheet_w * 2
        frame_bytes = frame_w * frame_h * 2
        sheet = _load_rgb565_blob(abs_path, sheet_w * sheet_h * 2)
        if sheet is None:
            continue
        frames = []
        fi = 0
        while fi < frame_count:
            frame_buf = bytearray(frame_bytes)
            row = 0
            while row < frame_h:
                src_off = (row * row_bytes) + (fi * frame_w * 2)
                dst_off = row * frame_w * 2
                frame_buf[dst_off : dst_off + (frame_w * 2)] = sheet[src_off : src_off + (frame_w * 2)]
                row += 1
            frames.append(frame_buf)
            fi += 1
        out[anim_id] = {
            "frames": frames,
            "frame_w": frame_w,
            "frame_h": frame_h,
            "fps": fps,
            "frame_hold": int(spec.get("frame_hold", 4) or 4),
            "loop": bool(spec.get("loop", True)),
        }
    return out


def _csv_header_index(line):
    if not line:
        return {}
    header = [h.strip() for h in str(line).split(",")]
    out = {}
    i = 0
    while i < len(header):
        out[header[i]] = i
        i += 1
    return out


def _parse_enemies_csv(text):
    rows = []
    meta_rows = []
    if not text:
        return rows, meta_rows
    lines = text.splitlines()
    if not lines:
        return rows, meta_rows
    idx = _csv_header_index(lines[0])
    if not idx:
        return rows, meta_rows

    def _col(cols, key, default=""):
        pos = idx.get(key, -1)
        if pos < 0 or pos >= len(cols):
            return default
        return cols[pos].strip()

    def _to_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    line_i = 1
    while line_i < len(lines):
        line = lines[line_i].strip()
        line_i += 1
        if (not line) or line.startswith("#"):
            continue
        cols = [c.strip() for c in line.split(",")]
        try:
            wx = _to_int(_col(cols, "world_x"))
            wy = _to_int(_col(cols, "world_y"))
            w = _to_int(_col(cols, "w"))
            h = _to_int(_col(cols, "h"))
        except Exception:
            continue
        swappable = 1 if _to_int(_col(cols, "swappable"), 0) != 0 else 0
        facing = _to_int(_col(cols, "facing"), -1)
        if facing >= 0:
            facing = 1
        else:
            facing = -1
        rows.append([wx, wy, w, h, 1, swappable])
        meta_rows.append(
            {
                "id": _col(cols, "id", ""),
                "type": _col(cols, "type", "bow"),
                "facing": facing,
            }
        )
    return rows, meta_rows


def _load_enemies_rows_and_meta(path):
    try:
        with open(path, "r") as fp:
            text = fp.read()
    except Exception:
        return [], []
    try:
        return _parse_enemies_csv(text)
    except Exception:
        return [], []


def _clone_enemy_rows(rows):
    if not rows:
        return []
    return [list(row) for row in rows]


def _reset_enemy_state(state, meta=None):
    facing = -1
    if meta is not None:
        facing = int(meta.get("facing", -1) or -1)
    if facing >= 0:
        facing = 1
    else:
        facing = -1
    state["facing"] = facing
    state["state"] = _ENEMY_STATE_IDLE
    state["anim_counter"] = 0
    state["shoot_cooldown"] = 0
    state["shot_fired"] = 0
    state["vel_y"] = 0


def _build_enemy_states(meta_rows):
    if not meta_rows:
        return _PackedEnemyStates(0)
    out = _PackedEnemyStates(len(meta_rows))
    i = 0
    while i < len(meta_rows):
        _reset_enemy_state(out[i], meta_rows[i])
        i += 1
    return out


def _restore_enemy_rows(rows, saved_rows, enemy_states=None, enemy_meta=None):
    if not rows or not saved_rows:
        return
    limit = len(rows)
    if len(saved_rows) < limit:
        limit = len(saved_rows)
    i = 0
    while i < limit:
        saved = saved_rows[i]
        row = rows[i]
        row[0] = int(saved[0])
        row[1] = int(saved[1])
        row[2] = int(saved[2])
        row[3] = int(saved[3])
        row[4] = int(saved[4])
        row[5] = int(saved[5])
        if enemy_states is not None and i < len(enemy_states):
            meta = enemy_meta[i] if (enemy_meta is not None and i < len(enemy_meta)) else None
            _reset_enemy_state(enemy_states[i], meta)
        i += 1


def _pick_animation_frame(anim_spec, anim_counter=0):
    if not anim_spec:
        return None, 0, 0
    frames = anim_spec.get("frames") or []
    frame_count = len(frames)
    if frame_count <= 0:
        return None, 0, 0
    frame_hold = int(anim_spec.get("frame_hold", 4) or 4)
    if frame_hold < 1:
        frame_hold = 1
    if anim_counter < 0:
        anim_counter = 0
    frame_index = int(anim_counter) // frame_hold
    if bool(anim_spec.get("loop", True)):
        frame_index %= frame_count
    elif frame_index >= frame_count:
        frame_index = frame_count - 1
    return frames[frame_index], int(anim_spec.get("frame_w", 0) or 0), int(anim_spec.get("frame_h", 0) or 0)


def _target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h):
    px = player_x + (player_w // 2)
    py = player_y + (player_h // 2)
    ox = int(wx) + (int(ow) // 2)
    oy = int(wy) + (int(oh) // 2)
    dx = ox - px
    dy = oy - py
    return dx * dx + dy * dy


def _pick_swappable_enemy_index(enemy_rows, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h):
    if not enemy_rows:
        return -1
    best_i = -1
    best_d2 = -1
    ei = 0
    while ei < len(enemy_rows):
        wx, wy, ow, oh, visible, swappable = enemy_rows[ei]
        if visible and swappable:
            sx0 = int(wx) - int(camera_x)
            sy0 = int(wy) - int(band_top)
            sx1 = sx0 + int(ow)
            sy1 = sy0 + int(oh)
            in_view = (sx0 < view_w and sx1 > 0 and sy0 < view_h and sy1 > 0)
            if in_view:
                d2 = _target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h)
                if best_i < 0:
                    best_i = ei
                    best_d2 = d2
                else:
                    if pick_far:
                        if d2 > best_d2:
                            best_i = ei
                            best_d2 = d2
                    else:
                        if d2 < best_d2:
                            best_i = ei
                            best_d2 = d2
        ei += 1
    return best_i


def _pick_swappable_bullet_index(enemy_bullets, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h):
    if not enemy_bullets:
        return -1
    best_i = -1
    best_d2 = -1
    bi = 0
    while bi < len(enemy_bullets):
        bx, by, _vx, _vy, bw, bh, active = enemy_bullets[bi][0:7]
        if active:
            sx0 = int(bx) - int(camera_x)
            sy0 = int(by) - int(band_top)
            sx1 = sx0 + int(bw)
            sy1 = sy0 + int(bh)
            in_view = (sx0 < view_w and sx1 > 0 and sy0 < view_h and sy1 > 0)
            if in_view:
                d2 = _target_distance2(bx, by, bw, bh, player_x, player_y, player_w, player_h)
                if best_i < 0:
                    best_i = bi
                    best_d2 = d2
                elif pick_far:
                    if d2 > best_d2:
                        best_i = bi
                        best_d2 = d2
                elif d2 < best_d2:
                    best_i = bi
                    best_d2 = d2
        bi += 1
    return best_i


def _pick_enemy_hit_by_bullet(enemy_rows, enemy_states, bx, by, bw, bh, ignore_enemy_i=-1):
    if not enemy_rows:
        return -1
    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        if state is not None and ei != int(ignore_enemy_i):
            ex, ey, ew, eh, visible, _swappable = row
            if visible and bx < (ex + ew) and (bx + bw) > ex and by < (ey + eh) and (by + bh) > ey:
                return ei
        ei += 1
    return -1


def _enemy_has_support_ahead(tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, wx, wy, ow, oh, direction, step_px):
    step = int(step_px)
    if step < 1:
        step = 1
    if direction >= 0:
        probe_x = int(wx) + int(ow) + step - 2
    else:
        probe_x = int(wx) - step
    probe_y = int(wy) + int(oh) + 1
    return _aabb_collides_world(probe_x, probe_y, 2, 2, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids)


def _pick_enemy_frame_rect(enemy_state, anim_counter, facing, frame_w, frame_h, frame_hold):
    hold = int(frame_hold)
    if hold < 1:
        hold = 1
    frame_idx = int(anim_counter) // hold
    face_right = 1 if int(facing) >= 0 else 0
    state_code = int(enemy_state)
    if state_code == _ENEMY_STATE_SHOOT:
        if frame_idx > 9:
            frame_idx = 9
        src_y = 0 if face_right else frame_h
        src_x = frame_idx * frame_w
        return src_x, src_y, frame_w, frame_h
    walk_idx = frame_idx % 5
    src_y = frame_h * 2
    if face_right:
        src_x = walk_idx * frame_w
    else:
        src_x = (5 + walk_idx) * frame_w
    return src_x, src_y, frame_w, frame_h


def _aabb_near_view(wx, wy, w, h, camera_x, view_w, view_h, margin_x=0, margin_y=0):
    if w <= 0 or h <= 0 or view_w <= 0 or view_h <= 0:
        return False
    left = int(wx)
    top = int(wy)
    right = left + int(w)
    bottom = top + int(h)
    view_left = int(camera_x) - int(margin_x)
    view_top = -int(margin_y)
    view_right = int(camera_x) + int(view_w) + int(margin_x)
    view_bottom = int(view_h) + int(margin_y)
    return left < view_right and right > view_left and top < view_bottom and bottom > view_top


def _pack_enemy_render_descriptors(enemy_rows, enemy_states, camera_x=0, view_w=320, view_h=240, margin_x=48, margin_y=32):
    if not enemy_rows or not enemy_states:
        return bytearray(), 8, 0
    out = bytearray()
    count = 0
    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        if state is not None:
            wx, wy, ow, oh, visible, _swappable = row
            if visible and _aabb_near_view(wx, wy, ow, oh, camera_x, view_w, view_h, margin_x, margin_y):
                _append_i16_le(out, wx)
                _append_i16_le(out, wy)
                _append_u16_le(out, int(state.get("anim_counter", 0) or 0))
                out.append(int(state.get("state", _ENEMY_STATE_IDLE)) & 0xFF)
                out.append(1 if int(state.get("facing", 1)) >= 0 else 0)
                count += 1
        ei += 1
    return out, 8, count


def _make_solid_sprite_rgb565(sprite_w, sprite_h, color565, wire_order=False):
    if sprite_w <= 0 or sprite_h <= 0:
        return None
    raw = int(color565) & 0xFFFF
    if wire_order:
        raw = _swap16(raw)
    b0 = raw & 0xFF
    b1 = (raw >> 8) & 0xFF
    out = bytearray(sprite_w * sprite_h * 2)
    i = 0
    while i < len(out):
        out[i] = b0
        out[i + 1] = b1
        i += 2
    return out


def _lift_black_pixels_rgb565(sprite_buf, transparent_key, replacement_color):
    if sprite_buf is None:
        return None
    src = sprite_buf
    if isinstance(src, bytearray):
        out = bytearray(src)
    else:
        out = bytearray(bytes(src))
    key = int(transparent_key) & 0xFFFF
    repl = int(replacement_color) & 0xFFFF
    i = 0
    changed = 0
    while i + 1 < len(out):
        px = out[i] | (out[i + 1] << 8)
        if px != key and px == 0x0000:
            out[i] = repl & 0xFF
            out[i + 1] = (repl >> 8) & 0xFF
            changed += 1
        i += 2
    if changed <= 0:
        return sprite_buf
    return bytes(out)


def _spawn_enemy_bullet(enemy_bullets, max_bullets, bullet_x, bullet_y, vel_x, vel_y, bullet_w, bullet_h, shooter_enemy_i=-1):
    if enemy_bullets is None or max_bullets <= 0 or bullet_w <= 0 or bullet_h <= 0:
        return False
    _bullet_debug(
        "BULLET_SPAWN",
        "x=%d y=%d vx=%d vy=%d w=%d h=%d owner=%d" % (
            int(bullet_x),
            int(bullet_y),
            int(vel_x),
            int(vel_y),
            int(bullet_w),
            int(bullet_h),
            int(shooter_enemy_i),
        ),
    )
    i = 0
    while i < len(enemy_bullets):
        row = enemy_bullets[i]
        if not row[6]:
            row[0] = int(bullet_x)
            row[1] = int(bullet_y)
            row[2] = int(vel_x)
            row[3] = int(vel_y)
            row[4] = int(bullet_w)
            row[5] = int(bullet_h)
            row[6] = 1
            row[7] = int(shooter_enemy_i)
            return True
        i += 1
    if len(enemy_bullets) >= max_bullets:
        return False
    if hasattr(enemy_bullets, "append_row"):
        enemy_bullets.append_row([
            int(bullet_x),
            int(bullet_y),
            int(vel_x),
            int(vel_y),
            int(bullet_w),
            int(bullet_h),
            1,
            int(shooter_enemy_i),
        ])
    else:
        enemy_bullets.append([int(bullet_x), int(bullet_y), int(vel_x), int(vel_y), int(bullet_w), int(bullet_h), 1, int(shooter_enemy_i)])
    return True


def _find_enemy_bullet_spawn_y(
    desired_y,
    fallback_y,
    bullet_x,
    bullet_w,
    bullet_h,
    tilemap_idx,
    tilemap_w,
    tilemap_h,
    tile_size,
    object_solids,
):
    probe_y = int(desired_y)
    floor_y = int(fallback_y)
    if probe_y < floor_y:
        floor_y = probe_y
    while probe_y >= floor_y:
        if not _aabb_collides_world(
            int(bullet_x),
            probe_y,
            int(bullet_w),
            int(bullet_h),
            tilemap_idx,
            tilemap_w,
            tilemap_h,
            tile_size,
            object_solids,
        ):
            return probe_y
        probe_y -= 1
    return int(fallback_y)


def _clear_enemy_bullets(enemy_bullets):
    if enemy_bullets is None:
        return
    if hasattr(enemy_bullets, "clear"):
        enemy_bullets.clear()
    else:
        enemy_bullets[:] = []


def _render_enemies_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    camera_x,
    band_top,
    enemy_rows,
    enemy_states,
    enemy_sheet,
    enemy_sheet_w,
    enemy_sheet_h,
    enemy_frame_w,
    enemy_frame_h,
    enemy_frame_hold,
    submit_wire_order,
    submit_wire_runtime_swap,
):
    if (not enemy_rows) or (not enemy_states) or enemy_sheet is None:
        return
    colorkey = int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF
    if submit_wire_order and not submit_wire_runtime_swap:
        colorkey = _swap16(colorkey)
    key_b0 = colorkey & 0xFF
    key_b1 = (colorkey >> 8) & 0xFF
    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        if state is not None:
            wx, wy, _ow, _oh, visible, _swappable = row
            if visible:
                src_x, src_y, src_w, src_h = _pick_enemy_frame_rect(
                    int(state.get("state", _ENEMY_STATE_IDLE)),
                    int(state.get("anim_counter", 0)),
                    int(state.get("facing", 1)),
                    enemy_frame_w,
                    enemy_frame_h,
                    enemy_frame_hold,
                )
                _blit_atlas_region_colorkey_into_scene(
                    scene_buf,
                    scene_w,
                    scene_h,
                    int(wx) - int(camera_x),
                    int(wy) - int(band_top),
                    enemy_sheet,
                    enemy_sheet_w,
                    enemy_sheet_h,
                    src_x,
                    src_y,
                    src_w,
                    src_h,
                    key_b0,
                    key_b1,
                )
        ei += 1


def _render_enemy_bullets_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    camera_x,
    band_top,
    enemy_bullets,
    bullet_frame_right,
    bullet_frame_left,
    bullet_w,
    bullet_h,
    submit_wire_order,
    submit_wire_runtime_swap,
    bullet_color,
):
    if not enemy_bullets:
        return
    bi = 0
    while bi < len(enemy_bullets):
        bx, by, _vx, _vy, bw, bh, active = enemy_bullets[bi][0:7]
        if active:
            clip = _clip_rect_screen_xywh(int(bx) - int(camera_x), int(by) - int(band_top), int(bw), int(bh), scene_w, scene_h)
            if clip is not None:
                _fill_buffer_rect565(scene_buf, scene_w, clip[0], clip[1], clip[2], clip[3], bullet_color)
        bi += 1


def _update_enemies_and_bullets(
    enemy_rows,
    enemy_meta,
    enemy_states,
    enemy_bullets,
    player_x,
    player_y,
    player_w,
    player_h,
    vel_y,
    tilemap_idx,
    tilemap_w,
    tilemap_h,
    tile_size,
    object_solids,
    death_margin,
    enemy_detect_x,
    enemy_flee_x,
    enemy_detect_y,
    enemy_move_speed,
    enemy_gravity_step,
    enemy_frame_hold,
    enemy_shoot_fire_frame,
    enemy_bullet_speed,
    enemy_bullet_w,
    enemy_bullet_h,
    enemy_max_bullets,
    enemy_shoot_interval,
    fall_speed_max,
    map_w_px,
    map_h_px,
    camera_x=0,
    screen_w=320,
    screen_h=240,
    enemy_update_margin_x=160,
    enemy_update_margin_y=80,
    enemy_bullet_cull_margin=32,
):
    if (not enemy_rows) or (not enemy_states) or tilemap_idx is None or tilemap_w <= 0 or tilemap_h <= 0:
        return player_y, vel_y

    player_center_x_enemy = player_x + (player_w // 2)
    player_center_y_enemy = player_y + (player_h // 2)
    shoot_anim_total = 10 * enemy_frame_hold
    shoot_fire_tick = enemy_shoot_fire_frame * enemy_frame_hold
    if shoot_fire_tick < 1:
        shoot_fire_tick = enemy_frame_hold

    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        if state is not None:
            wx, wy, ew, eh, visible, _swappable = row
            if visible and ew > 0 and eh > 0:
                state_code = int(state.get("state", _ENEMY_STATE_IDLE))
                facing_enemy = 1 if int(state.get("facing", 1)) >= 0 else -1
                vel_enemy_y = int(state.get("vel_y", 0))
                shoot_cooldown = int(state.get("shoot_cooldown", 0))
                enemy_center_x = int(wx) + (int(ew) // 2)
                enemy_center_y = int(wy) + (int(eh) // 2)
                dx_to_player = player_center_x_enemy - enemy_center_x
                dy_to_player = player_center_y_enemy - enemy_center_y
                near_player_x = dx_to_player <= (enemy_detect_x + enemy_update_margin_x) if dx_to_player >= 0 else (-dx_to_player) <= (enemy_detect_x + enemy_update_margin_x)
                near_player_y = dy_to_player <= (enemy_detect_y + enemy_update_margin_y) if dy_to_player >= 0 else (-dy_to_player) <= (enemy_detect_y + enemy_update_margin_y)
                if not (_aabb_near_view(wx, wy, ew, eh, camera_x, screen_w, screen_h, enemy_update_margin_x, enemy_update_margin_y) or (near_player_x and near_player_y)):
                    ei += 1
                    continue
                if shoot_cooldown > 0:
                    shoot_cooldown -= 1
                detect_player = False
                if dx_to_player < 0:
                    detect_player = (-dx_to_player) <= enemy_detect_x
                else:
                    detect_player = dx_to_player <= enemy_detect_x
                if detect_player:
                    if dy_to_player < 0:
                        detect_player = (-dy_to_player) <= enemy_detect_y
                    else:
                        detect_player = dy_to_player <= enemy_detect_y
                flee_player = False
                if detect_player:
                    if dx_to_player < 0:
                        flee_player = (-dx_to_player) <= enemy_flee_x
                    else:
                        flee_player = dx_to_player <= enemy_flee_x
                aim_dir = 1 if dx_to_player >= 0 else -1
                move_enemy_x = 0
                if state_code == _ENEMY_STATE_SHOOT:
                    facing_enemy = aim_dir
                elif flee_player:
                    flee_dir = -1 if dx_to_player >= 0 else 1
                    if _enemy_has_support_ahead(
                        tilemap_idx,
                        tilemap_w,
                        tilemap_h,
                        tile_size,
                        object_solids,
                        wx,
                        wy,
                        ew,
                        eh,
                        flee_dir,
                        enemy_move_speed,
                    ):
                        if state_code != _ENEMY_STATE_WALK or int(state.get("facing", facing_enemy)) != flee_dir:
                            state["anim_counter"] = 0
                        facing_enemy = flee_dir
                        state_code = _ENEMY_STATE_WALK
                        move_enemy_x = flee_dir * enemy_move_speed
                    elif shoot_cooldown <= 0:
                        if state_code != _ENEMY_STATE_SHOOT or facing_enemy != aim_dir:
                            state["anim_counter"] = 0
                            state["shot_fired"] = 0
                        facing_enemy = aim_dir
                        state_code = _ENEMY_STATE_SHOOT
                    else:
                        facing_enemy = aim_dir
                        state_code = _ENEMY_STATE_IDLE
                elif detect_player:
                    facing_enemy = aim_dir
                    if shoot_cooldown <= 0:
                        if state_code != _ENEMY_STATE_SHOOT:
                            if facing_enemy != int(state.get("facing", facing_enemy)):
                                state["anim_counter"] = 0
                            state["shot_fired"] = 0
                        state_code = _ENEMY_STATE_SHOOT
                    else:
                        if facing_enemy != int(state.get("facing", facing_enemy)):
                            state["anim_counter"] = 0
                        state_code = _ENEMY_STATE_IDLE
                else:
                    state_code = _ENEMY_STATE_IDLE

                grounded_enemy = _aabb_collides_world(
                    int(wx),
                    int(wy) + 1,
                    int(ew),
                    int(eh),
                    tilemap_idx,
                    tilemap_w,
                    tilemap_h,
                    tile_size,
                    object_solids,
                )
                if not grounded_enemy:
                    vel_enemy_y += enemy_gravity_step
                    if vel_enemy_y > fall_speed_max:
                        vel_enemy_y = fall_speed_max
                elif vel_enemy_y > 0:
                    vel_enemy_y = 0

                wx, wy, _enemy_hit_x, enemy_hit_y = _move_axis_world(
                    tilemap_idx,
                    tilemap_w,
                    tilemap_h,
                    tile_size,
                    object_solids,
                    int(wx),
                    int(wy),
                    int(ew),
                    int(eh),
                    int(move_enemy_x),
                    int(vel_enemy_y),
                )
                max_enemy_x = map_w_px - int(ew)
                if max_enemy_x < 0:
                    max_enemy_x = 0
                wx = _clamp(int(wx), 0, max_enemy_x)
                if enemy_hit_y:
                    vel_enemy_y = 0
                if int(wy) < 0:
                    wy = 0
                    vel_enemy_y = 0
                if int(wy) > (map_h_px + death_margin):
                    row[1] = int(wy)
                    row[4] = 0
                    _reset_enemy_state(state, enemy_meta[ei] if ei < len(enemy_meta) else None)
                else:
                    row[0] = int(wx)
                    row[1] = int(wy)
                    state["facing"] = facing_enemy
                    state["state"] = state_code
                    state["shoot_cooldown"] = shoot_cooldown
                    state["vel_y"] = vel_enemy_y
                    if state_code == _ENEMY_STATE_WALK:
                        state["anim_counter"] = int(state.get("anim_counter", 0)) + 1
                        state["shot_fired"] = 0
                    elif state_code == _ENEMY_STATE_SHOOT:
                        state["anim_counter"] = int(state.get("anim_counter", 0)) + 1
                        if (not int(state.get("shot_fired", 0))) and int(state.get("anim_counter", 0)) >= shoot_fire_tick:
                            bullet_vx = enemy_bullet_speed * facing_enemy
                            bullet_x = int(row[0]) + ((int(ew) - enemy_bullet_w) // 2)
                            if facing_enemy >= 0:
                                bullet_x = int(row[0]) + int(ew)
                            else:
                                bullet_x = int(row[0]) - enemy_bullet_w
                            bullet_base_y = int(row[1]) + (int(eh) // 2) - (enemy_bullet_h // 2)
                            bullet_y = _find_enemy_bullet_spawn_y(
                                bullet_base_y + 16,
                                bullet_base_y,
                                bullet_x,
                                enemy_bullet_w,
                                enemy_bullet_h,
                                tilemap_idx,
                                tilemap_w,
                                tilemap_h,
                                tile_size,
                                object_solids,
                            )
                            _spawn_enemy_bullet(
                                enemy_bullets,
                                enemy_max_bullets,
                                bullet_x,
                                bullet_y,
                                bullet_vx,
                                0,
                                enemy_bullet_w,
                                enemy_bullet_h,
                                ei,
                            )
                            state["shot_fired"] = 1
                        if int(state.get("anim_counter", 0)) >= shoot_anim_total:
                            state["anim_counter"] = 0
                            state["shot_fired"] = 0
                            state["state"] = _ENEMY_STATE_IDLE
                            state["shoot_cooldown"] = enemy_shoot_interval
                    else:
                        state["anim_counter"] = 0
                        state["shot_fired"] = 0
        ei += 1

    bi = 0
    while bi < len(enemy_bullets):
        bullet = enemy_bullets[bi]
        if bullet[6]:
            bx = int(bullet[0]) + int(bullet[2])
            by = int(bullet[1]) + int(bullet[3])
            bw = int(bullet[4])
            bh = int(bullet[5])
            shooter_enemy_i = int(bullet[7]) if len(bullet) > 7 else -1
            active = 1
            if (bx + bw) < 0 or bx > map_w_px or by > (map_h_px + death_margin):
                active = 0
                _bullet_debug("BULLET_CULL", "oob x=%d y=%d w=%d h=%d" % (bx, by, bw, bh))
            elif not _aabb_near_view(bx, by, bw, bh, camera_x, screen_w, screen_h, enemy_bullet_cull_margin, enemy_bullet_cull_margin):
                active = 0
                _bullet_debug("BULLET_CULL", "view x=%d y=%d cam=%d screen=%d,%d" % (bx, by, int(camera_x), int(screen_w), int(screen_h)))
            elif _aabb_collides_world(bx, by, bw, bh, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
                active = 0
                _bullet_debug("BULLET_CULL", "world x=%d y=%d" % (bx, by))
            else:
                hit_enemy_i = _pick_enemy_hit_by_bullet(enemy_rows, enemy_states, bx, by, bw, bh, shooter_enemy_i)
                if hit_enemy_i >= 0:
                    active = 0
                    _bullet_debug("BULLET_HIT", "enemy idx=%d x=%d y=%d" % (int(hit_enemy_i), bx, by))
                    enemy_row = enemy_rows[hit_enemy_i]
                    enemy_row[4] = 0
                    hit_state = enemy_states[hit_enemy_i] if hit_enemy_i < len(enemy_states) else None
                    if hit_state is not None:
                        _reset_enemy_state(hit_state, enemy_meta[hit_enemy_i] if hit_enemy_i < len(enemy_meta) else None)
            if active and player_x < (bx + bw) and (player_x + player_w) > bx and player_y < (by + bh) and (player_y + player_h) > by:
                active = 0
                _bullet_debug("BULLET_HIT", "player x=%d y=%d" % (bx, by))
                player_y = map_h_px + death_margin + 1
                vel_y = 0
            if active:
                bullet[0] = bx
                bullet[1] = by
            else:
                bullet[6] = 0
        bi += 1
    _bullet_debug_active(enemy_bullets, camera_x, screen_w, screen_h)
    return player_y, vel_y


def _update_enemies_and_bullets_native(
    enemy_rows,
    enemy_meta,
    enemy_states,
    enemy_bullets,
    enemy_rows_c_buf,
    enemy_rows_c_stride,
    enemy_rows_c_count,
    object_solids_c_buf,
    object_solids_c_stride,
    object_solids_c_count,
    player_x,
    player_y,
    player_w,
    player_h,
    vel_y,
    tilemap_idx,
    tilemap_w,
    tilemap_h,
    tile_size,
    death_margin,
    enemy_detect_x,
    enemy_flee_x,
    enemy_detect_y,
    enemy_move_speed,
    enemy_gravity_step,
    enemy_frame_hold,
    enemy_shoot_fire_frame,
    enemy_bullet_speed,
    enemy_bullet_w,
    enemy_bullet_h,
    enemy_shoot_interval,
    fall_speed_max,
    map_w_px,
    map_h_px,
    camera_x=0,
    screen_w=320,
    screen_h=240,
    enemy_update_margin_x=160,
    enemy_update_margin_y=80,
    enemy_bullet_cull_margin=32,
):
    global _enemy_native_update_disabled
    if _enemy_native_update_disabled:
        return None
    if _lgfx is None or not hasattr(_lgfx, 'update_enemies_native'):
        return None
    if (not enemy_rows) or (not enemy_states) or tilemap_idx is None or tilemap_w <= 0 or tilemap_h <= 0:
        return None
    if enemy_rows_c_buf is None or enemy_rows_c_count <= 0:
        return None
    if not hasattr(enemy_states, '_buf') or not hasattr(enemy_bullets, '_buf'):
        return None
    try:
        out = _lgfx.update_enemies_native(
            enemy_rows_c_buf,
            enemy_rows_c_stride,
            enemy_states._buf,
            _ENEMY_STATE_STRIDE,
            enemy_rows_c_count,
            enemy_bullets._buf,
            _BULLET_STATE_STRIDE,
            len(enemy_bullets),
            player_x,
            player_y,
            player_w,
            player_h,
            vel_y,
            tilemap_idx,
            tilemap_w,
            tilemap_h,
            tile_size,
            object_solids_c_buf,
            object_solids_c_stride,
            object_solids_c_count,
            death_margin,
            enemy_detect_x,
            enemy_flee_x,
            enemy_detect_y,
            enemy_move_speed,
            enemy_gravity_step,
            enemy_frame_hold,
            enemy_shoot_fire_frame,
            enemy_bullet_speed,
            enemy_bullet_w,
            enemy_bullet_h,
            enemy_shoot_interval,
            fall_speed_max,
            map_w_px,
            map_h_px,
            camera_x,
            screen_w,
            screen_h,
            enemy_update_margin_x,
            enemy_update_margin_y,
            enemy_bullet_cull_margin,
        )
        _sync_enemy_rows_from_c(enemy_rows, enemy_rows_c_buf, enemy_rows_c_stride)
        return int(out[0]), int(out[1])
    except Exception as e:
        _enemy_native_update_disabled = True
        print('ENEMY_UPDATE_NATIVE_FALLBACK %s' % e)
        return None


def _perform_world_swap(
    swap_triggered,
    swap_pick_far,
    objects_rows,
    objects_meta,
    enemy_rows,
    enemy_states,
    enemy_bullets,
    player_x,
    player_y,
    player_w,
    player_h,
    camera_x,
    band_top,
    view_w,
    view_h,
    max_player_x,
    map_h_px,
    vel_y,
    objects_c_buf,
    objects_c_stride,
):
    if not swap_triggered or (not objects_rows and not enemy_rows and not enemy_bullets):
        return player_x, player_y, vel_y, _rebuild_object_solids(objects_rows)

    object_ti = -1
    enemy_ti = -1
    bullet_ti = -1
    if objects_rows:
        object_ti = _pick_swappable_object_index(
            objects_rows,
            player_x,
            player_y,
            player_w,
            player_h,
            swap_pick_far,
            camera_x,
            band_top,
            view_w,
            view_h,
        )
    if enemy_rows:
        enemy_ti = _pick_swappable_enemy_index(
            enemy_rows,
            player_x,
            player_y,
            player_w,
            player_h,
            swap_pick_far,
            camera_x,
            band_top,
            view_w,
            view_h,
        )
    if enemy_bullets:
        bullet_ti = _pick_swappable_bullet_index(
            enemy_bullets,
            player_x,
            player_y,
            player_w,
            player_h,
            swap_pick_far,
            camera_x,
            band_top,
            view_w,
            view_h,
        )

    target_kind = None
    ti = -1
    if object_ti >= 0:
        row = objects_rows[object_ti]
        target_kind = "object"
        ti = object_ti
        best_d2 = _target_distance2(row[0], row[1], row[2], row[3], player_x, player_y, player_w, player_h)
    else:
        best_d2 = -1
    if enemy_ti >= 0:
        row = enemy_rows[enemy_ti]
        d2 = _target_distance2(row[0], row[1], row[2], row[3], player_x, player_y, player_w, player_h)
        if ti < 0 or (swap_pick_far and d2 > best_d2) or ((not swap_pick_far) and d2 < best_d2):
            target_kind = "enemy"
            ti = enemy_ti
            best_d2 = d2
    if bullet_ti >= 0:
        row = enemy_bullets[bullet_ti]
        d2 = _target_distance2(row[0], row[1], row[4], row[5], player_x, player_y, player_w, player_h)
        if ti < 0 or (swap_pick_far and d2 > best_d2) or ((not swap_pick_far) and d2 < best_d2):
            target_kind = "bullet"
            ti = bullet_ti
            best_d2 = d2

    object_solids = _rebuild_object_solids(objects_rows)
    if target_kind == "object" and ti >= 0:
        row = objects_rows[ti]
        meta = objects_meta[ti] if ti < len(objects_meta) else None
        old_px = player_x
        old_py = player_y
        old_ox = int(row[0])
        old_oy = int(row[1])
        obj_w = int(row[2])
        obj_h = int(row[3])
        player_x = old_ox + ((obj_w - player_w) // 2)
        player_y = old_oy + (obj_h - player_h)
        row[0] = int(old_px + ((player_w - obj_w) // 2))
        row[1] = int(old_py + (player_h - obj_h))
        object_solids = _rebuild_object_solids(objects_rows)
        max_player_y_swap = map_h_px - player_h
        if max_player_y_swap < 0:
            max_player_y_swap = 0
        player_x = _clamp(player_x, 0, max_player_x)
        player_y = _clamp(player_y, 0, max_player_y_swap)
        _repack_single_object_entry(objects_c_buf, objects_c_stride, ti, row[0], row[1], row[8], row[9], row[10], row[11], meta)
        object_solids = _rebuild_object_solids(objects_rows)
        vel_y = 0
        if swap_pick_far:
            print("SWAP_FAR_OK_V2 idx=%d px=%d py=%d" % (ti, player_x, player_y))
        else:
            print("SWAP_NEAR_OK_V2 idx=%d px=%d py=%d" % (ti, player_x, player_y))
    elif target_kind == "enemy" and ti >= 0:
        row = enemy_rows[ti]
        state = enemy_states[ti] if ti < len(enemy_states) else None
        old_px = player_x
        old_py = player_y
        old_ex = int(row[0])
        old_ey = int(row[1])
        enemy_w = int(row[2])
        enemy_h = int(row[3])
        player_x = old_ex + ((enemy_w - player_w) // 2)
        player_y = old_ey + (enemy_h - player_h)
        row[0] = int(old_px + ((player_w - enemy_w) // 2))
        row[1] = int(old_py + (player_h - enemy_h))
        max_player_y_swap = map_h_px - player_h
        if max_player_y_swap < 0:
            max_player_y_swap = 0
        player_x = _clamp(player_x, 0, max_player_x)
        player_y = _clamp(player_y, 0, max_player_y_swap)
        vel_y = 0
        if state is not None:
            state["vel_y"] = 0
        if enemy_bullets:
            bi = 0
            while bi < len(enemy_bullets):
                bullet = enemy_bullets[bi]
                if len(bullet) > 7 and int(bullet[7]) == int(ti):
                    bullet[7] = -1
                bi += 1
        if swap_pick_far:
            print("SWAP_FAR_OK_ENEMY idx=%d px=%d py=%d" % (ti, player_x, player_y))
        else:
            print("SWAP_NEAR_OK_ENEMY idx=%d px=%d py=%d" % (ti, player_x, player_y))
    elif target_kind == "bullet" and ti >= 0:
        row = enemy_bullets[ti]
        old_px = player_x
        old_py = player_y
        old_bx = int(row[0])
        old_by = int(row[1])
        bullet_w = int(row[4])
        bullet_h = int(row[5])
        player_x = old_bx + ((bullet_w - player_w) // 2)
        player_y = old_by + (bullet_h - player_h)
        row[0] = int(old_px + ((player_w - bullet_w) // 2))
        row[1] = int(old_py + (player_h - bullet_h))
        max_player_y_swap = map_h_px - player_h
        if max_player_y_swap < 0:
            max_player_y_swap = 0
        player_x = _clamp(player_x, 0, max_player_x)
        player_y = _clamp(player_y, 0, max_player_y_swap)
        vel_y = 0
        if len(row) > 7:
            row[7] = -1
        if swap_pick_far:
            print("SWAP_FAR_OK_BULLET idx=%d px=%d py=%d" % (ti, player_x, player_y))
        else:
            print("SWAP_NEAR_OK_BULLET idx=%d px=%d py=%d" % (ti, player_x, player_y))
    else:
        print("SWAP_FAIL_NO_TARGET_V2")
    return player_x, player_y, vel_y, object_solids


def _is_special_render_object(meta):
    return bool(meta and meta.get("special_render"))

def _pack_enemy_rows_for_c(rows, meta_rows=None):
    if not rows:
        return bytearray(), _ENEMY_ROW_STRIDE, 0
    out = bytearray(len(rows) * _ENEMY_ROW_STRIDE)
    oi = 0
    bi = 0
    while oi < len(rows):
        wx, wy, ow, oh, visible, swappable = rows[oi]
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        default_facing = 1
        if meta is not None:
            mf = str(meta.get("facing", "R") or "R").upper()
            default_facing = 1 if mf != "L" else -1
        _buf_set_i16_le(out, bi + 0, wx)
        _buf_set_i16_le(out, bi + 2, wy)
        _buf_set_i16_le(out, bi + 4, ow)
        _buf_set_i16_le(out, bi + 6, oh)
        out[bi + 8] = 1 if int(visible) else 0
        out[bi + 9] = 1 if int(swappable) else 0
        out[bi + 10] = 1 if default_facing >= 0 else 0
        out[bi + 11] = 0
        bi += _ENEMY_ROW_STRIDE
        oi += 1
    return out, _ENEMY_ROW_STRIDE, len(rows)


def _sync_enemy_rows_from_c(rows, enemy_rows_c_buf, enemy_rows_c_stride):
    if not rows or enemy_rows_c_buf is None or enemy_rows_c_stride < _ENEMY_ROW_STRIDE:
        return
    limit = len(enemy_rows_c_buf) // int(enemy_rows_c_stride)
    if len(rows) < limit:
        limit = len(rows)
    i = 0
    while i < limit:
        base = i * int(enemy_rows_c_stride)
        row = rows[i]
        row[0] = _buf_get_i16_le(enemy_rows_c_buf, base + 0)
        row[1] = _buf_get_i16_le(enemy_rows_c_buf, base + 2)
        row[2] = _buf_get_i16_le(enemy_rows_c_buf, base + 4)
        row[3] = _buf_get_i16_le(enemy_rows_c_buf, base + 6)
        row[4] = 1 if enemy_rows_c_buf[base + 8] else 0
        row[5] = 1 if enemy_rows_c_buf[base + 9] else 0
        i += 1


def _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, rows, meta_rows=None):
    if enemy_rows_c_buf is None or enemy_rows_c_stride < _ENEMY_ROW_STRIDE or not rows:
        return 0
    limit = len(enemy_rows_c_buf) // int(enemy_rows_c_stride)
    if len(rows) < limit:
        limit = len(rows)
    oi = 0
    while oi < limit:
        base = oi * int(enemy_rows_c_stride)
        wx, wy, ow, oh, visible, swappable = rows[oi]
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        default_facing = 1
        if meta is not None:
            mf = str(meta.get("facing", "R") or "R").upper()
            default_facing = 1 if mf != "L" else -1
        _buf_set_i16_le(enemy_rows_c_buf, base + 0, wx)
        _buf_set_i16_le(enemy_rows_c_buf, base + 2, wy)
        _buf_set_i16_le(enemy_rows_c_buf, base + 4, ow)
        _buf_set_i16_le(enemy_rows_c_buf, base + 6, oh)
        enemy_rows_c_buf[base + 8] = 1 if int(visible) else 0
        enemy_rows_c_buf[base + 9] = 1 if int(swappable) else 0
        enemy_rows_c_buf[base + 10] = 1 if default_facing >= 0 else 0
        enemy_rows_c_buf[base + 11] = 0
        oi += 1
    return limit


def _pack_object_solids_for_c(object_solids):
    if not object_solids:
        return bytearray(), _OBJECT_SOLID_STRIDE, 0
    out = bytearray(len(object_solids) * _OBJECT_SOLID_STRIDE)
    i = 0
    bi = 0
    while i < len(object_solids):
        ox, oy, ow, oh = object_solids[i]
        _buf_set_i16_le(out, bi + 0, ox)
        _buf_set_i16_le(out, bi + 2, oy)
        _buf_set_i16_le(out, bi + 4, ow)
        _buf_set_i16_le(out, bi + 6, oh)
        bi += _OBJECT_SOLID_STRIDE
        i += 1
    return out, _OBJECT_SOLID_STRIDE, len(object_solids)


def _sync_object_solids_c_from_list(object_solids_c_buf, object_solids_c_stride, object_solids):
    if object_solids_c_buf is None or object_solids_c_stride < _OBJECT_SOLID_STRIDE:
        return 0
    limit = len(object_solids_c_buf) // int(object_solids_c_stride)
    src_count = 0 if not object_solids else len(object_solids)
    if src_count < limit:
        limit = src_count
    i = 0
    while i < limit:
        base = i * int(object_solids_c_stride)
        ox, oy, ow, oh = object_solids[i]
        _buf_set_i16_le(object_solids_c_buf, base + 0, ox)
        _buf_set_i16_le(object_solids_c_buf, base + 2, oy)
        _buf_set_i16_le(object_solids_c_buf, base + 4, ow)
        _buf_set_i16_le(object_solids_c_buf, base + 6, oh)
        i += 1
    while i < (len(object_solids_c_buf) // int(object_solids_c_stride)):
        base = i * int(object_solids_c_stride)
        _buf_set_i16_le(object_solids_c_buf, base + 0, 0)
        _buf_set_i16_le(object_solids_c_buf, base + 2, 0)
        _buf_set_i16_le(object_solids_c_buf, base + 4, 0)
        _buf_set_i16_le(object_solids_c_buf, base + 6, 0)
        i += 1
    return src_count


def _pack_objects_for_c(rows, meta_rows=None):
    if not rows:
        return bytearray(), 12, 0
    out = bytearray(len(rows) * 12)
    oi = 0
    bi = 0
    while oi < len(rows):
        wx, wy, _ow, _oh, _solid, _layer, visible, _swappable, sx, sy, sw, sh = rows[oi]
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        if _is_special_render_object(meta):
            sx = 0
            sy = 0
            sw = 0
            sh = 0
        if visible:
            for v in (wx, wy, sx, sy, sw, sh):
                iv = int(v)
                if iv < -32768:
                    iv = -32768
                if iv > 65535:
                    iv = 65535
                uv = iv & 0xFFFF
                out[bi] = uv & 0xFF
                out[bi + 1] = (uv >> 8) & 0xFF
                bi += 2
        oi += 1
    if bi != len(out):
        out = out[:bi]
    count = bi // 12
    return out, 12, count

def _pick_swappable_object_index(objects_rows, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h):
    if not objects_rows:
        return -1
    px = player_x + (player_w // 2)
    py = player_y + (player_h // 2)
    best_i = -1
    best_d2 = -1
    oi = 0
    while oi < len(objects_rows):
        wx, wy, ow, oh, _solid, _layer, visible, swappable, _sx, _sy, _sw, _sh = objects_rows[oi]
        if visible and swappable:
            sx0 = int(wx) - int(camera_x)
            sy0 = int(wy) - int(band_top)
            sx1 = sx0 + int(ow)
            sy1 = sy0 + int(oh)
            in_view = (sx0 < view_w and sx1 > 0 and sy0 < view_h and sy1 > 0)
            if in_view:
                ox = int(wx) + (int(ow) // 2)
                oy = int(wy) + (int(oh) // 2)
                dx = ox - px
                dy = oy - py
                d2 = dx * dx + dy * dy
                if best_i < 0:
                    best_i = oi
                    best_d2 = d2
                else:
                    if pick_far:
                        if d2 > best_d2:
                            best_i = oi
                            best_d2 = d2
                    else:
                        if d2 < best_d2:
                            best_i = oi
                            best_d2 = d2
        oi += 1
    return best_i


def _clone_object_rows(rows):
    if not rows:
        return []
    return [list(row) for row in rows]


def _restore_objects_rows(rows, saved_rows, objects_c_buf, objects_c_stride, meta_rows=None):
    if not rows or not saved_rows:
        return
    limit = len(rows)
    if len(saved_rows) < limit:
        limit = len(saved_rows)
    oi = 0
    while oi < limit:
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        if meta and meta.get("checkpoint"):
            oi += 1
            continue
        saved = saved_rows[oi]
        row = rows[oi]
        row[0] = int(saved[0])
        row[1] = int(saved[1])
        row[2] = int(saved[2])
        row[3] = int(saved[3])
        row[4] = int(saved[4])
        row[5] = int(saved[5])
        row[6] = int(saved[6])
        row[7] = int(saved[7])
        row[8] = int(saved[8])
        row[9] = int(saved[9])
        row[10] = int(saved[10])
        row[11] = int(saved[11])
        if row[6]:
            _repack_single_object_entry(
                objects_c_buf,
                objects_c_stride,
                oi,
                row[0],
                row[1],
                row[8],
                row[9],
                row[10],
                row[11],
                meta,
            )
        else:
            _repack_single_object_entry(objects_c_buf, objects_c_stride, oi, row[0], row[1], 0, 0, 0, 0, meta)
        oi += 1


def _repack_single_object_entry(objects_c_buf, obj_stride, row_index, wx, wy, sx, sy, sw, sh, meta=None):
    if objects_c_buf is None or obj_stride < 12 or row_index < 0:
        return
    base = row_index * obj_stride
    if base + 12 > len(objects_c_buf):
        return
    if _is_special_render_object(meta):
        sx = 0
        sy = 0
        sw = 0
        sh = 0
    vals = (wx, wy, sx, sy, sw, sh)
    bi = base
    for v in vals:
        iv = int(v)
        if iv < -32768:
            iv = -32768
        if iv > 65535:
            iv = 65535
        uv = iv & 0xFFFF
        objects_c_buf[bi] = uv & 0xFF
        objects_c_buf[bi + 1] = (uv >> 8) & 0xFF
        bi += 2


def _rebuild_object_solids(objects_rows):
    out = []
    if not objects_rows:
        return out
    i = 0
    while i < len(objects_rows):
        wx, wy, ow, oh, solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = objects_rows[i]
        if visible and solid:
            out.append((wx, wy, ow, oh))
        i += 1
    return out


def _object_valid_after_swap(objects_rows, row_index, tilemap_idx, tilemap_w, tilemap_h, tile_size):
    if row_index < 0 or row_index >= len(objects_rows):
        return False
    wx, wy, ow, oh, solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = objects_rows[row_index]
    if not visible or ow <= 0 or oh <= 0:
        return False
    # Only solid objects must stay out of tilemap blocks.
    # Decorative/non-solid objects are allowed to overlap map graphics.
    if solid and tilemap_idx is not None and tilemap_w > 0 and tilemap_h > 0:
        if _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, int(wx), int(wy), int(ow), int(oh)):
            return False
    i = 0
    while i < len(objects_rows):
        if i != row_index:
            x2, y2, w2, h2, _s2, _l2, v2, _sw2, _sx2, _sy2, _sw3, _sh3 = objects_rows[i]
            if v2 and w2 > 0 and h2 > 0:
                if int(wx) < int(x2) + int(w2) and int(wx) + int(ow) > int(x2) and int(wy) < int(y2) + int(h2) and int(wy) + int(oh) > int(y2):
                    return False
        i += 1
    return True



def _blit_atlas_region_colorkey_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    dst_x,
    dst_y,
    atlas_buf,
    atlas_w,
    atlas_h,
    src_x,
    src_y,
    src_w,
    src_h,
    key_b0,
    key_b1,
):
    if dst_x >= scene_w or dst_y >= scene_h or (dst_x + src_w) <= 0 or (dst_y + src_h) <= 0:
        return
    if src_x < 0 or src_y < 0 or src_w <= 0 or src_h <= 0:
        return
    if src_x + src_w > atlas_w or src_y + src_h > atlas_h:
        return

    src_x0 = 0
    src_y0 = 0
    dst_x0 = dst_x
    dst_y0 = dst_y
    copy_w = src_w
    copy_h = src_h
    if dst_x0 < 0:
        src_x0 = -dst_x0
        copy_w -= src_x0
        dst_x0 = 0
    if dst_y0 < 0:
        src_y0 = -dst_y0
        copy_h -= src_y0
        dst_y0 = 0
    if dst_x0 + copy_w > scene_w:
        copy_w = scene_w - dst_x0
    if dst_y0 + copy_h > scene_h:
        copy_h = scene_h - dst_y0
    if copy_w <= 0 or copy_h <= 0:
        return

    src_row_bytes = atlas_w * 2
    dst_row_bytes = scene_w * 2
    r = 0
    while r < copy_h:
        sy = src_y + src_y0 + r
        sx = src_x + src_x0
        src_off = (sy * src_row_bytes) + (sx * 2)
        dst_off = ((dst_y0 + r) * dst_row_bytes) + (dst_x0 * 2)
        x = 0
        while x < copy_w:
            s0 = atlas_buf[src_off]
            s1 = atlas_buf[src_off + 1]
            if not (s0 == key_b0 and s1 == key_b1):
                scene_buf[dst_off] = s0
                scene_buf[dst_off + 1] = s1
            src_off += 2
            dst_off += 2
            x += 1
        r += 1


def _render_special_objects_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    camera_x,
    band_top,
    objects_rows,
    object_meta_rows,
    object_animations,
    anim_counter,
    submit_wire_order,
    submit_wire_runtime_swap,
):
    if (not objects_rows) or (not object_meta_rows) or (not object_animations):
        return
    colorkey = int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF
    if submit_wire_order and not submit_wire_runtime_swap:
        colorkey = _swap16(colorkey)
    key_b0 = colorkey & 0xFF
    key_b1 = (colorkey >> 8) & 0xFF
    oi = 0
    while oi < len(objects_rows):
        meta = object_meta_rows[oi] if oi < len(object_meta_rows) else None
        if _is_special_render_object(meta):
            anim_spec = object_animations.get(meta.get("anim_id", ""))
            frame_rgb565, frame_w, frame_h = _pick_animation_frame(anim_spec, anim_counter)
            if frame_rgb565 is not None and frame_w > 0 and frame_h > 0:
                wx, wy, _ow, _oh, _solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = objects_rows[oi]
                if visible:
                    _blit_sprite_colorkey_into_scene(
                        scene_buf,
                        scene_w,
                        scene_h,
                        int(wx) - int(camera_x),
                        int(wy) - int(band_top),
                        frame_rgb565,
                        key_b0,
                        key_b1,
                        frame_w,
                        frame_h,
                    )
        oi += 1


def _render_anchor_into_scene(
    scene_buf,
    scene_w,
    scene_h,
    camera_x,
    band_top,
    anchor_active,
    anchor_x,
    anchor_y,
    anchor_anim_spec,
    anim_counter,
    submit_wire_order,
    submit_wire_runtime_swap,
):
    if not anchor_active or not anchor_anim_spec:
        return
    frame_rgb565, frame_w, frame_h = _pick_animation_frame(anchor_anim_spec, anim_counter)
    if frame_rgb565 is None or frame_w <= 0 or frame_h <= 0:
        return
    colorkey = int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF
    if submit_wire_order and not submit_wire_runtime_swap:
        colorkey = _swap16(colorkey)
    key_b0 = colorkey & 0xFF
    key_b1 = (colorkey >> 8) & 0xFF
    _blit_sprite_colorkey_into_scene(
        scene_buf,
        scene_w,
        scene_h,
        int(anchor_x) - int(camera_x),
        int(anchor_y) - int(band_top),
        frame_rgb565,
        key_b0,
        key_b1,
        frame_w,
        frame_h,
    )


def _append_u16_le(buf, value):
    iv = int(value)
    if iv < 0:
        iv = 0
    if iv > 65535:
        iv = 65535
    buf.append(iv & 0xFF)
    buf.append((iv >> 8) & 0xFF)


def _append_i16_le(buf, value):
    iv = int(value)
    if iv < -32768:
        iv = -32768
    if iv > 32767:
        iv = 32767
    uv = iv & 0xFFFF
    buf.append(uv & 0xFF)
    buf.append((uv >> 8) & 0xFF)


def _pack_special_render_overlays(
    objects_rows,
    object_meta_rows,
    object_animations,
    object_anim_counter,
    anchor_active,
    anchor_x,
    anchor_y,
    anchor_anim_spec,
    anchor_anim_counter,
    enemy_bullets=None,
    bullet_frame_right=None,
    bullet_frame_left=None,
    bullet_w=0,
    bullet_h=0,
    camera_x=0,
    view_w=320,
    view_h=240,
    bullet_margin=32,
):
    overlay_desc = bytearray()
    overlay_frames = []
    overlay_stride = 10
    overlay_count = 0
    if objects_rows and object_meta_rows and object_animations:
        oi = 0
        while oi < len(objects_rows):
            meta = object_meta_rows[oi] if oi < len(object_meta_rows) else None
            if _is_special_render_object(meta):
                anim_spec = object_animations.get(meta.get("anim_id", ""))
                frame_rgb565, frame_w, frame_h = _pick_animation_frame(anim_spec, object_anim_counter)
                if frame_rgb565 is not None and frame_w > 0 and frame_h > 0:
                    wx, wy, _ow, _oh, _solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = objects_rows[oi]
                    if visible:
                        frame_index = len(overlay_frames)
                        overlay_frames.append(frame_rgb565)
                        _append_i16_le(overlay_desc, wx)
                        _append_i16_le(overlay_desc, wy)
                        _append_u16_le(overlay_desc, frame_w)
                        _append_u16_le(overlay_desc, frame_h)
                        _append_u16_le(overlay_desc, frame_index)
                        overlay_count += 1
            oi += 1
    if anchor_active and anchor_anim_spec:
        frame_rgb565, frame_w, frame_h = _pick_animation_frame(anchor_anim_spec, anchor_anim_counter)
        if frame_rgb565 is not None and frame_w > 0 and frame_h > 0:
            frame_index = len(overlay_frames)
            overlay_frames.append(frame_rgb565)
            _append_i16_le(overlay_desc, anchor_x)
            _append_i16_le(overlay_desc, anchor_y)
            _append_u16_le(overlay_desc, frame_w)
            _append_u16_le(overlay_desc, frame_h)
            _append_u16_le(overlay_desc, frame_index)
            overlay_count += 1
    bullet_frame_right_index = -1
    bullet_frame_left_index = -1
    if enemy_bullets and bullet_w > 0 and bullet_h > 0:
        if bullet_frame_right is not None:
            bullet_frame_right_index = len(overlay_frames)
            overlay_frames.append(bullet_frame_right)
        if bullet_frame_left is not None:
            bullet_frame_left_index = len(overlay_frames)
            overlay_frames.append(bullet_frame_left)
        bi = 0
        while bi < len(enemy_bullets):
            bx, by, vx, _vy, bw, bh, active = enemy_bullets[bi][0:7]
            if active and _aabb_near_view(bx, by, bw, bh, camera_x, view_w, view_h, bullet_margin, bullet_margin):
                frame_index = bullet_frame_right_index
                if int(vx) < 0 and bullet_frame_left_index >= 0:
                    frame_index = bullet_frame_left_index
                elif int(vx) >= 0 and bullet_frame_right_index < 0:
                    frame_index = bullet_frame_left_index
                elif int(vx) < 0 and bullet_frame_left_index < 0:
                    frame_index = bullet_frame_right_index
                if frame_index < 0:
                    bi += 1
                    continue
                _append_i16_le(overlay_desc, bx)
                _append_i16_le(overlay_desc, by)
                _append_u16_le(overlay_desc, bullet_w)
                _append_u16_le(overlay_desc, bullet_h)
                _append_u16_le(overlay_desc, frame_index)
                overlay_count += 1
                if overlay_count <= 3:
                    _bullet_debug(
                        "BULLET_OVERLAY",
                        "wx=%d wy=%d sx=%d sy=%d vx=%d frame=%d cam=%d view=%d,%d" % (
                            int(bx),
                            int(by),
                            int(bx) - int(camera_x),
                            int(by),
                            int(vx),
                            int(frame_index),
                            int(camera_x),
                            int(view_w),
                            int(view_h),
                        ),
                    )
            bi += 1
    return overlay_desc, overlay_stride, overlay_count, tuple(overlay_frames)


def _aabb_collides_objects(px, py, pw, ph, object_solids):
    if not object_solids:
        return False
    p_right = px + pw
    p_bottom = py + ph
    i = 0
    while i < len(object_solids):
        ox, oy, ow, oh = object_solids[i]
        if px < (ox + ow) and p_right > ox and py < (oy + oh) and p_bottom > oy:
            return True
        i += 1
    return False


def _aabb_collides_world(px, py, pw, ph, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
    if tilemap_idx is not None and tilemap_w > 0 and tilemap_h > 0:
        if _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, px, py, pw, ph):
            return True
    if _aabb_collides_objects(px, py, pw, ph, object_solids):
        return True
    return False


def _move_axis_world(tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, px, py, pw, ph, dx, dy):
    hit_x = False
    hit_y = False
    nx = px
    ny = py
    sx = 1 if dx > 0 else -1
    sy = 1 if dy > 0 else -1
    ax = dx if dx >= 0 else -dx
    ay = dy if dy >= 0 else -dy

    while ax > 0:
        tx = nx + sx
        if _aabb_collides_world(tx, ny, pw, ph, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
            hit_x = True
            break
        nx = tx
        ax -= 1

    while ay > 0:
        ty = ny + sy
        if _aabb_collides_world(nx, ty, pw, ph, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
            hit_y = True
            break
        ny = ty
        ay -= 1

    return nx, ny, hit_x, hit_y


def _swap16(v):
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)


def _load_tileset_raw_rgb565(path, atlas_w=64, atlas_h=64):
    try:
        with open(path, 'rb') as fp:
            data = fp.read()
    except Exception:
        return None
    exp = atlas_w * atlas_h * 2
    if data is None or len(data) != exp:
        return None
    return data

def _load_tileset_rgb565(path, tile_size=16, atlas_w=64, atlas_h=64):
    try:
        with open(path, 'rb') as fp:
            data = fp.read()
    except Exception:
        return None
    exp = atlas_w * atlas_h * 2
    if data is None or len(data) != exp:
        return None
    cols = atlas_w // tile_size
    rows = atlas_h // tile_size
    tiles = [None]
    for tr in range(rows):
        for tc in range(cols):
            buf = bytearray(tile_size * tile_size * 2)
            di = 0
            for y in range(tile_size):
                sy = tr * tile_size + y
                so = ((sy * atlas_w) + (tc * tile_size)) * 2
                e = so + (tile_size * 2)
                seg = data[so:e]
                buf[di:di + (tile_size * 2)] = seg
                di += tile_size * 2
            tiles.append(bytes(buf))
    return tiles


def _extract_rgb565_region(atlas_buf, atlas_w, atlas_h, src_x, src_y, src_w, src_h):
    if atlas_buf is None:
        return None
    if src_x < 0 or src_y < 0 or src_w <= 0 or src_h <= 0:
        return None
    if (src_x + src_w) > atlas_w or (src_y + src_h) > atlas_h:
        return None
    out = bytearray(src_w * src_h * 2)
    di = 0
    row_bytes = atlas_w * 2
    copy_bytes = src_w * 2
    y = 0
    while y < src_h:
        so = ((src_y + y) * row_bytes) + (src_x * 2)
        out[di:di + copy_bytes] = atlas_buf[so:so + copy_bytes]
        di += copy_bytes
        y += 1
    return bytes(out)

def _blit_tile_to_scene(scene_buf, scene_w, scene_h, dx, dy, tile_buf, tile_size=16):
    if tile_buf is None:
        return
    sx0 = 0 if dx >= 0 else -dx
    sy0 = 0 if dy >= 0 else -dy
    sx1 = tile_size if (dx + tile_size) <= scene_w else (scene_w - dx)
    sy1 = tile_size if (dy + tile_size) <= scene_h else (scene_h - dy)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    copy_w = sx1 - sx0
    for y in range(sy0, sy1):
        src_off = ((y * tile_size) + sx0) * 2
        dst_y = dy + y
        dst_x = dx + sx0
        dst_off = ((dst_y * scene_w) + dst_x) * 2
        scene_buf[dst_off:dst_off + (copy_w * 2)] = tile_buf[src_off:src_off + (copy_w * 2)]

def _compose_tilemap_scene(scene_buf, scene_w, scene_h, camera_x, band_top, tile_rows, tileset, tile_size=16):
    if not tile_rows or not tileset:
        return
    map_h = len(tile_rows)
    map_w = len(tile_rows[0]) if map_h > 0 else 0
    if map_w <= 0:
        return
    start_col = camera_x // tile_size
    end_col = (camera_x + scene_w - 1) // tile_size
    start_row = band_top // tile_size
    end_row = (band_top + scene_h - 1) // tile_size
    if start_col < 0:
        start_col = 0
    if start_row < 0:
        start_row = 0
    if end_col >= map_w:
        end_col = map_w - 1
    if end_row >= map_h:
        end_row = map_h - 1
    for r in range(start_row, end_row + 1):
        row = tile_rows[r]
        for c in range(start_col, end_col + 1):
            tid = row[c]
            if tid <= 0 or tid >= len(tileset):
                continue
            dx = (c * tile_size) - camera_x
            dy = (r * tile_size) - band_top
            _blit_tile_to_scene(scene_buf, scene_w, scene_h, dx, dy, tileset[tid], tile_size)


def _tilemap_is_solid(tilemap_idx, tilemap_w, tilemap_h, tx, ty):
    if tx < 0 or ty < 0 or tx >= tilemap_w or ty >= tilemap_h:
        return False
    return tilemap_idx[(ty * tilemap_w) + tx] != 0


def _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, y, w, h):
    x0 = x
    y0 = y
    x1 = x + w - 1
    y1 = y + h - 1
    tx0 = x0 // tile_size
    ty0 = y0 // tile_size
    tx1 = x1 // tile_size
    ty1 = y1 // tile_size
    ty = ty0
    while ty <= ty1:
        tx = tx0
        while tx <= tx1:
            if _tilemap_is_solid(tilemap_idx, tilemap_w, tilemap_h, tx, ty):
                return True
            tx += 1
        ty += 1
    return False


def _move_axis_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, y, w, h, delta_x, delta_y):
    hit_x = 0
    hit_y = 0
    if delta_x != 0:
        step_x = 1 if delta_x > 0 else -1
        n = delta_x if delta_x > 0 else -delta_x
        i = 0
        while i < n:
            nx = x + step_x
            if _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, nx, y, w, h):
                hit_x = 1
                break
            x = nx
            i += 1
    if delta_y != 0:
        step_y = 1 if delta_y > 0 else -1
        n = delta_y if delta_y > 0 else -delta_y
        i = 0
        while i < n:
            ny = y + step_y
            if _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, ny, w, h):
                hit_y = 1
                break
            y = ny
            i += 1
    return x, y, hit_x, hit_y


def _snap_spawn_to_ground(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, y, w, h):
    map_h_px = tilemap_h * tile_size
    max_y = map_h_px - h
    if max_y < 0:
        max_y = 0
    if y < 0:
        y = 0
    if y > max_y:
        y = max_y

    guard = map_h_px + tile_size
    while guard > 0 and _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, y, w, h):
        if y <= 0:
            break
        y -= 1
        guard -= 1

    guard = map_h_px + tile_size
    while guard > 0:
        ny = y + 1
        if ny > max_y:
            break
        if _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, ny, w, h):
            break
        y = ny
        guard -= 1

    return y


def _normalize_mode(v):
    m = str(v).upper()
    if m == "MAP1_FULL_BULK":
        return _MODE_ROWS_SAFE_PROGRESSIVE
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
        _MODE_BLIT_WAIT_GRID_TEST,
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
        _MODE_BLIT_WAIT_GRID_TEST,
        _MODE_ROWS_SAFE_PROGRESSIVE,
        _MODE_ROWS_SAFE_NEAR_TILE_TEST,
        _MODE_FULL_BUFFER_TEST,
        _MODE_SPI_TFT_SPEED_TEST,
        _MODE_SPI_TFT_BULK_WAIT_TEST,
    )
    if mode == _MODE_BLIT_WAIT_GRID_TEST and not hasattr(_lgfx, "blit_rect565_wait"):
        raise RuntimeError("CAMERA_TEST_FAIL_NO_BLIT_WAIT")
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

    print("RUNTIME_APP_CAMERA_TEST_DEBUG_V2")
    print("APP_RUN_START_PHASE_CAMERA_TEST_V2")
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
    if mode == _MODE_BLIT_WAIT_GRID_TEST:
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
        if not hasattr(_lgfx, "blit_rect565_wait"):
            print("CAMERA_TEST_NEAR_FAIL_NO_BLIT_WAIT")
            raise RuntimeError("CAMERA_TEST_NEAR_FAIL_NO_BLIT_WAIT")

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
                _lgfx.blit_rect565_wait(0, y, sw, h, view)
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

            _lgfx.blit_rect565_wait(0, band_top, sw, scene_h, scene_buf)

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
        if not hasattr(_lgfx, "blit_rect565_wait"):
            print("SPI_TFT_FAIL_NO_WAIT_API")
            raise RuntimeError("SPI_TFT_FAIL_NO_WAIT_API")
        # Mainline lock: force full-screen bulk path only.
        path = "BULK_WAIT_DIRECT"

        if path in ("BULK_WAIT_DIRECT", "CHUNK_WAIT_DIRECT_16") and not hasattr(_lgfx, "blit_rect565_wait"):
            print("SPI_TFT_FAIL_NO_BULK_WAIT_API")
            raise RuntimeError("SPI_TFT_FAIL_NO_BULK_WAIT_API")
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
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
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
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                elif path == "CHUNK_WAIT_COPY_32":
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                elif path == "CHUNK_WAIT_COPY_COMPAT_1":
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                elif path == "CHUNK_WAIT_COPY_COMPAT_2":
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                elif path == "CHUNK_WAIT_COPY_COMPAT_4":
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                elif path == "CHUNK_WAIT_COPY_COMPAT_8":
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
                else:
                    _lgfx.blit_rect565_wait(0, 0, sw, sh, buf)
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
        if not hasattr(_lgfx, "blit_rect565_wait"):
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
            side = "left"
            while side in ("left", "right"):
                i = 0
                while i < 4:
                    sprite_wire_suffix = "_wire" if (bool(getattr(config, "CAMERA_FULL_BULK_WIRE_ORDER", False)) and not bool(getattr(config, "CAMERA_FULL_BULK_WIRE_RUNTIME_SWAP", True))) else ""
                    rgb_path = "/player_walk_%s_%d%s.rgb565" % (side, i, sprite_wire_suffix)
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
                _blend_sprite32_mask1_into_scene(
                    frame_buf,
                    sw,
                    sh,
                    sprite_x,
                    sprite_y,
                    spr_rgb,
                    spr_mask,
                )
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
                _lgfx.blit_rect565_wait(0, 0, sw, sh, frame_buf)
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

        if not hasattr(_lgfx, "blit_rect565_wait"):
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
            gravity = int(getattr(config, "PLAYER_GRAVITY", 1))
            if gravity < 0:
                gravity = 0
            fall_speed_max = int(getattr(config, "PLAYER_FALL_SPEED_MAX", 8))
            if fall_speed_max < 1:
                fall_speed_max = 1
            vel_y = 0

            object_gravity_enabled = bool(getattr(config, "OBJECT_GRAVITY_ENABLED", True))
            object_gravity_step = int(getattr(config, "OBJECT_GRAVITY_STEP", 2))
            if object_gravity_step < 0:
                object_gravity_step = 0
            if object_gravity_step > 8:
                object_gravity_step = 8
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

            # Keep the panel black until the first fully composed native-band frame.
            # Far background is loaded into RAM below, but no startup preview is submitted.

            ground_h = 16
            ground_y0 = sh - ground_h
            tilemap_mode_active = bool(getattr(config, "TILEMAP_ENABLED", False))
            sprite_logic_y = player_y
            if use_sprite_player and sprite_draw_mode == "COMPOSE":
                sprite_logic_y = player_y + draw_off_y
            band_top = player_y if player_y < sprite_logic_y else sprite_logic_y
            if band_top < 0:
                band_top = 0
            if band_top > ground_y0:
                band_top = ground_y0
            # Tilemap scene is sparse (index 0 means transparent), so keep full-screen compose.
            # A moving lower band would clip all tiles above the player.
            if tilemap_mode_active:
                band_top = 0
            # Allocate runtime compose buffer as early as possible to maximize contiguous heap.
            # COMPOSE may need a taller band for full 32x32 sprite; if allocation fails,
            # shrink band from top until allocation succeeds (still COMPOSE path).
            scene_buf = None
            scene_buf_back = None
            while True:
                # In tilemap mode we want far_bg as full backdrop, including bottom 16px.
                if tilemap_mode_active:
                    far_band_h = sh - band_top
                else:
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
            # Optional ping-pong buffer for async full-bulk submit.
            try:
                scene_buf_back = bytearray(sw * scene_h * 2)
            except Exception:
                scene_buf_back = None
            if use_sprite_player and sprite_draw_mode == "COMPOSE":
                print("CAMERA_COMPOSE_BAND_TOP=%d" % band_top)

            far_band_buf = None
            far_runtime_file = None
            # Prefer caching far background in RAM once at boot for smoother frame time.
            # Fallback to per-frame streaming only when allocation/load fails.
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
                print("CAMERA_FAR_BG_RAM_CACHE_READY")
            except Exception:
                far_band_buf = None
                far_runtime_file = open(far_raw, "rb")
                print("CAMERA_FAR_BG_STREAM_FALLBACK")

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
                print("CAMERA_PLAYER_SPRITE_TRANSPARENCY=COLORKEY")
                print("CAMERA_PLAYER_SPRITE_COMPOSE_IMPL=%s" % sprite_compose_impl)
            if use_sprite_player:
                sheet_path = str(getattr(config, "CAMERA_PLAYER_SPRITESHEET_PATH", "/player_wire.rgb565"))
                try:
                    with open(sheet_path, "rb") as sf:
                        sheet_rgb = sf.read()
                    sprite_right, sprite_left = _slice_player_spritesheet_frames(sheet_rgb, 128, sprite_w, sprite_h)
                except Exception:
                    print("CAMERA_TEST_STEP=4_FAIL_PLAYER_ASSET")
                    raise RuntimeError("CAMERA_TEST_STEP4_FAIL_PLAYER_ASSET")
                print("CAMERA_PLAYER_SPRITE_SOURCE=SHEET")
                print("CAMERA_PLAYER_SPRITE_READY=1")
            player_screen_x = player_x
            camera_x = 0
            frame = 0
            drew_once = False
            # Swap input stability: edge trigger + min interval + per-frame lock.
            swap_min_interval_ms = int(getattr(config, "SWAP_MIN_INTERVAL_MS", 90))
            if swap_min_interval_ms < 0:
                swap_min_interval_ms = 0
            last_x_down = False
            last_y_down = False
            last_swap_ms = -1000000
            prev_sprite_x = None
            prev_sprite_y = None
            last_tick = ticks_ms()
            perf_window_start = last_tick
            far_len = 0 if far_band_buf is None else len(far_band_buf)
            profile_every = int(getattr(config, "CAMERA_TEST_STEP4_PROFILE_EVERY", 60))
            if profile_every < 1:
                profile_every = 60
            stall_frame_us = int(getattr(config, "CAMERA_STALL_FRAME_US", 65000))
            if stall_frame_us < 1000:
                stall_frame_us = 65000
            stall_log_cooldown = int(getattr(config, "CAMERA_STALL_LOG_COOLDOWN", 15))
            if stall_log_cooldown < 1:
                stall_log_cooldown = 15
            stall_log_countdown = 0
            prof_update_us = 0
            prof_bg_us = 0
            prof_world_us = 0
            prof_sprite_us = 0
            prof_hud_us = 0
            prof_submit_us = 0
            prof_submit_wait_us = 0
            prof_submit_kick_us = 0
            prof_submit_swap_us = 0
            prof_total_us = 0
            prof_pace_us = 0
            partial_rect_experiment_disabled = False
            dirty_fallback_on_camera_move = True
            dirty_band_full_width = True
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
            tilemap_enabled = bool(getattr(config, "TILEMAP_ENABLED", True))
            tilemap_rows = None
            if tilemap_enabled:
                csv_path = _resolve_asset_path(getattr(config, "TILEMAP_CSV_PATH", "game/Tilemap/map1_tilemap.csv"))
                tilemap_rows = _load_tilemap_rows(csv_path)
                if tilemap_rows is None:
                    print("TILEMAP_CSV_LOAD_FAIL")
                    tilemap_rows = _parse_tilemap_csv(_TILEMAP_CSV)
            tilemap_idx = None
            tilemap_w = 0
            tilemap_h = 0
            tileset_raw = None
            tileset_cache = None
            tile_size = int(getattr(config, "TILE_SIZE", 16))
            tileset_w = int(getattr(config, "TILESET_ATLAS_W", 128))
            tileset_h = int(getattr(config, "TILESET_ATLAS_H", 128))
            tilemap_compose_impl = "PYTHON"
            if tilemap_enabled:
                tilemap_idx, tilemap_w, tilemap_h = _flatten_tilemap_rows(tilemap_rows)
                if tilemap_idx is not None and tilemap_w > 0 and tilemap_h > 0:
                    map_w = tilemap_w * tile_size
                    max_player_x = map_w - player_w
                    if max_player_x < 0:
                        max_player_x = 0
                    camera_max = map_w - sw
                    if camera_max < 0:
                        camera_max = 0
                    player_y = _snap_spawn_to_ground(tilemap_idx, tilemap_w, tilemap_h, tile_size, player_x, player_y, player_w, player_h)
                tileset_path = _resolve_asset_path(getattr(config, "TILESET_RGB565_PATH", "game/Tilemap/tilemap_all.rgb565"))
                tileset_raw = _load_tileset_raw_rgb565(tileset_path, tileset_w, tileset_h)
                if (
                    tileset_raw is not None
                    and tilemap_idx is not None
                    and hasattr(_lgfx, "compose_tilemap_rgb565")
                ):
                    tilemap_compose_impl = "C_API"
                else:
                    tileset_cache = _load_tileset_rgb565(tileset_path, tile_size, tileset_w, tileset_h)
                    if tileset_cache is None:
                        print("TILEMAP_TILESET_LOAD_FAIL")
                floor_layer_enabled = False
                print("TILEMAP_MODE_ON")
                print("TILEMAP_COMPOSE_IMPL=%s" % tilemap_compose_impl)

            objects_csv_path = _resolve_asset_path(getattr(config, "OBJECTS_CSV_PATH", "game/picture/object/objects.csv"))
            objects_atlas_path = _resolve_asset_path(getattr(config, "OBJECTS_ATLAS_RGB565_PATH", "game/picture/object/objects_atlas_wire.rgb565"))
            objects_atlas_w = int(getattr(config, "OBJECTS_ATLAS_W", 128))
            objects_atlas_h = int(getattr(config, "OBJECTS_ATLAS_H", 128))
            objects_compose_impl_cfg = str(getattr(config, "OBJECTS_COMPOSE_IMPL", "C_API")).upper()
            if objects_compose_impl_cfg not in ("C_API", "PYTHON"):
                objects_compose_impl_cfg = "C_API"
            objects_rows, objects_meta = _load_objects_rows_and_meta(objects_csv_path)
            objects_rows_initial = _clone_object_rows(objects_rows)
            objects_atlas = _load_rgb565_blob(objects_atlas_path, objects_atlas_w * objects_atlas_h * 2)
            object_animations_path = _resolve_asset_path(
                getattr(config, "OBJECT_ANIMATIONS_JSON_PATH", "game/picture/object/object_animations.json")
            )
            object_animations = _load_object_animations(object_animations_path)
            special_object_render_enabled = True if object_animations else False
            objects_c_buf = bytearray()
            objects_c_stride = 12
            objects_c_count = 0
            object_solids = []
            object_solids_c_buf = bytearray()
            object_solids_c_stride = _OBJECT_SOLID_STRIDE
            object_solids_c_count = 0
            if objects_rows and objects_atlas is not None:
                object_solids = _rebuild_object_solids(objects_rows)
                object_solids_c_buf, object_solids_c_stride, object_solids_c_count = _pack_object_solids_for_c(object_solids)
                objects_c_buf, objects_c_stride, objects_c_count = _pack_objects_for_c(objects_rows, objects_meta)
                print("OBJECT_MODE_ON")
                print("OBJECT_COUNT=%d" % len(objects_rows))
                print("OBJECT_C_COUNT=%d" % objects_c_count)
                print("OBJECT_COMPOSE_IMPL_CFG=%s" % objects_compose_impl_cfg)
                print("OBJECT_SOLID_COUNT=%d" % len(object_solids))
            else:
                objects_rows = []
                objects_meta = []
                objects_atlas = None
                object_solids_c_buf = bytearray()
                object_solids_c_stride = _OBJECT_SOLID_STRIDE
                object_solids_c_count = 0
                print("OBJECT_MODE_OFF")
            enemy_csv_path = _resolve_asset_path(getattr(config, "ENEMY_CSV_PATH", "game/picture/enemy/enemies.csv"))
            enemy_sheet_path = _resolve_asset_path(
                getattr(config, "ENEMY_SHEET_RGB565_PATH", "game/picture/enemy/enemy_bow_animation_wire.rgb565")
            )
            enemy_sheet_w = int(getattr(config, "ENEMY_SHEET_W", 320))
            enemy_sheet_h = int(getattr(config, "ENEMY_SHEET_H", 96))
            enemy_frame_w = int(getattr(config, "ENEMY_FRAME_W", 32))
            enemy_frame_h = int(getattr(config, "ENEMY_FRAME_H", 32))
            enemy_frame_hold = int(getattr(config, "ENEMY_FRAME_HOLD", 4))
            if enemy_frame_hold < 1:
                enemy_frame_hold = 4
            enemy_detect_x = int(getattr(config, "ENEMY_DETECT_RANGE_X", 160))
            enemy_flee_x = int(getattr(config, "ENEMY_FLEE_RANGE_X", 80))
            enemy_detect_y = int(getattr(config, "ENEMY_DETECT_RANGE_Y", 24))
            enemy_move_speed = int(getattr(config, "ENEMY_MOVE_SPEED", 1))
            if enemy_move_speed < 1:
                enemy_move_speed = 1
            enemy_gravity_step = int(getattr(config, "ENEMY_GRAVITY_STEP", 2))
            if enemy_gravity_step < 1:
                enemy_gravity_step = 1
            enemy_shoot_interval = int(getattr(config, "ENEMY_SHOOT_INTERVAL", 45))
            if enemy_shoot_interval < 1:
                enemy_shoot_interval = 45
            enemy_shoot_fire_frame = int(getattr(config, "ENEMY_SHOOT_FIRE_FRAME", 4))
            if enemy_shoot_fire_frame < 0:
                enemy_shoot_fire_frame = 4
            enemy_bullet_w = int(getattr(config, "ENEMY_BULLET_W", 6))
            enemy_bullet_h = int(getattr(config, "ENEMY_BULLET_H", 6))
            enemy_bullet_speed = int(getattr(config, "ENEMY_BULLET_SPEED", 3))
            if enemy_bullet_speed < 1:
                enemy_bullet_speed = 1
            enemy_max_bullets = int(getattr(config, "ENEMY_MAX_BULLETS", 4))
            if enemy_max_bullets < 1:
                enemy_max_bullets = 4
            enemy_update_margin_x = int(getattr(config, "ENEMY_UPDATE_MARGIN_X", 160))
            if enemy_update_margin_x < 0:
                enemy_update_margin_x = 0
            enemy_update_margin_y = int(getattr(config, "ENEMY_UPDATE_MARGIN_Y", 80))
            if enemy_update_margin_y < 0:
                enemy_update_margin_y = 0
            enemy_render_margin_x = int(getattr(config, "ENEMY_RENDER_MARGIN_X", 48))
            if enemy_render_margin_x < 0:
                enemy_render_margin_x = 0
            enemy_render_margin_y = int(getattr(config, "ENEMY_RENDER_MARGIN_Y", 32))
            if enemy_render_margin_y < 0:
                enemy_render_margin_y = 0
            enemy_bullet_cull_margin = int(getattr(config, "ENEMY_BULLET_CULL_MARGIN", 32))
            if enemy_bullet_cull_margin < 0:
                enemy_bullet_cull_margin = 0
            enemy_bullet_color = int(getattr(config, "COLOR_BULLET", 0xFFFF)) & 0xFFFF
            enemy_rows, enemy_meta = _load_enemies_rows_and_meta(enemy_csv_path)
            enemy_rows_initial = _clone_enemy_rows(enemy_rows)
            enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows_c_count = _pack_enemy_rows_for_c(enemy_rows, enemy_meta)
            enemy_states = _build_enemy_states(enemy_meta)
            enemy_sheet = None
            if enemy_sheet_w > 0 and enemy_sheet_h > 0:
                enemy_sheet = _load_rgb565_blob(enemy_sheet_path, enemy_sheet_w * enemy_sheet_h * 2)
            enemy_bullets = _PackedEnemyBullets()
            enemy_bullets.ensure_capacity(enemy_max_bullets)
            enemy_update_native_ready = bool(_lgfx is not None and hasattr(_lgfx, 'update_enemies_native'))
            enemy_render_enabled = bool(
                enemy_rows and enemy_states and enemy_sheet is not None and enemy_frame_w > 0 and enemy_frame_h > 0
            )
            if enemy_rows:
                print("ENEMY_MODE_ON")
                print("ENEMY_COUNT=%d" % len(enemy_rows))
                print("ENEMY_RENDER_READY=%d" % (1 if enemy_render_enabled else 0))
                print("ENEMY_UPDATE_IMPL=%s" % ("C_API" if enemy_update_native_ready else "PYTHON"))
            else:
                print("ENEMY_MODE_OFF")
            checkpoint_index = -1
            anchor_active = False
            anchor_x = 0
            anchor_y = 0
            object_anim_counter = 0
            anchor_anim_counter = 0
            death_state = 0
            death_camera_target_x = 0
            death_margin = int(getattr(config, "RESPAWN_DEATH_MARGIN", 48))
            if death_margin < 0:
                death_margin = 48
            camera_pan_step = int(getattr(config, "RESPAWN_CAMERA_PAN_STEP", 12))
            if camera_pan_step < 1:
                camera_pan_step = 12
            anchor_offset_y = int(getattr(config, "RESPAWN_ANCHOR_OFFSET_Y", 32))
            anchor_anim_id = str(getattr(config, "RESPAWN_ANCHOR_ANIM_ID", "resurrection_anchor"))
            anchor_anim_spec = object_animations.get(anchor_anim_id)
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
                        and False
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
            if partial_rect_experiment_disabled:
                print("PARTIAL_RECT_EXPERIMENT_DISABLED")

            submit_async_cfg = bool(getattr(config, "CAMERA_FULL_BULK_DOUBLE_BUFFER", True))
            submit_wire_order_cfg = bool(getattr(config, "CAMERA_FULL_BULK_WIRE_ORDER", False))
            submit_wire_runtime_swap = False
            has_async_api = hasattr(_lgfx, "blit_rect565_async") and hasattr(_lgfx, "blit_wait_done")
            has_wire_api = (
                hasattr(_lgfx, "blit_rect565_wire_async")
                and hasattr(_lgfx, "blit_rect565_wire_wait")
                and hasattr(_lgfx, "blit_wait_done")
            )
            submit_wire_order = submit_wire_order_cfg and has_wire_api
            submit_async_fn = _lgfx.blit_rect565_wire_async if submit_wire_order else _lgfx.blit_rect565_async
            submit_wait_fn = _lgfx.blit_rect565_wire_wait if submit_wire_order else _lgfx.blit_rect565_wait
            submit_async_enabled = (
                submit_async_cfg
                and scene_buf_back is not None
                and (has_wire_api if submit_wire_order_cfg else has_async_api)
            )
            submit_async_inflight = False
            submit_inflight_buf = None
            if submit_wire_order:
                print("SUBMIT_BYTE_ORDER=WIRE_NOSWAP")
                print("SUBMIT_WIRE_RUNTIME_SWAP=%d" % (1 if submit_wire_runtime_swap else 0))
            else:
                print("SUBMIT_BYTE_ORDER=RGB565_LE_SWAP")
                if submit_wire_order_cfg and not has_wire_api:
                    print("SUBMIT_FALLBACK_REASON=NO_WIRE_API")
            if submit_async_enabled:
                print("SUBMIT_MODE=ASYNC_DOUBLE_BUFFER_MAINLINE")
            else:
                print("SUBMIT_MODE=SYNC_SINGLE_BUFFER_FALLBACK")
                if submit_async_cfg and scene_buf_back is None:
                    print("SUBMIT_FALLBACK_REASON=NO_BACK_BUFFER")
                elif submit_async_cfg and submit_wire_order_cfg and not has_wire_api:
                    print("SUBMIT_FALLBACK_REASON=NO_WIRE_API")
                elif submit_async_cfg and not has_async_api:
                    print("SUBMIT_FALLBACK_REASON=NO_ASYNC_API")
                elif not submit_async_cfg:
                    print("SUBMIT_FALLBACK_REASON=CFG_OFF")

            enemy_bullet_src_x = int(getattr(config, "ENEMY_BULLET_SRC_X", 240))
            enemy_bullet_src_y_right = int(getattr(config, "ENEMY_BULLET_SRC_Y_RIGHT", 0))
            enemy_bullet_src_y_left = int(getattr(config, "ENEMY_BULLET_SRC_Y_LEFT", enemy_bullet_h))
            enemy_bullet_sprite_right = None
            enemy_bullet_sprite_left = None
            enemy_bullet_native_sprite_right = None
            enemy_bullet_native_sprite_left = None
            if enemy_bullet_w > 0 and enemy_bullet_h > 0 and objects_atlas is not None:
                enemy_bullet_sprite_right = _extract_rgb565_region(
                    objects_atlas,
                    objects_atlas_w,
                    objects_atlas_h,
                    enemy_bullet_src_x,
                    enemy_bullet_src_y_right,
                    enemy_bullet_w,
                    enemy_bullet_h,
                )
                enemy_bullet_sprite_left = _extract_rgb565_region(
                    objects_atlas,
                    objects_atlas_w,
                    objects_atlas_h,
                    enemy_bullet_src_x,
                    enemy_bullet_src_y_left,
                    enemy_bullet_w,
                    enemy_bullet_h,
                )
            if enemy_bullet_sprite_right is None and enemy_bullet_w > 0 and enemy_bullet_h > 0:
                enemy_bullet_sprite_right = _make_solid_sprite_rgb565(
                    enemy_bullet_w,
                    enemy_bullet_h,
                    enemy_bullet_color,
                    submit_wire_order and (not submit_wire_runtime_swap),
                )
            if enemy_bullet_sprite_left is None:
                enemy_bullet_sprite_left = enemy_bullet_sprite_right
            if enemy_bullet_w > 0 and enemy_bullet_h > 0:
                enemy_bullet_native_sprite_right = enemy_bullet_sprite_right
                enemy_bullet_native_sprite_left = enemy_bullet_sprite_left
                native_bullet_key = _swap16(int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
                native_bullet_fill = int(enemy_bullet_color) & 0xFFFF
                if submit_wire_order and (not submit_wire_runtime_swap):
                    native_bullet_fill = _swap16(native_bullet_fill)
                enemy_bullet_native_sprite_right = _lift_black_pixels_rgb565(
                    enemy_bullet_native_sprite_right,
                    native_bullet_key,
                    native_bullet_fill,
                )
                enemy_bullet_native_sprite_left = _lift_black_pixels_rgb565(
                    enemy_bullet_native_sprite_left,
                    native_bullet_key,
                    native_bullet_fill,
                )
                if enemy_bullet_native_sprite_right is None:
                    enemy_bullet_native_sprite_right = _make_solid_sprite_rgb565(
                        enemy_bullet_w,
                        enemy_bullet_h,
                        enemy_bullet_color,
                        submit_wire_order and (not submit_wire_runtime_swap),
                    )
                if enemy_bullet_native_sprite_left is None:
                    enemy_bullet_native_sprite_left = enemy_bullet_native_sprite_right

            native_band_h = int(getattr(config, "CAMERA_BAND_PIPELINE_H", 60))
            if native_band_h < 1:
                native_band_h = 60
            if native_band_h > sh:
                native_band_h = sh
            native_band_pipeline_enabled = (
                bool(getattr(config, "CAMERA_BAND_PIPELINE_NATIVE", False))
                and submit_wire_order
                and not submit_wire_runtime_swap
                and hasattr(_lgfx, "render_scene_bands_rgb565")
                and far_band_buf is not None
                and tilemap_idx is not None
                and tileset_raw is not None
                and objects_atlas is not None
                and use_sprite_player
                and scene_buf_back is not None
            )
            if native_band_pipeline_enabled:
                submit_async_enabled = False
                submit_async_inflight = False
                print("SUBMIT_MODE=NATIVE_BAND_PIPELINE")
                print("BAND_PIPELINE_NATIVE_ON h=%d" % native_band_h)
            elif bool(getattr(config, "CAMERA_BAND_PIPELINE_NATIVE", False)):
                print("BAND_PIPELINE_NATIVE_FALLBACK")

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
                object_anim_counter += 1
                if anchor_active:
                    anchor_anim_counter += 1

                if submit_async_enabled and submit_async_inflight:
                    wait_t0 = ticks_us()
                    try:
                        _lgfx.blit_wait_done()
                    except Exception:
                        submit_async_enabled = False
                        submit_async_inflight = False
                        submit_inflight_buf = None
                        print("SUBMIT_FALLBACK_REASON=WAIT_FAIL")
                    else:
                        w_us = ticks_diff(ticks_us(), wait_t0)
                        prof_submit_wait_us += w_us
                        submit_async_inflight = False
                        submit_inflight_buf = None

                seg_t0 = ticks_us()
                input_system.update(now)
                input_lr = int(getattr(input_system, "joy_x_axis", 0))
                move_x = 0
                if input_lr > 20:
                    move_x = speed
                    facing = 1
                elif input_lr < -20:
                    move_x = -speed
                    facing = -1

                # User-mapped keys: B=far swap, Y=near swap.
                # Stable trigger: edge only + minimum interval.
                b_pressed = bool(getattr(input_system, "btn_b_pressed", False))
                x_pressed = bool(getattr(input_system, "btn_x_pressed", False))
                y_pressed = bool(getattr(input_system, "btn_y_pressed", False))
                x_now = b_pressed
                y_now = y_pressed
                x_edge = x_now and (not last_x_down)
                y_edge = y_now and (not last_y_down)
                last_x_down = x_now
                last_y_down = y_now

                if b_pressed or x_pressed or y_pressed:
                    print("SWAP_BTN_DBG b=%d x=%d y=%d x_edge=%d y_edge=%d" % (
                        1 if b_pressed else 0,
                        1 if x_pressed else 0,
                        1 if y_pressed else 0,
                        1 if x_edge else 0,
                        1 if y_edge else 0,
                    ))

                swap_pick_far = False
                swap_triggered = False
                if x_edge:
                    swap_pick_far = True
                    swap_triggered = True
                elif y_edge:
                    swap_pick_far = False
                    swap_triggered = True

                if swap_triggered:
                    print("SWAP_TRIGGER_DBG far=%d" % (1 if swap_pick_far else 0))
                    if ticks_diff(now, last_swap_ms) < swap_min_interval_ms:
                        swap_triggered = False
                    else:
                        last_swap_ms = now

                map_h_px = tilemap_h * tile_size if (tilemap_enabled and tilemap_h > 0) else sh
                if map_h_px < sh:
                    map_h_px = sh
                map_w_px = tilemap_w * tile_size if (tilemap_enabled and tilemap_w > 0) else sw
                if map_w_px < sw:
                    map_w_px = sw

                if object_gravity_enabled and object_gravity_step > 0 and objects_rows and tilemap_enabled and tilemap_idx is not None and tilemap_w > 0 and tilemap_h > 0:
                    obj_moved = False
                    oi = 0
                    while oi < len(objects_rows):
                        row = objects_rows[oi]
                        meta = objects_meta[oi] if oi < len(objects_meta) else None
                        wx, wy, ow, oh, _solid, _layer, visible, _swappable, sx, sy, sw0, sh0 = row
                        if visible and ow > 0 and oh > 0:
                            steps = object_gravity_step
                            moved_y = 0
                            object_removed = False
                            while steps > 0:
                                ny = int(wy) + 1
                                if _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, int(wx), ny, int(ow), int(oh)):
                                    break
                                wy = ny
                                moved_y += 1
                                if int(wy) > (map_h_px + death_margin):
                                    object_removed = True
                                    break
                                steps -= 1
                            if object_removed:
                                row[1] = int(wy)
                                row[6] = 0
                                _repack_single_object_entry(objects_c_buf, objects_c_stride, oi, row[0], row[1], 0, 0, 0, 0, meta)
                                obj_moved = True
                            elif moved_y > 0:
                                row[1] = int(wy)
                                _repack_single_object_entry(objects_c_buf, objects_c_stride, oi, row[0], row[1], row[8], row[9], row[10], row[11], meta)
                                obj_moved = True
                        oi += 1
                    if obj_moved:
                        object_solids = _rebuild_object_solids(objects_rows)
                        object_solids_c_count = _sync_object_solids_c_from_list(object_solids_c_buf, object_solids_c_stride, object_solids)
                if death_state == 0:
                    enemy_update_out = _update_enemies_and_bullets_native(
                        enemy_rows,
                        enemy_meta,
                        enemy_states,
                        enemy_bullets,
                        enemy_rows_c_buf,
                        enemy_rows_c_stride,
                        enemy_rows_c_count,
                        object_solids_c_buf,
                        object_solids_c_stride,
                        object_solids_c_count,
                        player_x,
                        player_y,
                        player_w,
                        player_h,
                        vel_y,
                        tilemap_idx,
                        tilemap_w,
                        tilemap_h,
                        tile_size,
                        death_margin,
                        enemy_detect_x,
                        enemy_flee_x,
                        enemy_detect_y,
                        enemy_move_speed,
                        enemy_gravity_step,
                        enemy_frame_hold,
                        enemy_shoot_fire_frame,
                        enemy_bullet_speed,
                        enemy_bullet_w,
                        enemy_bullet_h,
                        enemy_shoot_interval,
                        fall_speed_max,
                        map_w_px,
                        map_h_px,
                        camera_x,
                        sw,
                        sh,
                        enemy_update_margin_x,
                        enemy_update_margin_y,
                        enemy_bullet_cull_margin,
                    )
                    if enemy_update_out is None:
                        player_y, vel_y = _update_enemies_and_bullets(
                            enemy_rows,
                            enemy_meta,
                            enemy_states,
                            enemy_bullets,
                            player_x,
                            player_y,
                            player_w,
                            player_h,
                            vel_y,
                            tilemap_idx,
                            tilemap_w,
                            tilemap_h,
                            tile_size,
                            object_solids,
                            death_margin,
                            enemy_detect_x,
                            enemy_flee_x,
                            enemy_detect_y,
                            enemy_move_speed,
                            enemy_gravity_step,
                            enemy_frame_hold,
                            enemy_shoot_fire_frame,
                            enemy_bullet_speed,
                            enemy_bullet_w,
                            enemy_bullet_h,
                            enemy_max_bullets,
                            enemy_shoot_interval,
                            fall_speed_max,
                            map_w_px,
                            map_h_px,
                            camera_x,
                            sw,
                            sh,
                            enemy_update_margin_x,
                            enemy_update_margin_y,
                            enemy_bullet_cull_margin,
                        )
                        _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
                    else:
                        player_y, vel_y = enemy_update_out

                    player_x, player_y, vel_y, object_solids = _perform_world_swap(
                        swap_triggered,
                        swap_pick_far,
                        objects_rows,
                        objects_meta,
                        enemy_rows,
                        enemy_states,
                        enemy_bullets,
                        player_x,
                        player_y,
                        player_w,
                        player_h,
                        camera_x,
                        band_top,
                        sw,
                        scene_h,
                        max_player_x,
                        map_h_px,
                        vel_y,
                        objects_c_buf,
                        objects_c_stride,
                    )
                    if swap_triggered:
                        _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
                        object_solids_c_count = _sync_object_solids_c_from_list(object_solids_c_buf, object_solids_c_stride, object_solids)

                    if tilemap_enabled or object_solids:
                        unembed_guard = tile_size * 4
                        if unembed_guard < 16:
                            unembed_guard = 16
                        while unembed_guard > 0 and _aabb_collides_world(player_x, player_y, player_w, player_h, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
                            player_y -= 1
                            if player_y < 0:
                                player_y = 0
                                break
                            unembed_guard -= 1

                        grounded = _aabb_collides_world(player_x, player_y + 1, player_w, player_h, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids)
                        if not grounded:
                            vel_y += gravity
                            if vel_y > fall_speed_max:
                                vel_y = fall_speed_max
                        elif vel_y > 0:
                            vel_y = 0

                        player_x, player_y, _hit_x, hit_y = _move_axis_world(
                            tilemap_idx,
                            tilemap_w,
                            tilemap_h,
                            tile_size,
                            object_solids,
                            player_x,
                            player_y,
                            player_w,
                            player_h,
                            move_x,
                            vel_y,
                        )
                        if hit_y:
                            vel_y = 0
                        if player_x < 0:
                            player_x = 0
                        if player_x > max_player_x:
                            player_x = max_player_x
                        if player_y < 0:
                            player_y = 0
                            vel_y = 0
                    else:
                        player_x += move_x
                        player_x = _clamp(player_x, 0, max_player_x)

                    oi = 0
                    while oi < len(objects_rows):
                        meta = objects_meta[oi] if oi < len(objects_meta) else None
                        if meta and meta.get("checkpoint"):
                            row = objects_rows[oi]
                            wx, wy, ow, oh, _solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = row
                            if visible and player_x < (wx + ow) and (player_x + player_w) > wx and player_y < (wy + oh) and (player_y + player_h) > wy:
                                if checkpoint_index != oi:
                                    checkpoint_index = oi
                                    print("CHECKPOINT_TOUCH idx=%d id=%s x=%d y=%d" % (oi, meta.get("id", ""), wx, wy))
                                break
                        oi += 1

                    if player_y > (map_h_px + death_margin):
                        if checkpoint_index < 0:
                            oi = 0
                            while oi < len(objects_rows):
                                meta = objects_meta[oi] if oi < len(objects_meta) else None
                                row = objects_rows[oi]
                                if meta and meta.get("checkpoint") and row[6]:
                                    checkpoint_index = oi
                                    break
                                oi += 1
                        death_state = 1
                        anchor_active = False
                        vel_y = 0
                        if checkpoint_index >= 0 and checkpoint_index < len(objects_rows):
                            row = objects_rows[checkpoint_index]
                            death_camera_target_x = _clamp(int(row[0]) + (int(row[2]) // 2) - screen_half, 0, camera_max)
                        else:
                            death_camera_target_x = 0
                        print("PLAYER_DEAD_WAIT_RESPAWN checkpoint=%d camera_target=%d" % (checkpoint_index, death_camera_target_x))

                    if death_state == 0:
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
                    else:
                        moving = 0
                        anim_counter = 0
                        anim_idx = 0
                else:
                    moving = 0
                    anim_counter = 0
                    anim_idx = 0
                    if death_state == 1:
                        if camera_x < death_camera_target_x:
                            camera_x += camera_pan_step
                            if camera_x > death_camera_target_x:
                                camera_x = death_camera_target_x
                        elif camera_x > death_camera_target_x:
                            camera_x -= camera_pan_step
                            if camera_x < death_camera_target_x:
                                camera_x = death_camera_target_x
                        if camera_x == death_camera_target_x:
                            death_state = 2
                            if checkpoint_index >= 0 and checkpoint_index < len(objects_rows):
                                row = objects_rows[checkpoint_index]
                                anchor_w = 32
                                anchor_h = 32
                                if anchor_anim_spec is not None:
                                    anchor_w = int(anchor_anim_spec.get("frame_w", 32) or 32)
                                    anchor_h = int(anchor_anim_spec.get("frame_h", 32) or 32)
                                anchor_x = int(row[0]) + ((int(row[2]) - anchor_w) // 2)
                                anchor_y = int(row[1]) - anchor_offset_y
                                if anchor_y < 0:
                                    anchor_y = 0
                                anchor_active = True
                                anchor_anim_counter = 0
                                print("RESPAWN_ANCHOR_READY idx=%d x=%d y=%d" % (checkpoint_index, anchor_x, anchor_y))
                    elif death_state == 2:
                        camera_x = death_camera_target_x
                        if anchor_active and (x_edge or y_edge):
                            anchor_w = 32
                            anchor_h = 32
                            if anchor_anim_spec is not None:
                                anchor_w = int(anchor_anim_spec.get("frame_w", 32) or 32)
                                anchor_h = int(anchor_anim_spec.get("frame_h", 32) or 32)
                            player_x = anchor_x + ((anchor_w - player_w) // 2)
                            player_y = anchor_y + (anchor_h - player_h)
                            player_x = _clamp(player_x, 0, max_player_x)
                            vel_y = 0
                            anchor_active = False
                            anchor_anim_counter = 0
                            _restore_objects_rows(
                                objects_rows,
                                objects_rows_initial,
                                objects_c_buf,
                                objects_c_stride,
                                objects_meta,
                            )
                            _restore_enemy_rows(enemy_rows, enemy_rows_initial, enemy_states, enemy_meta)
                            _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
                            _clear_enemy_bullets(enemy_bullets)
                            if hasattr(enemy_bullets, "ensure_capacity"):
                                enemy_bullets.ensure_capacity(enemy_max_bullets)
                            object_solids = _rebuild_object_solids(objects_rows)
                            object_solids_c_count = _sync_object_solids_c_from_list(object_solids_c_buf, object_solids_c_stride, object_solids)
                            death_state = 0
                            player_center_x = player_x + (player_w // 2)
                            target_camera_x = player_center_x - screen_half
                            camera_x = _clamp(target_camera_x, 0, camera_max)
                            player_screen_x = player_x - camera_x
                            print("PLAYER_RESPAWN_OK x=%d y=%d" % (player_x, player_y))
                    player_screen_x = -4096

                prof_update_us += ticks_diff(ticks_us(), seg_t0)

                frame_native_band_enabled = native_band_pipeline_enabled

                if frame_native_band_enabled:
                    submit_t0 = ticks_us()
                    sprite_x = player_screen_x + draw_off_x
                    sprite_y = player_y + draw_off_y
                    spr_x = sprite_x
                    spr_y = sprite_y - band_top
                    if facing < 0:
                        spr_rgb = sprite_left[anim_idx]
                    else:
                        spr_rgb = sprite_right[anim_idx]
                    player_colorkey_raw = _swap16(int(getattr(config, "CAMERA_PLAYER_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
                    transparent_key = _swap16(0xF81F)
                    object_colorkey = -1
                    if bool(getattr(config, "CAMERA_OBJECT_COLORKEY_ENABLE", True)):
                        object_colorkey = _swap16(int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
                    overlay_desc_buf, overlay_stride, overlay_count, overlay_frames = _pack_special_render_overlays(
                        objects_rows,
                        objects_meta,
                        object_animations,
                        object_anim_counter,
                        anchor_active,
                        anchor_x,
                        anchor_y,
                        anchor_anim_spec,
                        anchor_anim_counter,
                        enemy_bullets,
                        enemy_bullet_native_sprite_right,
                        enemy_bullet_native_sprite_left,
                        enemy_bullet_w,
                        enemy_bullet_h,
                        camera_x,
                        sw,
                        sh,
                        enemy_bullet_cull_margin,
                    )
                    enemy_desc_buf, enemy_desc_stride, enemy_desc_count = _pack_enemy_render_descriptors(
                        enemy_rows,
                        enemy_states,
                        camera_x,
                        sw,
                        sh,
                        enemy_render_margin_x,
                        enemy_render_margin_y,
                    )
                    try:
                        if enemy_render_enabled:
                            band_res = _lgfx.render_scene_bands_rgb565(
                                scene_buf,
                                scene_buf_back,
                                sw,
                                sh,
                                native_band_h,
                                far_band_buf,
                                camera_x,
                                tilemap_idx,
                                tilemap_w,
                                tilemap_h,
                                tileset_raw,
                                tile_size,
                                tileset_w,
                                transparent_key,
                                objects_c_buf,
                                objects_c_stride,
                                objects_atlas,
                                objects_atlas_w,
                                objects_atlas_h,
                                object_colorkey,
                                objects_c_count,
                                spr_rgb,
                                sprite_w,
                                sprite_h,
                                spr_x,
                                sprite_y,
                                player_colorkey_raw,
                                overlay_desc_buf,
                                overlay_stride,
                                overlay_count,
                                overlay_frames,
                                object_colorkey,
                                enemy_desc_buf,
                                enemy_desc_stride,
                                enemy_desc_count,
                                enemy_sheet,
                                enemy_sheet_w,
                                enemy_sheet_h,
                                object_colorkey,
                                enemy_frame_hold,
                                False,
                            )
                        else:
                            band_res = _lgfx.render_scene_bands_rgb565(
                                scene_buf,
                                scene_buf_back,
                                sw,
                                sh,
                                native_band_h,
                                far_band_buf,
                                camera_x,
                                tilemap_idx,
                                tilemap_w,
                                tilemap_h,
                                tileset_raw,
                                tile_size,
                                tileset_w,
                                transparent_key,
                                objects_c_buf,
                                objects_c_stride,
                                objects_atlas,
                                objects_atlas_w,
                                objects_atlas_h,
                                object_colorkey,
                                objects_c_count,
                                spr_rgb,
                                sprite_w,
                                sprite_h,
                                spr_x,
                                sprite_y,
                                player_colorkey_raw,
                                overlay_desc_buf,
                                overlay_stride,
                                overlay_count,
                                overlay_frames,
                                object_colorkey,
                                False,
                            )
                    except Exception as exc:
                        native_band_pipeline_enabled = False
                        print("BAND_PIPELINE_NATIVE_FAIL")
                        raise
                    us = ticks_diff(ticks_us(), submit_t0)
                    band_count = int(band_res[0])
                    band_compose_us = int(band_res[1])
                    kick_us = int(band_res[2])
                    wait_us = int(band_res[3])
                    swap_us = 0
                    submit_acc += us
                    prof_submit_us += us
                    prof_submit_wait_us += wait_us
                    prof_submit_kick_us += kick_us
                    prof_submit_swap_us += swap_us
                    dirty_last_rects_count = band_count
                    dirty_last_bands_count = band_count
                    dirty_last_camera_static = 1 if camera_x == prev_camera_x else 0
                    if dirty_log_countdown <= 0:
                        print("BAND_PIPELINE_SUBMIT_OK")
                        dirty_log_countdown = 30
                    if dirty_log_countdown > 0:
                        dirty_log_countdown -= 1
                else:
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
                            _lgfx.compose_colorkey_rgb565(
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
                        if tilemap_enabled:
                            if tilemap_compose_impl == "C_API" and tilemap_idx is not None and tileset_raw is not None:
                                transparent_key = 0xF81F
                                if submit_wire_order and not submit_wire_runtime_swap:
                                    transparent_key = _swap16(transparent_key)
                                _lgfx.compose_tilemap_rgb565(
                                    scene_buf,
                                    sw,
                                    scene_h,
                                    camera_x,
                                    band_top,
                                    tilemap_idx,
                                    tilemap_w,
                                    tilemap_h,
                                    tileset_raw,
                                    tile_size,
                                    tileset_w,
                                    transparent_key,
                                )
                            elif tilemap_rows is not None and tileset_cache is not None:
                                _compose_tilemap_scene(scene_buf, sw, scene_h, camera_x, band_top, tilemap_rows, tileset_cache, tile_size)
                            else:
                                pass
                        else:
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
                    if objects_rows and objects_atlas is not None:
                        object_colorkey_enable = bool(getattr(config, "CAMERA_OBJECT_COLORKEY_ENABLE", True))
                        object_colorkey = -1
                        if object_colorkey_enable:
                            object_colorkey = int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF
                            if submit_wire_order and not submit_wire_runtime_swap:
                                object_colorkey = _swap16(object_colorkey)
                        if (
                            objects_compose_impl_cfg == "C_API"
                            and hasattr(_lgfx, "compose_objects_atlas_rgb565")
                            and objects_c_count > 0
                        ):
                            _lgfx.compose_objects_atlas_rgb565(
                                scene_buf,
                                sw,
                                scene_h,
                                camera_x,
                                band_top,
                                objects_c_buf,
                                objects_c_stride,
                                objects_atlas,
                                objects_atlas_w,
                                objects_atlas_h,
                                object_colorkey,
                                objects_c_count,
                            )
                        else:
                            obj_key_b0 = object_colorkey & 0xFF
                            obj_key_b1 = (object_colorkey >> 8) & 0xFF
                            oi = 0
                            while oi < len(objects_rows):
                                wx, wy, _ow, _oh, _solid, _layer, visible, _swappable, sx, sy, sw0, sh0 = objects_rows[oi]
                                if visible:
                                    dx = int(wx) - camera_x
                                    dy = int(wy) - band_top
                                    _blit_atlas_region_colorkey_into_scene(
                                        scene_buf,
                                        sw,
                                        scene_h,
                                        dx,
                                        dy,
                                        objects_atlas,
                                        objects_atlas_w,
                                        objects_atlas_h,
                                        sx,
                                        sy,
                                        sw0,
                                        sh0,
                                        obj_key_b0,
                                        obj_key_b1,
                                    )
                                oi += 1

                    if special_object_render_enabled:
                        _render_special_objects_into_scene(
                            scene_buf,
                            sw,
                            scene_h,
                            camera_x,
                            band_top,
                            objects_rows,
                            objects_meta,
                            object_animations,
                            object_anim_counter,
                            submit_wire_order,
                            submit_wire_runtime_swap,
                        )
                        _render_anchor_into_scene(
                            scene_buf,
                            sw,
                            scene_h,
                            camera_x,
                            band_top,
                            anchor_active,
                            anchor_x,
                            anchor_y,
                            anchor_anim_spec,
                            anchor_anim_counter,
                            submit_wire_order,
                            submit_wire_runtime_swap,
                        )
                    if enemy_render_enabled:
                        _render_enemies_into_scene(
                            scene_buf,
                            sw,
                            scene_h,
                            camera_x,
                            band_top,
                            enemy_rows,
                            enemy_states,
                            enemy_sheet,
                            enemy_sheet_w,
                            enemy_sheet_h,
                            enemy_frame_w,
                            enemy_frame_h,
                            enemy_frame_hold,
                            submit_wire_order,
                            submit_wire_runtime_swap,
                        )
                    if enemy_bullets:
                        _render_enemy_bullets_into_scene(
                            scene_buf,
                            sw,
                            scene_h,
                            camera_x,
                            band_top,
                            enemy_bullets,
                            enemy_bullet_sprite_right,
                            enemy_bullet_sprite_left,
                            enemy_bullet_w,
                            enemy_bullet_h,
                            submit_wire_order,
                            submit_wire_runtime_swap,
                            enemy_bullet_color,
                        )

                    prof_world_us += ticks_diff(ticks_us(), seg_t0)

                    seg_t0 = ticks_us()
                    spr_x = 0
                    spr_y = 0
                    if use_sprite_player and death_state == 0:
                        sprite_x = player_screen_x + draw_off_x
                        sprite_y = player_y + draw_off_y
                        spr_x = sprite_x
                        spr_y = sprite_y - band_top
                        if facing < 0:
                            spr_rgb = sprite_left[anim_idx]
                        else:
                            spr_rgb = sprite_right[anim_idx]
                        player_colorkey = int(getattr(config, "CAMERA_PLAYER_COLORKEY_RGB565", 0xF81F)) & 0xFFFF
                        player_colorkey_raw = player_colorkey
                        if submit_wire_order and not submit_wire_runtime_swap:
                            player_colorkey_raw = _swap16(player_colorkey)
                        if hasattr(_lgfx, "compose_colorkey_rgb565"):
                            _lgfx.compose_colorkey_rgb565(
                                scene_buf,
                                sw,
                                scene_h,
                                spr_x,
                                spr_y,
                                spr_rgb,
                                sprite_w,
                                sprite_h,
                                player_colorkey_raw,
                            )
                            if not c_compose_ok_logged:
                                print("CAMERA_PLAYER_SPRITE_C_COLORKEY_OK")
                                c_compose_ok_logged = True
                        else:
                            key_b0 = player_colorkey_raw & 0xFF
                            key_b1 = (player_colorkey_raw >> 8) & 0xFF
                            _blit_sprite_colorkey_into_scene(
                                scene_buf,
                                sw,
                                scene_h,
                                spr_x,
                                spr_y,
                                spr_rgb,
                                key_b0,
                                key_b1,
                                sprite_w,
                                sprite_h,
                            )
                    elif death_state == 0:
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
                        partial_rect_experiment_disabled
                        and use_sprite_player
                        and sprite_draw_mode == "COMPOSE"
                        and (camera_static == 1 or not dirty_fallback_on_camera_move)
                        and drew_once
                    )
                    submit_t0 = ticks_us()
                    wait_us = 0
                    kick_us = 0
                    swap_us = 0
                    if submit_async_enabled:
                        kick_t0 = ticks_us()
                        try:
                            submit_async_fn(0, band_top, sw, scene_h, scene_buf)
                        except Exception:
                            submit_async_enabled = False
                            submit_async_inflight = False
                            submit_inflight_buf = None
                            print("SUBMIT_FALLBACK_REASON=ASYNC_KICK_FAIL")
                            submit_wait_fn(0, band_top, sw, scene_h, scene_buf)
                            kick_us = ticks_diff(ticks_us(), kick_t0)
                        else:
                            kick_us = ticks_diff(ticks_us(), kick_t0)
                            submit_async_inflight = True
                            submit_inflight_buf = scene_buf
                            # Swap compose/submit buffers for next frame.
                            tmp_buf = scene_buf
                            scene_buf = scene_buf_back
                            scene_buf_back = tmp_buf
                    else:
                        kick_t0 = ticks_us()
                        submit_wait_fn(0, band_top, sw, scene_h, scene_buf)
                        kick_us = ticks_diff(ticks_us(), kick_t0)
                    us = ticks_diff(ticks_us(), submit_t0)
                    submit_acc += us
                    prof_submit_us += us
                    prof_submit_wait_us += wait_us
                    prof_submit_kick_us += kick_us
                    prof_submit_swap_us += swap_us
                    dirty_last_rects_count = 2
                    dirty_last_bands_count = 1
                    dirty_last_camera_static = 1 if camera_x == prev_camera_x else 0
                    if dirty_log_countdown <= 0:
                        print("FULLSCREEN_BULK_SUBMIT_OK")
                        dirty_log_countdown = 30
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
                        _lgfx.blit_rect565_wait(0, 0, top_hud_w, top_hud_h, top_hud_buf)
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
                        _lgfx.blit_rect565_wait(right_x, 0, top_hud_w, top_hud_h, top_hud_buf)
                    prof_hud_us += ticks_diff(ticks_us(), seg_t0)

                frame_total_us = ticks_diff(ticks_us(), frame_start_us)
                prof_total_us += frame_total_us
                if frame_total_us >= stall_frame_us:
                    if stall_log_countdown <= 0:
                        print(
                            "STALL_FRAME total_us=%d submit_us=%d bg_us_acc=%d world_us_acc=%d sprite_us_acc=%d frame=%d camera_x=%d player_x=%d"
                            % (
                                frame_total_us,
                                us,
                                prof_bg_us,
                                prof_world_us,
                                prof_sprite_us,
                                frame,
                                camera_x,
                                player_x,
                            )
                        )
                        stall_log_countdown = stall_log_cooldown
                if stall_log_countdown > 0:
                    stall_log_countdown -= 1

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
                    if partial_rect_experiment_disabled:
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
                    avg_submit_wait_us = prof_submit_wait_us // n
                    avg_submit_kick_us = prof_submit_kick_us // n
                    avg_submit_swap_us = prof_submit_swap_us // n
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
                    print("PROFILE submit_wait_us=%d" % avg_submit_wait_us)
                    print("PROFILE submit_kick_us=%d" % avg_submit_kick_us)
                    print("PROFILE submit_swap_us=%d" % avg_submit_swap_us)
                    print("PROFILE pacing_us=%d" % avg_pace_us)
                    print("PROFILE other_us=%d" % avg_other_us)
                    print("PROFILE total_us=%d" % avg_total_us)
                    print("PROFILE fps=%.2f" % fps_prof)
                    if partial_rect_experiment_disabled:
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
                    prof_submit_wait_us = 0
                    prof_submit_kick_us = 0
                    prof_submit_swap_us = 0
                    prof_total_us = 0
                    prof_pace_us = 0

                if max_frames is not None and frame >= int(max_frames):
                    break

            if submit_async_enabled and submit_async_inflight:
                try:
                    w_t0 = ticks_us()
                    _lgfx.blit_wait_done()
                    prof_submit_wait_us += ticks_diff(ticks_us(), w_t0)
                except Exception:
                    pass
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
                _lgfx.blit_rect565_wait(0, y, sw, h, view)
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

    if mode == _MODE_BLIT_WAIT_GRID_TEST:
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
            _lgfx.blit_rect565_wait(0, y, sw, h, view)
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
        if not hasattr(_lgfx, "blit_rect565_wait"):
            raise RuntimeError("CAMERA_TEST_FAIL_NO_BLIT_WAIT")
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
                _lgfx.blit_rect565_wait(0, y, sw, h, view)
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
