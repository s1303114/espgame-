import config
import object_native

try:
    import monk_orb_damage
except Exception:
    monk_orb_damage = None

try:
    import monk_final_path
except Exception:
    monk_final_path = None

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
    import math
except Exception:
    math = None

try:
    import ujson as json
except Exception:
    try:
        import json
    except Exception:
        json = None

_MODE_ROWS_SAFE_PROGRESSIVE = "ROWS_SAFE_PROGRESSIVE"

_ENEMY_STATE_IDLE = 0
_ENEMY_STATE_WALK = 1
_ENEMY_STATE_SHOOT = 2
_ENEMY_STATE_DEATH = 3
_ENEMY_DEATH_FRAME_COUNT = 5
_BULLET_DEBUG_LIMIT = 12
_bullet_debug_count = 0
_bullet_debug_last_active_ms = -1000000
_enemy_native_update_disabled = False
_ENEMY_STATE_KEYS = ("facing", "state", "anim_counter", "shoot_cooldown", "shot_fired", "vel_y")
_ENEMY_ROW_STRIDE = 12
_ENEMY_STATE_STRIDE = 8
_BULLET_STATE_STRIDE = 16
_MONK_HOVER_STATE_STRIDE = 11
_MONK_ORB_NATIVE_STRIDE = 16
_MONK_ATTACK_NATIVE_STRIDE = 32
_MONK_ORB_NATIVE_MODE_ORBIT = 0
_MONK_ORB_NATIVE_MODE_DETACHED = 1
_MONK_ORB_NATIVE_MODE_CAPTURED_RETURN = 2
_MONK_ORB_NATIVE_MODE_SCRIPTED_INTRO = 3
_MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK = 4
_MONK_ORB_NATIVE_MODE_PULSE_DAMAGE = 5
_MONK_ORB_NATIVE_MODE_PULSE_HOLD = 6
_MONK_ORB_NATIVE_MODE_CLASH_BOUNCE = 7
_MONK_ORB_NATIVE_MODE_LOST = 8
_MONK_ORB_NATIVE_MODE_FINAL_ORBIT = 9
_MONK_ORB_NATIVE_MODE_PLAYER_ORBIT = 10
_MONK_ORB_NATIVE_MODE_UNUSED = 255
_MONK_ORB_NATIVE_FINAL_SWAP_PENDING = 1
_MONK_ORB_FINAL_RADIUS = 44
_MONK_ATTACK_NATIVE_FINAL_PHASE_LOCK = 8
_MONK_ATTACK_NATIVE_FINAL_PHASE_RUSH = 9
_MONK_ATTACK_NATIVE_FINAL_PHASE_DEATH = 12
_MONK_FINAL_PATH_DESC_MAX_COUNT = 40
_MONK_FINAL_PATH_DESC_CHUNK_PX = 96
_MONK_FINAL_PATH_THICKNESS = 1
_MONK_FINAL_RUSH_STEPS = 72
_SWAP_PREVIEW_STATE_STRIDE = 24
_SWAP_INPUT_STATE_STRIDE = 5
_SWAP_TARGET_NONE = 0
_SWAP_TARGET_OBJECT = 1
_SWAP_TARGET_ENEMY = 2
_SWAP_TARGET_BULLET = 3
_SWAP_TARGET_MONK_ORB = 4
_SWAP_PREVIEW_HYSTERESIS_PX = 16
_SPECIAL_KIND_SWAP_PREVIEW = 4
_boot_source_tag = "ROOT"
_draw_digits_to_buf = None
_get_digits_text_width = None


def _buf_get_i16_le(buf, off):
    val = buf[off] | (buf[off + 1] << 8)
    if val & 0x8000:
        val -= 0x10000
    return val


def _buf_get_u16_le(buf, off):
    return (buf[off] | (buf[off + 1] << 8)) & 0xFFFF


def _buf_get_i32_le(buf, off):
    val = buf[off] | (buf[off + 1] << 8) | (buf[off + 2] << 16) | (buf[off + 3] << 24)
    if val & 0x80000000:
        val -= 0x100000000
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


def _buf_set_u16_le(buf, off, value):
    uv = int(value) & 0xFFFF
    buf[off] = uv & 0xFF
    buf[off + 1] = (uv >> 8) & 0xFF


def _buf_set_i32_le(buf, off, value):
    uv = int(value) & 0xFFFFFFFF
    buf[off] = uv & 0xFF
    buf[off + 1] = (uv >> 8) & 0xFF
    buf[off + 2] = (uv >> 16) & 0xFF
    buf[off + 3] = (uv >> 24) & 0xFF


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


def _runtime_verbose_enabled():
    try:
        return bool(getattr(config, "CAMERA_RUNTIME_VERBOSE", False))
    except Exception:
        return False


def _monk_intro_enabled():
    try:
        return bool(getattr(config, "MONK_INTRO_ENABLED", True))
    except Exception:
        return True


def _monk_attack_enabled():
    try:
        return bool(getattr(config, "MONK_ATTACK_ENABLED", False))
    except Exception:
        return False


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
        if checkpoint:
            swappable = 0
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
            "frame_count": frame_count,
            "sheet": sheet,
            "sheet_w": sheet_w,
            "sheet_h": sheet_h,
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
        enemy_type = _col(cols, "type", "bow")
        swappable = 1 if _to_int(_col(cols, "swappable"), 0) != 0 else 0
        facing = _to_int(_col(cols, "facing"), -1)
        if facing >= 0:
            facing = 1
        else:
            facing = -1
        static_enemy = 1 if enemy_type == "monk" else 0
        gravity_enabled = 0 if static_enemy else 1
        rows.append([wx, wy, w, h, 1, swappable])
        meta_rows.append(
            {
                "id": _col(cols, "id", ""),
                "type": enemy_type,
                "facing": facing,
                "static": static_enemy,
                "gravity": gravity_enabled,
                "spawn_mode": _col(cols, "spawn_mode", "live"),
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


def _clone_enemy_meta_rows(meta_rows):
    if not meta_rows:
        return []
    return [dict(row) for row in meta_rows]


def _build_monk_encounter_from_template(row, meta):
    return {
        "state": _MONK_ENCOUNTER_STATE_INACTIVE,
        "template_row": list(row),
        "template_meta": dict(meta),
        "intro_state": None,
        "live_enemy_i": -1,
        "body_x": 0,
        "body_y": 0,
        "body_target_x": 0,
        "body_target_y": 0,
        "body_target_bottom_y": 0,
        "anim_counter": 0,
        "orbs": [],
        "orb_states": [],
    }


def _split_live_enemies_and_monk_encounters(rows, meta_rows):
    live_rows = []
    live_meta = []
    monk_encounters = []
    if not rows:
        return live_rows, live_meta, monk_encounters
    ei = 0
    while ei < len(rows):
        row = rows[ei]
        meta = meta_rows[ei] if (meta_rows is not None and ei < len(meta_rows)) else {}
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        spawn_mode = str(meta.get("spawn_mode", "live") or "live") if meta is not None else "live"
        if enemy_type == "monk" and spawn_mode != "live":
            monk_encounters.append(_build_monk_encounter_from_template(row, meta))
        else:
            live_rows.append(list(row))
            live_meta.append(dict(meta))
        ei += 1
    return live_rows, live_meta, monk_encounters


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


def _pick_animation_frame_index(anim_spec, anim_counter=0):
    if not anim_spec:
        return -1
    frames = anim_spec.get("frames") or []
    frame_count = len(frames)
    if frame_count <= 0:
        return -1
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
    return frame_index


def _pick_animation_frame(anim_spec, anim_counter=0):
    if not anim_spec:
        return None, 0, 0
    frames = anim_spec.get("frames") or []
    frame_index = _pick_animation_frame_index(anim_spec, anim_counter)
    if frame_index < 0 or frame_index >= len(frames):
        return None, 0, 0
    return frames[frame_index], int(anim_spec.get("frame_w", 0) or 0), int(anim_spec.get("frame_h", 0) or 0)


def _target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h):
    px = player_x + (player_w // 2)
    py = player_y + (player_h // 2)
    ox = int(wx) + (int(ow) // 2)
    oy = int(wy) + (int(oh) // 2)
    dx = ox - px
    dy = oy - py
    return dx * dx + dy * dy


def _visible_target_metrics(wx, wy, ow, oh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h):
    sx0 = int(wx) - int(camera_x)
    sy0 = int(wy) - int(band_top)
    sx1 = sx0 + int(ow)
    sy1 = sy0 + int(oh)
    cx0 = _clamp(sx0, 0, int(view_w))
    cy0 = _clamp(sy0, 0, int(view_h))
    cx1 = _clamp(sx1, 0, int(view_w))
    cy1 = _clamp(sy1, 0, int(view_h))
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    visible_w = cx1 - cx0
    visible_h = cy1 - cy0
    visible_area = visible_w * visible_h
    px = (int(player_x) - int(camera_x)) + (int(player_w) // 2)
    py = (int(player_y) - int(band_top)) + (int(player_h) // 2)
    ox = (cx0 + cx1) // 2
    oy = (cy0 + cy1) // 2
    dx = ox - px
    dy = oy - py
    return {
        'sx0': sx0,
        'sy0': sy0,
        'sx1': sx1,
        'sy1': sy1,
        'cx0': cx0,
        'cy0': cy0,
        'cx1': cx1,
        'cy1': cy1,
        'visible_w': visible_w,
        'visible_h': visible_h,
        'visible_area': visible_area,
        'd2': dx * dx + dy * dy,
    }


def _visible_target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h):
    info = _visible_target_metrics(wx, wy, ow, oh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
    if info is None:
        return -1
    visible_w = info['visible_w']
    visible_h = info['visible_h']
    visible_area = info['visible_area']
    if visible_w < 10 or visible_h < 10 or visible_area < 128:
        return -1
    return info['d2']


def _pick_swappable_enemy_index(enemy_rows, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h, enemy_meta=None):
    if not enemy_rows:
        return -1
    best_i = -1
    best_d2 = -1
    ei = 0
    while ei < len(enemy_rows):
        wx, wy, ow, oh, visible, swappable = enemy_rows[ei]
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        if visible and swappable and enemy_type != "monk":
            d2 = _visible_target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            if d2 >= 0:
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
            d2 = _visible_target_distance2(bx, by, bw, bh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            if d2 >= 0:
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


def _pick_swappable_monk_orb_native(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows_c_count, monk_orb_c_buf, monk_orb_c_stride, monk_orb_c_count, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h, prefer_enemy_i=-1, current_best_d2=-1):
    if _lgfx is None or not hasattr(_lgfx, "pick_swappable_monk_orb_native"):
        return -1, -1, -1
    if enemy_rows_c_buf is None or monk_orb_c_buf is None or enemy_rows_c_count <= 0 or monk_orb_c_count <= 0:
        return -1, -1, -1
    try:
        out = _lgfx.pick_swappable_monk_orb_native(
            enemy_rows_c_buf,
            enemy_rows_c_stride,
            enemy_rows_c_count,
            monk_orb_c_buf,
            monk_orb_c_stride,
            monk_orb_c_count,
            player_x,
            player_y,
            player_w,
            player_h,
            pick_far,
            camera_x,
            band_top,
            view_w,
            view_h,
            prefer_enemy_i,
            current_best_d2,
        )
        return int(out[0]), int(out[1]), int(out[2])
    except Exception as exc:
        print("MONK_ORB_PICK_NATIVE_FAIL %r" % (exc,))
        return -1, -1, -1


def _pick_swappable_monk_orb(enemy_rows, enemy_states, enemy_meta, monk_orb_states, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h, monk_frame_w, monk_frame_h, enemy_rows_c_buf=None, enemy_rows_c_stride=0, enemy_rows_c_count=0, monk_orb_c_buf=None, monk_orb_c_stride=0, monk_orb_c_count=0):
    native_enemy_i, native_slot_i, _native_d2 = _pick_swappable_monk_orb_native(
        enemy_rows_c_buf,
        enemy_rows_c_stride,
        enemy_rows_c_count,
        monk_orb_c_buf,
        monk_orb_c_stride,
        monk_orb_c_count,
        player_x,
        player_y,
        player_w,
        player_h,
        pick_far,
        camera_x,
        band_top,
        view_w,
        view_h,
    )
    if native_enemy_i >= 0 and native_slot_i >= 0:
        return native_enemy_i, native_slot_i
    if not enemy_rows or not enemy_states or not monk_orb_states:
        return -1, -1
    best_enemy_i = -1
    best_slot_i = -1
    best_d2 = -1
    ei = 0
    while ei < len(enemy_rows):
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        state = enemy_states[ei] if ei < len(enemy_states) else None
        slot_states = monk_orb_states[ei] if ei < len(monk_orb_states) else None
        if enemy_type == "monk" and state is not None and slot_states:
            wx, wy, ow, oh, visible, swappable = enemy_rows[ei]
            if visible and swappable:
                si = 0
                while si < len(slot_states):
                    orb_state = slot_states[si]
                    mode = str(orb_state.get("mode", "orbit") or "orbit") if orb_state is not None else "lost"
                    if mode == "clash_bounce" or mode == "lost":
                        si += 1
                        continue
                    orb_x, orb_y = _monk_orb_current_world_pos(wx, wy, ow, oh, int(state.get("anim_counter", 0) or 0), si, monk_frame_w, monk_frame_h, orb_state)
                    d2 = _visible_target_distance2(orb_x, orb_y, _MONK_ORB_W, _MONK_ORB_H, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
                    if d2 >= 0:
                        if best_enemy_i < 0:
                            best_enemy_i = ei
                            best_slot_i = si
                            best_d2 = d2
                        elif pick_far:
                            if d2 > best_d2:
                                best_enemy_i = ei
                                best_slot_i = si
                                best_d2 = d2
                        else:
                            if d2 < best_d2:
                                best_enemy_i = ei
                                best_slot_i = si
                                best_d2 = d2
                    si += 1
        ei += 1
    return best_enemy_i, best_slot_i


def _swap_with_monk_orb(enemy_rows, enemy_states, monk_orb_states, enemy_i, slot_i, player_x, player_y, player_w, player_h, max_player_x, map_h_px, monk_frame_w, monk_frame_h, monk_orb_c_buf=None, monk_orb_c_stride=0):
    if enemy_i < 0 or slot_i < 0 or enemy_i >= len(enemy_rows) or enemy_i >= len(enemy_states) or enemy_i >= len(monk_orb_states):
        return player_x, player_y, 0, False
    slot_states = monk_orb_states[enemy_i]
    if slot_states is None or slot_i >= len(slot_states):
        return player_x, player_y, 0, False
    row = enemy_rows[enemy_i]
    state = enemy_states[enemy_i]
    orb_state = slot_states[slot_i]
    native_pos = _monk_orb_c_current_pos(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if native_pos is not None:
        orb_x, orb_y = native_pos
    else:
        orb_x, orb_y = _monk_orb_current_world_pos(row[0], row[1], row[2], row[3], int(state.get("anim_counter", 0) or 0), slot_i, monk_frame_w, monk_frame_h, orb_state)
    old_px = int(player_x)
    old_py = int(player_y)
    player_x = orb_x + ((_MONK_ORB_W - player_w) // 2)
    player_y = orb_y + (_MONK_ORB_H - player_h)
    max_player_y_swap = map_h_px - player_h
    if max_player_y_swap < 0:
        max_player_y_swap = 0
    player_x = _clamp(player_x, 0, max_player_x)
    player_y = _clamp(player_y, 0, max_player_y_swap)
    new_orb_x = int(old_px + ((player_w - _MONK_ORB_W) // 2))
    new_orb_y = int(old_py + (player_h - _MONK_ORB_H))
    native_mode = _monk_orb_c_mode(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    final_swap = _monk_orb_c_is_final_candidate(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    orb_state["detached_x"] = new_orb_x
    orb_state["detached_y"] = new_orb_y
    orb_state["return_radius"] = _MONK_ORB_FINAL_RADIUS if final_swap else _MONK_ORB_RADIUS
    if native_mode == _MONK_ORB_NATIVE_MODE_FINAL_ORBIT:
        orb_state["mode"] = _MONK_ORB_MODE_FINAL_ORBIT
    elif native_mode == _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK:
        orb_state["mode"] = _MONK_ORB_MODE_SCRIPTED_ATTACK
    else:
        orb_state["mode"] = "detached"
    orb_state["script_x"] = new_orb_x
    orb_state["script_y"] = new_orb_y
    orb_state["current_x"] = new_orb_x
    orb_state["current_y"] = new_orb_y
    orb_state["native_current_valid"] = 0
    if final_swap:
        if _runtime_verbose_enabled():
            print("SWAP_MONK_ORB_FINAL_CONTINUE enemy=%d slot=%d mode=%d x=%d y=%d" % (enemy_i, slot_i, native_mode, new_orb_x, new_orb_y))
        _write_monk_orb_final_swap_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, native_mode, new_orb_x, new_orb_y)
    elif native_mode == _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK:
        if _runtime_verbose_enabled():
            print("SWAP_MONK_ORB_ATTACK_CONTINUE enemy=%d slot=%d x=%d y=%d" % (enemy_i, slot_i, new_orb_x, new_orb_y))
        _write_monk_orb_scripted_attack_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, new_orb_x, new_orb_y)
    else:
        _write_monk_orb_detached_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, new_orb_x, new_orb_y)
    if monk_orb_damage is not None:
        monk_orb_damage.ignore_next()
    return player_x, player_y, 0, True


def _pick_enemy_hit_by_bullet(enemy_rows, enemy_states, bx, by, bw, bh, ignore_enemy_i=-1, enemy_meta=None):
    if not enemy_rows:
        return -1
    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        if state is not None and ei != int(ignore_enemy_i):
            meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
            enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
            ex, ey, ew, eh, visible, _swappable = row
            if enemy_type != "monk" and visible and int(state.get("state", _ENEMY_STATE_IDLE)) != _ENEMY_STATE_DEATH and bx < (ex + ew) and (bx + bw) > ex and by < (ey + eh) and (by + bh) > ey:
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
    if state_code == _ENEMY_STATE_DEATH:
        if frame_idx >= _ENEMY_DEATH_FRAME_COUNT:
            frame_idx = _ENEMY_DEATH_FRAME_COUNT - 1
        src_y = frame_h * 3
        src_x = (frame_idx if face_right else (_ENEMY_DEATH_FRAME_COUNT + frame_idx)) * frame_w
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


def _pack_enemy_render_descriptors(enemy_rows, enemy_states, enemy_meta=None, camera_x=0, view_w=320, view_h=240, margin_x=48, margin_y=32, monk_frame_w=0, monk_frame_h=0):
    if not enemy_rows or not enemy_states:
        return bytearray(), 10, 0
    out = bytearray()
    count = 0
    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        if state is not None:
            wx, wy, ow, oh, visible, _swappable = row
            enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
            if visible and _aabb_near_view(wx, wy, ow, oh, camera_x, view_w, view_h, margin_x, margin_y):
                draw_x = int(wx)
                draw_y = int(wy)
                enemy_type_code = 0
                if enemy_type == "monk":
                    enemy_type_code = 1
                    if int(monk_frame_w) > 0 and int(ow) != int(monk_frame_w):
                        draw_x = int(wx) + ((int(ow) - int(monk_frame_w)) // 2)
                    if int(monk_frame_h) > 0 and int(oh) != int(monk_frame_h):
                        draw_y = int(wy) + (int(oh) - int(monk_frame_h))
                _append_i16_le(out, draw_x)
                _append_i16_le(out, draw_y)
                _append_u16_le(out, int(state.get("anim_counter", 0) or 0))
                out.append(int(state.get("state", _ENEMY_STATE_IDLE)) & 0xFF)
                out.append(1 if int(state.get("facing", 1)) >= 0 else 0)
                out.append(enemy_type_code & 0xFF)
                out.append(ei & 0xFF)
                count += 1
        ei += 1
    return out, 10, count


def _apply_monk_death_render_state(enemy_desc_buf, enemy_desc_stride, enemy_desc_count, monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count):
    if enemy_desc_count <= 0 or enemy_desc_stride < 10 or monk_attack_c_buf is None or monk_attack_c_stride < _MONK_ATTACK_NATIVE_STRIDE:
        return
    stride = int(enemy_desc_stride)
    attack_stride = int(monk_attack_c_stride)
    i = 0
    while i < int(enemy_desc_count):
        ebase = i * stride
        if (ebase + stride) <= len(enemy_desc_buf) and int(enemy_desc_buf[ebase + 8]) == 1:
            source_i = int(enemy_desc_buf[ebase + 9]) if stride > 9 else i
            if source_i < 0 or source_i >= int(monk_attack_c_count):
                source_i = i
            abase = source_i * attack_stride
            if (abase + _MONK_ATTACK_NATIVE_STRIDE) <= len(monk_attack_c_buf) and int(monk_attack_c_buf[abase]) == _MONK_ATTACK_NATIVE_FINAL_PHASE_DEATH:
                frame_counter = int(monk_attack_c_buf[abase + 14])
                _buf_set_u16_le(enemy_desc_buf, ebase + 4, frame_counter)
                enemy_desc_buf[ebase + 6] = _MONK_ATTACK_NATIVE_FINAL_PHASE_DEATH
        i += 1



def _load_enemy_runtime_assets(shared_monk_orb_atlas=None, shared_monk_orb_atlas_w=0, shared_monk_orb_atlas_h=0, shared_monk_orb_atlas_path=""):
    enemy_csv_path = _resolve_asset_path(getattr(config, "ENEMY_CSV_PATH", "game/picture/enemy/enemies.csv"))
    enemy_sheet_path = _resolve_asset_path(
        getattr(config, "ENEMY_SHEET_RGB565_PATH", "game/picture/enemy/enemy_bow_animation_wire.rgb565")
    )
    enemy_monk_sheet_path = _resolve_asset_path(
        getattr(config, "ENEMY_MONK_SHEET_RGB565_PATH", "game/picture/enemy/enemy_monk_wire.rgb565")
    )
    enemy_monk_orb_atlas_path = _resolve_asset_path(
        getattr(config, "ENEMY_MONK_ORB_ATLAS_RGB565_PATH", "game/picture/object/object_altes_wire.rgb565")
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

    enemy_rows_all, enemy_meta_all = _load_enemies_rows_and_meta(enemy_csv_path)
    enemy_rows, enemy_meta, monk_encounters = _split_live_enemies_and_monk_encounters(enemy_rows_all, enemy_meta_all)
    enemy_rows_initial = _clone_enemy_rows(enemy_rows)
    enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows_c_count = _pack_enemy_rows_for_c(enemy_rows, enemy_meta)
    monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count = _pack_monk_hover_states_for_c(enemy_rows, enemy_meta, int(getattr(config, "CAMERA_TEST_MAP_W", 0)))
    enemy_states = _build_enemy_states(enemy_meta)

    enemy_sheet = None
    if enemy_sheet_w > 0 and enemy_sheet_h > 0:
        enemy_sheet = _load_rgb565_blob(enemy_sheet_path, enemy_sheet_w * enemy_sheet_h * 2)

    enemy_monk_frame_w = int(getattr(config, "ENEMY_MONK_FRAME_W", 32))
    enemy_monk_frame_h = int(getattr(config, "ENEMY_MONK_FRAME_H", 48))
    enemy_monk_frame_count = int(getattr(config, "ENEMY_MONK_FRAME_COUNT", 4))
    enemy_monk_sheet_rows = int(getattr(config, "ENEMY_MONK_SHEET_ROWS", 1) or 1)
    enemy_monk_frame_hold = int(getattr(config, "ENEMY_MONK_FRAME_HOLD", 6))
    if enemy_monk_frame_count < 1:
        enemy_monk_frame_count = 1
    if enemy_monk_frame_hold < 1:
        enemy_monk_frame_hold = 1
    if enemy_monk_sheet_rows < 1:
        enemy_monk_sheet_rows = 1
    enemy_monk_sheet = None
    enemy_monk_sheet_w = enemy_monk_frame_w * enemy_monk_frame_count
    if enemy_monk_frame_w > 0 and enemy_monk_frame_h > 0 and enemy_monk_sheet_w > 0:
        enemy_monk_sheet = _load_rgb565_blob(enemy_monk_sheet_path, enemy_monk_sheet_w * enemy_monk_frame_h * enemy_monk_sheet_rows * 2)

    enemy_monk_orb_atlas_w = int(getattr(config, "ENEMY_MONK_ORB_ATLAS_W", 256))
    enemy_monk_orb_atlas_h = int(getattr(config, "ENEMY_MONK_ORB_ATLAS_H", 256))
    enemy_monk_orb_atlas = None
    if (
        shared_monk_orb_atlas is not None
        and int(shared_monk_orb_atlas_w) == enemy_monk_orb_atlas_w
        and int(shared_monk_orb_atlas_h) == enemy_monk_orb_atlas_h
        and str(shared_monk_orb_atlas_path or "") == str(enemy_monk_orb_atlas_path or "")
    ):
        enemy_monk_orb_atlas = shared_monk_orb_atlas
    elif enemy_monk_orb_atlas_w > 0 and enemy_monk_orb_atlas_h > 0:
        try:
            enemy_monk_orb_atlas = _load_rgb565_blob(
                enemy_monk_orb_atlas_path,
                enemy_monk_orb_atlas_w * enemy_monk_orb_atlas_h * 2,
            )
        except Exception:
            enemy_monk_orb_atlas = None

    enemy_bullets = _PackedEnemyBullets()
    enemy_bullets.ensure_capacity(enemy_max_bullets)
    enemy_update_native_ready = bool(_lgfx is not None and hasattr(_lgfx, "update_enemies_native"))
    enemy_bow_ready = bool(enemy_sheet is not None and enemy_frame_w > 0 and enemy_frame_h > 0)
    enemy_monk_ready = bool(enemy_monk_sheet is not None and enemy_monk_frame_w > 0 and enemy_monk_frame_h > 0)
    monk_orb_states = _build_monk_orb_states(enemy_rows, enemy_meta)
    monk_orb_c_buf, monk_orb_c_stride, monk_orb_c_count = _pack_monk_orbs_for_c(monk_orb_states)
    monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count = _pack_monk_attack_states_for_c(enemy_rows, enemy_meta)
    monk_attack_states = _build_monk_attack_states(enemy_rows, enemy_meta)
    monk_intro_states = _build_monk_intro_states(monk_encounters)
    enemy_render_enabled = bool((enemy_rows or monk_encounters) and (enemy_bow_ready or enemy_monk_ready))

    return {
        "enemy_detect_x": enemy_detect_x,
        "enemy_flee_x": enemy_flee_x,
        "enemy_detect_y": enemy_detect_y,
        "enemy_move_speed": enemy_move_speed,
        "enemy_gravity_step": enemy_gravity_step,
        "enemy_shoot_interval": enemy_shoot_interval,
        "enemy_shoot_fire_frame": enemy_shoot_fire_frame,
        "enemy_bullet_w": enemy_bullet_w,
        "enemy_bullet_h": enemy_bullet_h,
        "enemy_bullet_speed": enemy_bullet_speed,
        "enemy_max_bullets": enemy_max_bullets,
        "enemy_update_margin_x": enemy_update_margin_x,
        "enemy_update_margin_y": enemy_update_margin_y,
        "enemy_render_margin_x": enemy_render_margin_x,
        "enemy_render_margin_y": enemy_render_margin_y,
        "enemy_bullet_cull_margin": enemy_bullet_cull_margin,
        "enemy_bullet_color": enemy_bullet_color,
        "enemy_rows": enemy_rows,
        "enemy_meta": enemy_meta,
        "enemy_rows_initial": enemy_rows_initial,
        "monk_encounters": monk_encounters,
        "enemy_rows_c_buf": enemy_rows_c_buf,
        "enemy_rows_c_stride": enemy_rows_c_stride,
        "enemy_rows_c_count": enemy_rows_c_count,
        "monk_hover_c_buf": monk_hover_c_buf,
        "monk_hover_c_stride": monk_hover_c_stride,
        "monk_hover_c_count": monk_hover_c_count,
        "enemy_states": enemy_states,
        "enemy_sheet": enemy_sheet,
        "enemy_sheet_w": enemy_sheet_w,
        "enemy_sheet_h": enemy_sheet_h,
        "enemy_frame_w": enemy_frame_w,
        "enemy_frame_h": enemy_frame_h,
        "enemy_frame_hold": enemy_frame_hold,
        "enemy_monk_sheet": enemy_monk_sheet,
        "enemy_monk_frame_w": enemy_monk_frame_w,
        "enemy_monk_frame_h": enemy_monk_frame_h,
        "enemy_monk_frame_count": enemy_monk_frame_count,
        "enemy_monk_frame_hold": enemy_monk_frame_hold,
        "enemy_monk_orb_atlas": enemy_monk_orb_atlas,
        "enemy_monk_orb_atlas_w": enemy_monk_orb_atlas_w,
        "enemy_monk_orb_atlas_h": enemy_monk_orb_atlas_h,
        "monk_orb_states": monk_orb_states,
        "monk_orb_c_buf": monk_orb_c_buf,
        "monk_orb_c_stride": monk_orb_c_stride,
        "monk_orb_c_count": monk_orb_c_count,
        "monk_attack_c_buf": monk_attack_c_buf,
        "monk_attack_c_stride": monk_attack_c_stride,
        "monk_attack_c_count": monk_attack_c_count,
        "monk_attack_states": monk_attack_states,
        "monk_intro_states": monk_intro_states,
        "enemy_bullets": enemy_bullets,
        "enemy_update_native_ready": enemy_update_native_ready,
        "enemy_render_enabled": enemy_render_enabled,
        "monk_defeated": False,
    }

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
                if state_code == _ENEMY_STATE_DEATH:
                    death_anim_total = _ENEMY_DEATH_FRAME_COUNT * enemy_frame_hold
                    anim_counter = int(state.get("anim_counter", 0)) + 1
                    if anim_counter >= death_anim_total:
                        row[4] = 0
                        _reset_enemy_state(state, enemy_meta[ei] if ei < len(enemy_meta) else None)
                    else:
                        state["state"] = _ENEMY_STATE_DEATH
                        state["anim_counter"] = anim_counter
                        state["shot_fired"] = 0
                        state["vel_y"] = 0
                    ei += 1
                    continue
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
                            # Fire from the lower half of the enemy body: for a 32px enemy and
                            # 16px bullet, this anchors the bullet top at enemy_y + 16.
                            bullet_base_y = int(row[1]) + (int(eh) // 2)
                            bullet_y = _find_enemy_bullet_spawn_y(
                                bullet_base_y,
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
                hit_enemy_i = _pick_enemy_hit_by_bullet(enemy_rows, enemy_states, bx, by, bw, bh, shooter_enemy_i, enemy_meta)
                if hit_enemy_i >= 0:
                    active = 0
                    _bullet_debug("BULLET_HIT", "enemy idx=%d x=%d y=%d" % (int(hit_enemy_i), bx, by))
                    enemy_row = enemy_rows[hit_enemy_i]
                    enemy_row[5] = 0
                    hit_state = enemy_states[hit_enemy_i] if hit_enemy_i < len(enemy_states) else None
                    if hit_state is not None:
                        hit_state["state"] = _ENEMY_STATE_DEATH
                        hit_state["anim_counter"] = 0
                        hit_state["shoot_cooldown"] = 0
                        hit_state["shot_fired"] = 0
                        hit_state["vel_y"] = 0
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
    monk_hover_c_buf,
    monk_hover_c_stride,
    monk_hover_c_count,
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
            monk_hover_c_buf,
            monk_hover_c_stride,
            monk_hover_c_count,
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
    monk_orb_states,
    enemy_meta,
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
    monk_frame_w,
    monk_frame_h,
    monk_intro_states=None,
    monk_orb_c_buf=None,
    monk_orb_c_stride=0,
    monk_orb_c_count=0,
    enemy_rows_c_buf=None,
    enemy_rows_c_stride=0,
    enemy_rows_c_count=0,
    locked_target=None,
):
    if not swap_triggered or (not objects_rows and not enemy_rows and not enemy_bullets):
        return player_x, player_y, vel_y, object_native.rebuild_solids(objects_rows)

    if monk_intro_states:
        ei = 0
        while ei < len(monk_intro_states):
            intro_state = monk_intro_states[ei]
            if intro_state is not None and int(intro_state.get("state", _MONK_INTRO_STATE_IDLE) or _MONK_INTRO_STATE_IDLE) == _MONK_INTRO_STATE_DROPPING:
                if _runtime_verbose_enabled():
                    print("SWAP_BLOCKED_MONK_INTRO")
                return player_x, player_y, vel_y, object_native.rebuild_solids(objects_rows)
            ei += 1

    target_kind = None
    ti = -1
    object_ti = -1
    enemy_ti = -1
    monk_orb_enemy_i = -1
    monk_orb_slot_i = -1
    bullet_ti = -1
    if locked_target is not None and int(locked_target[1]) != 0:
        locked_kind = int(locked_target[3])
        locked_index = int(locked_target[4])
        locked_slot = int(locked_target[5])
        if locked_kind == _SWAP_TARGET_OBJECT:
            object_ti = locked_index
            target_kind = "object"
            ti = object_ti
        elif locked_kind == _SWAP_TARGET_ENEMY:
            enemy_ti = locked_index
            target_kind = "enemy"
            ti = enemy_ti
        elif locked_kind == _SWAP_TARGET_BULLET:
            bullet_ti = locked_index
            target_kind = "bullet"
            ti = bullet_ti
        elif locked_kind == _SWAP_TARGET_MONK_ORB:
            monk_orb_enemy_i = locked_index
            monk_orb_slot_i = locked_slot
            target_kind = "monk_orb"
            ti = monk_orb_slot_i
        best_d2 = int(locked_target[10])
    else:
        if objects_rows:
            object_ti = object_native.pick_swappable_index(
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
                enemy_meta,
            )
            monk_orb_enemy_i, monk_orb_slot_i = _pick_swappable_monk_orb(
                enemy_rows,
                enemy_states,
                enemy_meta,
                monk_orb_states,
                player_x,
                player_y,
                player_w,
                player_h,
                swap_pick_far,
                camera_x,
                band_top,
                view_w,
                view_h,
                monk_frame_w,
                monk_frame_h,
                enemy_rows_c_buf,
                enemy_rows_c_stride,
                enemy_rows_c_count,
                monk_orb_c_buf,
                monk_orb_c_stride,
                monk_orb_c_count,
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

        if object_ti >= 0:
            row = objects_rows[object_ti]
            target_kind = "object"
            ti = object_ti
            best_d2 = _visible_target_distance2(row[0], row[1], row[2], row[3], player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
        else:
            best_d2 = -1
        if enemy_ti >= 0:
            row = enemy_rows[enemy_ti]
            d2 = _visible_target_distance2(row[0], row[1], row[2], row[3], player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            if ti < 0 or (swap_pick_far and d2 > best_d2) or ((not swap_pick_far) and d2 < best_d2):
                target_kind = "enemy"
                ti = enemy_ti
                best_d2 = d2
        if monk_orb_enemy_i >= 0 and monk_orb_slot_i >= 0:
            row = enemy_rows[monk_orb_enemy_i]
            state = enemy_states[monk_orb_enemy_i] if monk_orb_enemy_i < len(enemy_states) else None
            slot_states = monk_orb_states[monk_orb_enemy_i] if (monk_orb_states is not None and monk_orb_enemy_i < len(monk_orb_states)) else None
            if state is not None and slot_states is not None and monk_orb_slot_i < len(slot_states):
                orb_state = slot_states[monk_orb_slot_i]
                native_pos = _monk_orb_c_current_pos(monk_orb_c_buf, monk_orb_c_stride, monk_orb_enemy_i, monk_orb_slot_i)
                if native_pos is not None:
                    orb_x, orb_y = native_pos
                else:
                    orb_x, orb_y = _monk_orb_current_world_pos(row[0], row[1], row[2], row[3], int(state.get("anim_counter", 0) or 0), monk_orb_slot_i, monk_frame_w, monk_frame_h, orb_state)
                d2 = _visible_target_distance2(orb_x, orb_y, _MONK_ORB_W, _MONK_ORB_H, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
                prefer_over_enemy = (target_kind == "enemy" and enemy_ti == monk_orb_enemy_i)
                if d2 >= 0 and (prefer_over_enemy or ti < 0 or (swap_pick_far and d2 > best_d2) or ((not swap_pick_far) and d2 < best_d2)):
                    target_kind = "monk_orb"
                    ti = monk_orb_slot_i
                    best_d2 = d2
        if bullet_ti >= 0:
            row = enemy_bullets[bullet_ti]
            d2 = _visible_target_distance2(row[0], row[1], row[4], row[5], player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            if ti < 0 or (swap_pick_far and d2 > best_d2) or ((not swap_pick_far) and d2 < best_d2):
                target_kind = "bullet"
                ti = bullet_ti
                best_d2 = d2

    if swap_triggered:
        print("SWAP_CANDIDATE_DBG obj=%d enemy=%d bullet=%d far=%d" % (
            object_ti,
            enemy_ti,
            bullet_ti,
            1 if swap_pick_far else 0,
        ))
        if target_kind == "object" and ti >= 0:
            row = objects_rows[ti]
            info = _visible_target_metrics(row[0], row[1], row[2], row[3], player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            print("SWAP_TARGET_DBG kind=object idx=%d wx=%d wy=%d ow=%d oh=%d info=%r" % (ti, row[0], row[1], row[2], row[3], info))
        elif target_kind == "enemy" and ti >= 0:
            row = enemy_rows[ti]
            info = _visible_target_metrics(row[0], row[1], row[2], row[3], player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            print("SWAP_TARGET_DBG kind=enemy idx=%d wx=%d wy=%d ow=%d oh=%d info=%r" % (ti, row[0], row[1], row[2], row[3], info))
        elif target_kind == "bullet" and ti >= 0:
            row = enemy_bullets[ti]
            info = _visible_target_metrics(row[0], row[1], row[4], row[5], player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            print("SWAP_TARGET_DBG kind=bullet idx=%d wx=%d wy=%d ow=%d oh=%d info=%r" % (ti, row[0], row[1], row[4], row[5], info))
        elif target_kind == "monk_orb" and monk_orb_enemy_i >= 0:
            row = enemy_rows[monk_orb_enemy_i]
            state = enemy_states[monk_orb_enemy_i] if monk_orb_enemy_i < len(enemy_states) else None
            slot_states = monk_orb_states[monk_orb_enemy_i] if (monk_orb_states is not None and monk_orb_enemy_i < len(monk_orb_states)) else None
            if state is not None and slot_states is not None and ti < len(slot_states):
                orb_state = slot_states[ti]
                native_pos = _monk_orb_c_current_pos(monk_orb_c_buf, monk_orb_c_stride, monk_orb_enemy_i, ti)
                if native_pos is not None:
                    orb_x, orb_y = native_pos
                else:
                    orb_x, orb_y = _monk_orb_current_world_pos(row[0], row[1], row[2], row[3], int(state.get("anim_counter", 0) or 0), ti, monk_frame_w, monk_frame_h, orb_state)
                info = _visible_target_metrics(orb_x, orb_y, _MONK_ORB_W, _MONK_ORB_H, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
                print("SWAP_TARGET_DBG kind=monk_orb enemy=%d slot=%d wx=%d wy=%d ow=%d oh=%d info=%r" % (monk_orb_enemy_i, ti, orb_x, orb_y, _MONK_ORB_W, _MONK_ORB_H, info))
        else:
            print("SWAP_TARGET_DBG kind=none idx=-1")

    object_solids = object_native.rebuild_solids(objects_rows)
    if target_kind == "object" and ti >= 0:
        row = objects_rows[ti]
        meta = objects_meta[ti] if ti < len(objects_meta) else None
        if meta and meta.get("checkpoint"):
            return player_x, player_y, vel_y, object_solids
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
        object_solids = object_native.rebuild_solids(objects_rows)
        max_player_y_swap = map_h_px - player_h
        if max_player_y_swap < 0:
            max_player_y_swap = 0
        player_x = _clamp(player_x, 0, max_player_x)
        player_y = _clamp(player_y, 0, max_player_y_swap)
        object_native.repack_render_entry(objects_c_buf, objects_c_stride, ti, row[0], row[1], row[8], row[9], row[10], row[11], meta)
        object_solids = object_native.rebuild_solids(objects_rows)
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
    elif target_kind == "monk_orb" and monk_orb_enemy_i >= 0 and ti >= 0:
        player_x, player_y, vel_y, swapped_ok = _swap_with_monk_orb(
            enemy_rows,
            enemy_states,
            monk_orb_states,
            monk_orb_enemy_i,
            ti,
            player_x,
            player_y,
            player_w,
            player_h,
            max_player_x,
            map_h_px,
            monk_frame_w,
            monk_frame_h,
            monk_orb_c_buf,
            monk_orb_c_stride,
        )
        if swapped_ok:
            slot_states = monk_orb_states[monk_orb_enemy_i] if (monk_orb_states is not None and monk_orb_enemy_i < len(monk_orb_states)) else None
            if slot_states is not None and ti < len(slot_states):
                slot_states[ti]["native_current_valid"] = 0
            if swap_pick_far:
                print("SWAP_FAR_OK_MONK_ORB enemy=%d slot=%d px=%d py=%d" % (monk_orb_enemy_i, ti, player_x, player_y))
            else:
                print("SWAP_NEAR_OK_MONK_ORB enemy=%d slot=%d px=%d py=%d" % (monk_orb_enemy_i, ti, player_x, player_y))
        else:
            print("SWAP_FAIL_NO_TARGET_V2")
    else:
        print("SWAP_FAIL_NO_TARGET_V2")
    return player_x, player_y, vel_y, object_solids


def _is_special_render_object(meta):
    return bool(meta and meta.get("special_render"))


_SPECIAL_KIND_RESPAWN_STONE = 0
_SPECIAL_KIND_ANCHOR = 1
_SPECIAL_KIND_MONK_ORB = 2
_SPECIAL_KIND_MONK_FINAL_PATH = 3

_MONK_ORB_COUNT = 5
_MONK_ORB_RADIUS = 28
_MONK_ORB_W = 16
_MONK_ORB_H = 16
_MONK_ORB_SCALE = 1024
_MONK_ORB_TABLE_SIZE = 60
_MONK_ORB_COS = (1024, 1018, 1002, 974, 935, 887, 828, 761, 685, 602, 512, 416, 316, 213, 107, 0, -107, -213, -316, -416, -512, -602, -685, -761, -828, -887, -935, -974, -1002, -1018, -1024, -1018, -1002, -974, -935, -887, -828, -761, -685, -602, -512, -416, -316, -213, -107, 0, 107, 213, 316, 416, 512, 602, 685, 761, 828, 887, 935, 974, 1002, 1018)
_MONK_ORB_SIN = (0, 107, 213, 316, 416, 512, 602, 685, 761, 828, 887, 935, 974, 1002, 1018, 1024, 1018, 1002, 974, 935, 887, 828, 761, 685, 602, 512, 416, 316, 213, 107, 0, -107, -213, -316, -416, -512, -602, -685, -761, -828, -887, -935, -974, -1002, -1018, -1024, -1018, -1002, -974, -935, -887, -828, -761, -685, -602, -512, -416, -316, -213, -107)
_MONK_ORB_CAPTURE_ANGLE_EPS = 1
_MONK_ORB_CAPTURE_LOCK_FRAMES = 4
_MONK_ORB_CAPTURE_LINE_EPS = 6
_MONK_ORB_RETURN_DONE_RADIUS_EPS = 1
_MONK_ORB_RETURN_RADIUS_DIV = 20
_MONK_ORB_RETURN_RADIUS_MIN_STEP = 1
_MONK_ORB_RAD_PER_IDX = 6.283185307179586 / _MONK_ORB_TABLE_SIZE
_MONK_ORB_MODE_SCRIPTED_INTRO = "scripted_intro"
_MONK_ORB_MODE_SCRIPTED_ATTACK = "scripted_attack"
_MONK_ORB_MODE_FINAL_ORBIT = "final_orbit"
_MONK_ORB_MODE_PLAYER_ORBIT = "player_orbit"
_MONK_ENCOUNTER_STATE_INACTIVE = "inactive"
_MONK_ENCOUNTER_STATE_INTRO = "intro_drop"
_MONK_ENCOUNTER_STATE_LIVE = "live"
_MONK_ENCOUNTER_STATE_DEFEATED = "defeated"
_MONK_ATTACK_PHASE_SPLIT = "split_edges"
_MONK_ATTACK_PHASE_DROP = "drop_profile"
_MONK_ATTACK_PHASE_SWEEP = "sweep"
_MONK_ATTACK_PHASE_PAUSE = "pause"
_MONK_ATTACK_PAUSE_FRAMES = 30
_MONK_ATTACK_EDGE_SPEED = 6
_MONK_ATTACK_DROP_SPEED = 6
_MONK_ATTACK_SWEEP_SPEED = 4
_MONK_ATTACK_BODY_LOCK_CD = 2
_MONK_ATTACK_PROFILE_LIFTS = ((0, 16), (16, 0), (0, 32), (32, 0))
_MONK_HOVER_MOVING_CD = 255
_MONK_HOVER_INTERVAL_MIN_CD = 1
_MONK_INTRO_STATE_IDLE = 0
_MONK_INTRO_STATE_DROPPING = 1
_MONK_INTRO_STATE_DONE = 2
_MONK_INTRO_NATIVE_STRIDE = 64
_MONK_INTRO_NATIVE_ORB_BASE = 20
_MONK_INTRO_NATIVE_ORB_STRIDE = 4


def _cyclic_idx_diff(target_idx, current_idx, modulo):
    diff = (int(target_idx) - int(current_idx)) % int(modulo)
    if diff > (modulo // 2):
        diff -= modulo
    return diff


def _monk_enemy_draw_origin(wx, wy, ow, oh, monk_frame_w, monk_frame_h):
    draw_x = int(wx)
    draw_y = int(wy)
    if int(monk_frame_w) > 0 and int(ow) != int(monk_frame_w):
        draw_x = int(wx) + ((int(ow) - int(monk_frame_w)) // 2)
    if int(monk_frame_h) > 0 and int(oh) != int(monk_frame_h):
        draw_y = int(wy) + (int(oh) - int(monk_frame_h))
    return draw_x, draw_y


def _monk_center_world_pos(wx, wy, ow, oh, monk_frame_w, monk_frame_h):
    draw_x, draw_y = _monk_enemy_draw_origin(wx, wy, ow, oh, monk_frame_w, monk_frame_h)
    return draw_x + (int(monk_frame_w) // 2), draw_y + (int(monk_frame_h) // 2)


def _monk_orb_world_pos_from_polar(center_x, center_y, radius_px, angle_idx):
    idx = int(angle_idx) % _MONK_ORB_TABLE_SIZE
    orb_cx = int(center_x) + ((_MONK_ORB_COS[idx] * int(radius_px)) // _MONK_ORB_SCALE)
    orb_cy = int(center_y) - ((_MONK_ORB_SIN[idx] * int(radius_px)) // _MONK_ORB_SCALE)
    return orb_cx - (_MONK_ORB_W // 2), orb_cy - (_MONK_ORB_H // 2)


def _monk_orb_world_pos_from_angle(center_x, center_y, radius_px, angle_rad):
    if math is None:
        idx = int((float(angle_rad) / _MONK_ORB_RAD_PER_IDX) + 0.5)
        return _monk_orb_world_pos_from_polar(center_x, center_y, radius_px, idx)
    orb_cx = int(center_x) + int(math.cos(float(angle_rad)) * float(radius_px))
    orb_cy = int(center_y) - int(math.sin(float(angle_rad)) * float(radius_px))
    return orb_cx - (_MONK_ORB_W // 2), orb_cy - (_MONK_ORB_H // 2)


def _monk_orb_slot_angle_rad(anim_counter, slot_i):
    angle_rad = float(int(anim_counter or 0)) * _MONK_ORB_RAD_PER_IDX
    angle_rad += (float(slot_i) * 6.283185307179586) / float(_MONK_ORB_COUNT)
    while angle_rad >= 6.283185307179586:
        angle_rad -= 6.283185307179586
    while angle_rad < 0.0:
        angle_rad += 6.283185307179586
    return angle_rad


def _monk_orb_rel_to_center(center_x, center_y, orb_x, orb_y):
    orb_cx = int(orb_x) + (_MONK_ORB_W // 2)
    orb_cy = int(orb_y) + (_MONK_ORB_H // 2)
    rel_x = orb_cx - int(center_x)
    rel_y = int(center_y) - orb_cy
    return rel_x, rel_y


def _pick_nearest_monk_orb_angle_idx(rel_x, rel_y):
    best_idx = 0
    best_dot = None
    idx = 0
    while idx < _MONK_ORB_TABLE_SIZE:
        dot = (int(rel_x) * _MONK_ORB_COS[idx]) + (int(rel_y) * _MONK_ORB_SIN[idx])
        if best_dot is None or dot > best_dot:
            best_dot = dot
            best_idx = idx
        idx += 1
    return best_idx


def _quantize_monk_orb_polar(center_x, center_y, orb_x, orb_y):
    orb_cx = int(orb_x) + (_MONK_ORB_W // 2)
    orb_cy = int(orb_y) + (_MONK_ORB_H // 2)
    rel_x = orb_cx - int(center_x)
    rel_y = int(center_y) - orb_cy
    radius_px = _MONK_ORB_RADIUS
    radius_sq = (rel_x * rel_x) + (rel_y * rel_y)
    if radius_sq > 0:
        if math is not None:
            try:
                radius_px = int(math.sqrt(radius_sq))
            except Exception:
                radius_px = _MONK_ORB_RADIUS
    angle_rad = 0.0
    if math is not None:
        try:
            angle_rad = math.atan2(float(rel_y), float(rel_x))
            if angle_rad < 0.0:
                angle_rad += 6.283185307179586
        except Exception:
            angle_idx = _pick_nearest_monk_orb_angle_idx(rel_x, rel_y)
            angle_rad = float(angle_idx) * _MONK_ORB_RAD_PER_IDX
    else:
        angle_idx = _pick_nearest_monk_orb_angle_idx(rel_x, rel_y)
        angle_rad = float(angle_idx) * _MONK_ORB_RAD_PER_IDX
    return radius_px, angle_rad


def _build_monk_orb_states(enemy_rows, enemy_meta=None, orb_count=_MONK_ORB_COUNT):
    states = []
    if not enemy_rows or orb_count <= 0:
        return states
    ei = 0
    while ei < len(enemy_rows):
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        if enemy_type == "monk":
            slot_states = []
            si = 0
            while si < orb_count:
                slot_states.append({
                    "slot": si,
                    "mode": "orbit",
                    "detached_x": 0,
                    "detached_y": 0,
                    "return_radius": _MONK_ORB_RADIUS,
                    "capture_lock": 0,
                    "script_x": 0,
                    "script_y": 0,
                    "script_target_x": 0,
                    "script_target_y": 0,
                })
                si += 1
            states.append(slot_states)
        else:
            states.append(None)
        ei += 1
    return states


def _monk_orb_native_mode_from_state(orb_state):
    if orb_state is None:
        return _MONK_ORB_NATIVE_MODE_UNUSED
    mode = str(orb_state.get("mode", "orbit") or "orbit")
    if mode == "detached":
        return _MONK_ORB_NATIVE_MODE_DETACHED
    if mode == "captured_return":
        return _MONK_ORB_NATIVE_MODE_CAPTURED_RETURN
    if mode == _MONK_ORB_MODE_SCRIPTED_INTRO:
        return _MONK_ORB_NATIVE_MODE_SCRIPTED_INTRO
    if mode == _MONK_ORB_MODE_SCRIPTED_ATTACK:
        return _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK
    if mode == _MONK_ORB_MODE_FINAL_ORBIT:
        return _MONK_ORB_NATIVE_MODE_FINAL_ORBIT
    if mode == _MONK_ORB_MODE_PLAYER_ORBIT:
        return _MONK_ORB_NATIVE_MODE_PLAYER_ORBIT
    if mode == "clash_bounce":
        return _MONK_ORB_NATIVE_MODE_CLASH_BOUNCE
    if mode == "lost":
        return _MONK_ORB_NATIVE_MODE_LOST
    return _MONK_ORB_NATIVE_MODE_ORBIT


def _monk_orb_state_mode_from_native(mode):
    mi = int(mode)
    if mi == _MONK_ORB_NATIVE_MODE_DETACHED:
        return "detached"
    if mi == _MONK_ORB_NATIVE_MODE_CAPTURED_RETURN:
        return "captured_return"
    if mi == _MONK_ORB_NATIVE_MODE_SCRIPTED_INTRO:
        return _MONK_ORB_MODE_SCRIPTED_INTRO
    if mi == _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK:
        return _MONK_ORB_MODE_SCRIPTED_ATTACK
    if mi == _MONK_ORB_NATIVE_MODE_FINAL_ORBIT:
        return _MONK_ORB_MODE_FINAL_ORBIT
    if mi == _MONK_ORB_NATIVE_MODE_PLAYER_ORBIT:
        return _MONK_ORB_MODE_PLAYER_ORBIT
    if mi == _MONK_ORB_NATIVE_MODE_CLASH_BOUNCE:
        return "clash_bounce"
    if mi == _MONK_ORB_NATIVE_MODE_LOST:
        return "lost"
    return "orbit"


def _pack_monk_orbs_for_c(monk_orb_states):
    if not monk_orb_states:
        return bytearray(), _MONK_ORB_NATIVE_STRIDE, 0
    count = len(monk_orb_states) * _MONK_ORB_COUNT
    out = bytearray(count * _MONK_ORB_NATIVE_STRIDE)
    ei = 0
    while ei < len(monk_orb_states):
        slot_states = monk_orb_states[ei]
        si = 0
        while si < _MONK_ORB_COUNT:
            base = ((ei * _MONK_ORB_COUNT) + si) * _MONK_ORB_NATIVE_STRIDE
            orb_state = slot_states[si] if (slot_states is not None and si < len(slot_states)) else None
            mode = _monk_orb_native_mode_from_state(orb_state)
            out[base + 0] = mode & 0xFF
            out[base + 1] = si & 0xFF
            if orb_state is not None:
                out[base + 2] = int(orb_state.get("capture_lock", 0) or 0) & 0xFF
                _buf_set_i16_le(out, base + 4, int(orb_state.get("detached_x", 0) or 0))
                _buf_set_i16_le(out, base + 6, int(orb_state.get("detached_y", 0) or 0))
                _buf_set_i16_le(out, base + 8, int(orb_state.get("return_radius", _MONK_ORB_RADIUS) or _MONK_ORB_RADIUS))
                _buf_set_i16_le(out, base + 10, int(orb_state.get("current_x", orb_state.get("script_x", 0)) or 0))
                _buf_set_i16_le(out, base + 12, int(orb_state.get("current_y", orb_state.get("script_y", 0)) or 0))
            si += 1
        ei += 1
    return out, _MONK_ORB_NATIVE_STRIDE, count


def _sync_monk_orb_state_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, orb_state):
    if monk_orb_c_buf is None or orb_state is None or monk_orb_c_stride < _MONK_ORB_NATIVE_STRIDE:
        return
    base = ((int(enemy_i) * _MONK_ORB_COUNT) + int(slot_i)) * int(monk_orb_c_stride)
    if base < 0 or (base + _MONK_ORB_NATIVE_STRIDE) > len(monk_orb_c_buf):
        return
    monk_orb_c_buf[base + 0] = _monk_orb_native_mode_from_state(orb_state) & 0xFF
    monk_orb_c_buf[base + 1] = int(slot_i) & 0xFF
    monk_orb_c_buf[base + 2] = int(orb_state.get("capture_lock", 0) or 0) & 0xFF
    _buf_set_i16_le(monk_orb_c_buf, base + 4, int(orb_state.get("detached_x", 0) or 0))
    _buf_set_i16_le(monk_orb_c_buf, base + 6, int(orb_state.get("detached_y", 0) or 0))
    _buf_set_i16_le(monk_orb_c_buf, base + 8, int(orb_state.get("return_radius", _MONK_ORB_RADIUS) or _MONK_ORB_RADIUS))
    _buf_set_i16_le(monk_orb_c_buf, base + 10, int(orb_state.get("current_x", 0) or 0))
    _buf_set_i16_le(monk_orb_c_buf, base + 12, int(orb_state.get("current_y", 0) or 0))


def _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i):
    if monk_orb_c_buf is None or monk_orb_c_stride < _MONK_ORB_NATIVE_STRIDE:
        return -1
    base = ((int(enemy_i) * _MONK_ORB_COUNT) + int(slot_i)) * int(monk_orb_c_stride)
    if base < 0 or (base + _MONK_ORB_NATIVE_STRIDE) > len(monk_orb_c_buf):
        return -1
    return base


def _monk_orb_c_current_pos(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i):
    base = _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if base < 0:
        return None
    mode = int(monk_orb_c_buf[base + 0])
    if mode == _MONK_ORB_NATIVE_MODE_UNUSED or mode == _MONK_ORB_NATIVE_MODE_SCRIPTED_INTRO or mode == _MONK_ORB_NATIVE_MODE_LOST:
        return None
    return _buf_get_i16_le(monk_orb_c_buf, base + 10), _buf_get_i16_le(monk_orb_c_buf, base + 12)


def _monk_orb_c_mode(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i):
    base = _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if base < 0:
        return _MONK_ORB_NATIVE_MODE_UNUSED
    return int(monk_orb_c_buf[base + 0])


def _monk_orb_c_is_final_candidate(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i):
    mode = _monk_orb_c_mode(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if mode != _MONK_ORB_NATIVE_MODE_FINAL_ORBIT and mode != _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK:
        return False
    lost_count = 0
    si = 0
    while si < _MONK_ORB_COUNT:
        base = _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, si)
        if base < 0:
            return False
        slot_mode = int(monk_orb_c_buf[base + 0])
        if si == int(slot_i):
            if slot_mode != mode:
                return False
        elif slot_mode == _MONK_ORB_NATIVE_MODE_LOST:
            lost_count += 1
        else:
            return False
        si += 1
    return lost_count == (_MONK_ORB_COUNT - 1)


def _write_monk_orb_detached_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, detached_x, detached_y):
    base = _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if base < 0:
        return False
    monk_orb_c_buf[base + 0] = _MONK_ORB_NATIVE_MODE_DETACHED
    monk_orb_c_buf[base + 1] = int(slot_i) & 0xFF
    monk_orb_c_buf[base + 2] = 0
    monk_orb_c_buf[base + 3] = 1
    _buf_set_i16_le(monk_orb_c_buf, base + 4, detached_x)
    _buf_set_i16_le(monk_orb_c_buf, base + 6, detached_y)
    _buf_set_i16_le(monk_orb_c_buf, base + 8, _MONK_ORB_RADIUS)
    _buf_set_i16_le(monk_orb_c_buf, base + 10, detached_x)
    _buf_set_i16_le(monk_orb_c_buf, base + 12, detached_y)
    return True


def _write_monk_orb_scripted_attack_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, script_x, script_y):
    base = _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if base < 0:
        return False
    monk_orb_c_buf[base + 0] = _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK
    monk_orb_c_buf[base + 1] = int(slot_i) & 0xFF
    monk_orb_c_buf[base + 2] = 0
    monk_orb_c_buf[base + 3] = 1
    _buf_set_i16_le(monk_orb_c_buf, base + 4, script_x)
    _buf_set_i16_le(monk_orb_c_buf, base + 6, script_y)
    _buf_set_i16_le(monk_orb_c_buf, base + 8, _MONK_ORB_RADIUS)
    _buf_set_i16_le(monk_orb_c_buf, base + 10, script_x)
    _buf_set_i16_le(monk_orb_c_buf, base + 12, script_y)
    return True


def _write_monk_orb_final_swap_to_c(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i, native_mode, x, y):
    base = _monk_orb_c_base(monk_orb_c_buf, monk_orb_c_stride, enemy_i, slot_i)
    if base < 0:
        return False
    mode = _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK if int(native_mode) == _MONK_ORB_NATIVE_MODE_SCRIPTED_ATTACK else _MONK_ORB_NATIVE_MODE_FINAL_ORBIT
    monk_orb_c_buf[base + 0] = mode
    monk_orb_c_buf[base + 1] = int(slot_i) & 0xFF
    monk_orb_c_buf[base + 2] = _MONK_ORB_NATIVE_FINAL_SWAP_PENDING
    monk_orb_c_buf[base + 3] = 1
    _buf_set_i16_le(monk_orb_c_buf, base + 4, x)
    _buf_set_i16_le(monk_orb_c_buf, base + 6, y)
    _buf_set_i16_le(monk_orb_c_buf, base + 8, _MONK_ORB_FINAL_RADIUS)
    _buf_set_i16_le(monk_orb_c_buf, base + 10, x)
    _buf_set_i16_le(monk_orb_c_buf, base + 12, y)
    return True


def _sync_monk_orbs_from_c(monk_orb_states, monk_orb_c_buf, monk_orb_c_stride):
    if not monk_orb_states or monk_orb_c_buf is None or monk_orb_c_stride < _MONK_ORB_NATIVE_STRIDE:
        return
    ei = 0
    while ei < len(monk_orb_states):
        slot_states = monk_orb_states[ei]
        if slot_states is not None:
            si = 0
            while si < len(slot_states) and si < _MONK_ORB_COUNT:
                base = ((ei * _MONK_ORB_COUNT) + si) * int(monk_orb_c_stride)
                if (base + _MONK_ORB_NATIVE_STRIDE) <= len(monk_orb_c_buf):
                    mode = monk_orb_c_buf[base + 0]
                    if mode != _MONK_ORB_NATIVE_MODE_UNUSED:
                        orb_state = slot_states[si]
                        orb_state["mode"] = _monk_orb_state_mode_from_native(mode)
                        orb_state["capture_lock"] = int(monk_orb_c_buf[base + 2])
                        orb_state["return_radius"] = _buf_get_i16_le(monk_orb_c_buf, base + 8)
                        orb_state["current_x"] = _buf_get_i16_le(monk_orb_c_buf, base + 10)
                        orb_state["current_y"] = _buf_get_i16_le(monk_orb_c_buf, base + 12)
                        orb_state["native_current_valid"] = 1
                si += 1
        ei += 1


def _monk_orb_native_ready():
    return bool(_lgfx is not None and hasattr(_lgfx, "update_monk_orbs_native"))


def _update_monk_orbs_native(monk_orb_states, monk_orb_c_buf, monk_orb_c_stride, monk_orb_c_count, enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows_c_count, enemy_states, monk_frame_w, monk_frame_h):
    if not _monk_orb_native_ready():
        return False
    if not monk_orb_states or monk_orb_c_buf is None or monk_orb_c_count <= 0:
        return False
    if enemy_rows_c_buf is None or enemy_rows_c_count <= 0 or not hasattr(enemy_states, "_buf"):
        return False
    try:
        _lgfx.update_monk_orbs_native(
            monk_orb_c_buf,
            monk_orb_c_stride,
            monk_orb_c_count,
            enemy_rows_c_buf,
            enemy_rows_c_stride,
            enemy_rows_c_count,
            enemy_states._buf,
            _ENEMY_STATE_STRIDE,
            monk_frame_w,
            monk_frame_h,
        )
        return True
    except Exception as exc:
        print("MONK_ORB_NATIVE_FAIL %r" % (exc,))
        return False


def _pack_monk_attack_states_for_c(enemy_rows, enemy_meta=None):
    count = len(enemy_rows) if enemy_rows else 0
    out = bytearray(count * _MONK_ATTACK_NATIVE_STRIDE)
    ei = 0
    while ei < count:
        base = ei * _MONK_ATTACK_NATIVE_STRIDE
        out[base + 0] = 0
        out[base + 1] = _MONK_HOVER_MOVING_CD
        out[base + 2] = 0xFF
        out[base + 3] = 0xFF
        out[base + 16] = 0xFF
        out[base + 17] = 0
        out[base + 14] = 0
        _buf_set_i16_le(out, base + 18, 0)
        _buf_set_i16_le(out, base + 20, 0)
        ei += 1
    return out, _MONK_ATTACK_NATIVE_STRIDE, count


def _ensure_monk_attack_c_count(monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count, enemy_count):
    if monk_attack_c_buf is None or monk_attack_c_stride < _MONK_ATTACK_NATIVE_STRIDE:
        monk_attack_c_buf = bytearray()
        monk_attack_c_stride = _MONK_ATTACK_NATIVE_STRIDE
        monk_attack_c_count = 0
    while monk_attack_c_count < int(enemy_count):
        base = len(monk_attack_c_buf)
        monk_attack_c_buf.extend(bytearray(monk_attack_c_stride))
        monk_attack_c_buf[base + 0] = 0
        monk_attack_c_buf[base + 1] = _MONK_HOVER_MOVING_CD
        monk_attack_c_buf[base + 2] = 0xFF
        monk_attack_c_buf[base + 3] = 0xFF
        monk_attack_c_buf[base + 12] = 0
        monk_attack_c_buf[base + 13] = 0
        monk_attack_c_buf[base + 14] = 0
        monk_attack_c_buf[base + 16] = 0xFF
        monk_attack_c_buf[base + 17] = 0
        _buf_set_i16_le(monk_attack_c_buf, base + 18, 0)
        _buf_set_i16_le(monk_attack_c_buf, base + 20, 0)
        monk_attack_c_count += 1
    return monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count


def _monk_attack_c_has_active(monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count):
    if monk_attack_c_buf is None or monk_attack_c_stride < _MONK_ATTACK_NATIVE_STRIDE:
        return False
    stride = int(monk_attack_c_stride)
    ei = 0
    while ei < int(monk_attack_c_count):
        base = ei * stride
        if base >= 0 and (base + _MONK_ATTACK_NATIVE_STRIDE) <= len(monk_attack_c_buf):
            if int(monk_attack_c_buf[base + 0]) != 0 or int(monk_attack_c_buf[base + 17]) != 0:
                return True
        ei += 1
    return False


def _native_monk_attack_ready():
    return bool(_lgfx is not None and hasattr(_lgfx, "update_monk_attack_native"))


def _update_monk_attack_native(monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count, enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows_c_count, monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count, monk_orb_c_buf, monk_orb_c_stride, monk_orb_c_count, player_x=0, player_w=16, player_y=0, player_h=16, camera_x=0, view_w=320, view_h=240):
    if not _native_monk_attack_ready():
        return False
    if monk_attack_c_buf is None or enemy_rows_c_buf is None or monk_hover_c_buf is None or monk_orb_c_buf is None:
        return False
    speed_px = int(getattr(config, "MONK_ATTACK_SPEED", 6) or 6)
    if speed_px < 1:
        speed_px = 1
    try:
        _lgfx.update_monk_attack_native(
            monk_attack_c_buf,
            monk_attack_c_stride,
            monk_attack_c_count,
            enemy_rows_c_buf,
            enemy_rows_c_stride,
            enemy_rows_c_count,
            monk_hover_c_buf,
            monk_hover_c_stride,
            monk_hover_c_count,
            monk_orb_c_buf,
            monk_orb_c_stride,
            monk_orb_c_count,
            _monk_attack_enabled(),
            speed_px,
            int(player_x),
            int(player_w),
            int(player_y),
            int(player_h),
            int(camera_x),
            int(view_w),
            int(view_h),
        )
        return True
    except Exception as exc:
        print("MONK_ATTACK_NATIVE_FAIL %r" % (exc,))
        return False


def _build_monk_attack_states(enemy_rows, enemy_meta=None):
    out = []
    if not enemy_rows:
        return out
    ei = 0
    while ei < len(enemy_rows):
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        if enemy_type == "monk":
            out.append({
                "active": 0,
                "phase": "",
                "timer": 0,
                "slot_a": -1,
                "slot_b": -1,
                "left_edge_x": 0,
                "right_edge_x": 0,
                "left_floor_y": 0,
                "right_floor_y": 0,
                "left_lift": 0,
                "right_lift": 16,
                "body_anchor_x": 0,
                "body_anchor_y": 0,
                "prev_cd": 255,
            })
        else:
            out.append(None)
        ei += 1
    return out


def _build_monk_intro_states(monk_encounters):
    out = []
    if not monk_encounters:
        return out
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is not None:
            state_obj = {
                "state": _MONK_INTRO_STATE_IDLE,
                "armed": 0,
                "body_target_x": 0,
                "body_target_y": 0,
                "body_target_bottom_y": 0,
            }
            encounter["intro_state"] = state_obj
            out.append(state_obj)
        else:
            out.append(None)
        ei += 1
    return out


def _native_monk_intro_ready():
    return bool(_lgfx is not None and hasattr(_lgfx, "update_monk_intro_native"))


def _sync_monk_intro_native_from_encounter(buf, intro_i, encounter, intro_state):
    if buf is None or encounter is None or intro_state is None:
        return False
    base = int(intro_i) * _MONK_INTRO_NATIVE_STRIDE
    if base < 0 or (base + _MONK_INTRO_NATIVE_STRIDE) > len(buf):
        return False
    template_row = encounter.get("template_row") or [0, 0, 48, 64]
    body_w = int(template_row[2])
    body_h = int(template_row[3])
    buf[base + 0] = int(intro_state.get("state", _MONK_INTRO_STATE_IDLE) or _MONK_INTRO_STATE_IDLE) & 0xFF
    buf[base + 1] = int(intro_state.get("armed", 0) or 0) & 0xFF
    _buf_set_i16_le(buf, base + 4, int(encounter.get("body_x", 0) or 0))
    _buf_set_i16_le(buf, base + 6, int(encounter.get("body_y", 0) or 0))
    _buf_set_i16_le(buf, base + 8, body_w)
    _buf_set_i16_le(buf, base + 10, body_h)
    _buf_set_i16_le(buf, base + 12, int(intro_state.get("body_target_x", encounter.get("body_x", 0)) or encounter.get("body_x", 0)))
    _buf_set_i16_le(buf, base + 14, int(intro_state.get("body_target_y", encounter.get("body_y", 0)) or encounter.get("body_y", 0)))
    _buf_set_i16_le(buf, base + 16, int(intro_state.get("body_target_bottom_y", int(encounter.get("body_y", 0) or 0) + body_h) or (int(encounter.get("body_y", 0) or 0) + body_h)))
    _buf_set_u16_le(buf, base + 18, int(encounter.get("anim_counter", 0) or 0))
    return True


def _sync_monk_intro_native_to_encounter(buf, intro_i, encounter, intro_state):
    if buf is None or encounter is None or intro_state is None:
        return False
    base = int(intro_i) * _MONK_INTRO_NATIVE_STRIDE
    if base < 0 or (base + _MONK_INTRO_NATIVE_STRIDE) > len(buf):
        return False
    state_now = int(buf[base + 0])
    encounter["body_x"] = _buf_get_i16_le(buf, base + 4)
    encounter["body_y"] = _buf_get_i16_le(buf, base + 6)
    encounter["anim_counter"] = _buf_get_u16_le(buf, base + 18)
    encounter_orbs = encounter.get("orbs") or []
    encounter_orb_states = encounter.get("orb_states") or []
    si = 0
    while si < len(encounter_orbs) and si < _MONK_ORB_COUNT:
        orb_base = base + _MONK_INTRO_NATIVE_ORB_BASE + (si * _MONK_INTRO_NATIVE_ORB_STRIDE)
        orb_x = _buf_get_i16_le(buf, orb_base + 0)
        orb_y = _buf_get_i16_le(buf, orb_base + 2)
        orb = encounter_orbs[si]
        orb["x"] = orb_x
        orb["y"] = orb_y
        if si < len(encounter_orb_states):
            orb_state = encounter_orb_states[si]
            if orb_state is not None:
                orb_state["mode"] = _MONK_ORB_MODE_SCRIPTED_INTRO
                orb_state["script_x"] = orb_x
                orb_state["script_y"] = orb_y
                orb_state["detached_x"] = orb_x
                orb_state["detached_y"] = orb_y
        si += 1
    if state_now == _MONK_INTRO_STATE_DONE:
        intro_state["state"] = _MONK_INTRO_STATE_DONE
    return True


def _update_monk_intro_native_one(monk_intro_states, monk_encounters, intro_i, drop_speed, monk_frame_w, monk_frame_h):
    if not _native_monk_intro_ready():
        return False
    if intro_i < 0 or intro_i >= len(monk_intro_states) or intro_i >= len(monk_encounters):
        return False
    intro_state = monk_intro_states[intro_i]
    encounter = monk_encounters[intro_i]
    if intro_state is None or encounter is None:
        return False
    buf = encounter.get("intro_native_buf") or None
    if buf is None or len(buf) < _MONK_INTRO_NATIVE_STRIDE:
        buf = bytearray(_MONK_INTRO_NATIVE_STRIDE)
        encounter["intro_native_buf"] = buf
    if not _sync_monk_intro_native_from_encounter(buf, 0, encounter, intro_state):
        return False
    try:
        _lgfx.update_monk_intro_native(
            buf,
            _MONK_INTRO_NATIVE_STRIDE,
            1,
            int(drop_speed),
            int(monk_frame_w),
            int(monk_frame_h),
            _MONK_ORB_COUNT,
        )
    except Exception as exc:
        if _runtime_verbose_enabled():
            print("MONK_INTRO_NATIVE_FALLBACK %r" % (exc,))
        return False
    return _sync_monk_intro_native_to_encounter(buf, 0, encounter, intro_state)


def _apply_monk_intro_initial_visibility(enemy_rows, enemy_rows_initial, enemy_meta=None):
    if not _monk_intro_enabled() or not enemy_rows:
        return
    ei = 0
    while ei < len(enemy_rows):
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        if enemy_type == "monk":
            enemy_rows[ei][4] = 0
            if enemy_rows_initial is not None and ei < len(enemy_rows_initial):
                enemy_rows_initial[ei][4] = 0
        ei += 1


def _start_monk_intro(encounter_i, intro_state, monk_encounters, camera_x, view_w):
    if intro_state is None or encounter_i < 0 or encounter_i >= len(monk_encounters):
        return False
    encounter = monk_encounters[encounter_i]
    if encounter is None:
        return False
    if not int(intro_state.get("armed", 0) or 0):
        return False
    template_row = encounter.get("template_row") or None
    if template_row is None:
        return False
    body_w = int(template_row[2])
    body_h = int(template_row[3])
    body_target_x = int(template_row[0])
    center_target_y = int(getattr(config, "MONK_INTRO_TARGET_Y", 72) or 72)
    body_target_bottom_y = center_target_y + body_h
    intro_start_offset_y = int(getattr(config, "MONK_INTRO_START_OFFSET_Y", 96) or 96)
    monk_frame_w = int(getattr(config, "ENEMY_MONK_FRAME_W", 32) or 32)
    monk_frame_h = int(getattr(config, "ENEMY_MONK_FRAME_H", 48) or 48)
    if intro_start_offset_y < 0:
        intro_start_offset_y = 0
    encounter["body_x"] = body_target_x
    encounter["body_y"] = -intro_start_offset_y
    encounter["body_target_x"] = body_target_x
    encounter["body_target_y"] = center_target_y
    intro_state["body_target_x"] = body_target_x
    intro_state["body_target_y"] = center_target_y
    intro_state["body_target_bottom_y"] = body_target_bottom_y
    encounter["anim_counter"] = 0
    orb_states = _build_monk_orb_states([template_row], [encounter.get("template_meta") or {}])
    encounter_orb_states = orb_states[0] if orb_states else []
    encounter_orbs = []
    si = 0
    while si < _MONK_ORB_COUNT:
        orb_state = encounter_orb_states[si] if si < len(encounter_orb_states) else None
        orb_x, orb_y = _monk_orb_slot_world_pos(body_target_x, -intro_start_offset_y, body_w, body_h, int(encounter.get("anim_counter", 0) or 0), si, monk_frame_w, monk_frame_h)
        if orb_state is not None:
            orb_state["mode"] = _MONK_ORB_MODE_SCRIPTED_INTRO
            orb_state["script_x"] = orb_x
            orb_state["script_y"] = orb_y
            orb_state["detached_x"] = orb_x
            orb_state["detached_y"] = orb_y
        encounter_orbs.append({
            "x": orb_x,
            "y": orb_y,
        })
        si += 1
    encounter["orbs"] = encounter_orbs
    encounter["orb_states"] = encounter_orb_states
    intro_state["state"] = _MONK_INTRO_STATE_DROPPING
    intro_state["armed"] = 0
    encounter["state"] = _MONK_ENCOUNTER_STATE_INTRO
    if _runtime_verbose_enabled():
        print("MONK_INTRO_START encounter=%d x=%d y=%d" % (encounter_i, body_target_x, center_target_y))
    return True


def _update_monk_intro_states(monk_intro_states, monk_encounters, camera_x, view_w):
    if not monk_intro_states or not monk_encounters:
        return False
    if not _monk_intro_enabled():
        return False
    intro_changed = False
    ei = 0
    while ei < len(monk_intro_states) and ei < len(monk_encounters):
        intro_state = monk_intro_states[ei]
        encounter = monk_encounters[ei]
        if intro_state is None or encounter is None:
            ei += 1
            continue
        if intro_state.get("state") == _MONK_INTRO_STATE_IDLE:
            if _start_monk_intro(ei, intro_state, monk_encounters, camera_x, view_w):
                intro_changed = True
        if intro_state.get("state") == _MONK_INTRO_STATE_DROPPING:
            drop_speed = int(getattr(config, "MONK_INTRO_DROP_SPEED", 6) or 6)
            monk_frame_w = int(getattr(config, "ENEMY_MONK_FRAME_W", 32) or 32)
            monk_frame_h = int(getattr(config, "ENEMY_MONK_FRAME_H", 48) or 48)
            if drop_speed < 1:
                drop_speed = 1
            native_updated = _update_monk_intro_native_one(monk_intro_states, monk_encounters, ei, drop_speed, monk_frame_w, monk_frame_h)
            if not native_updated:
                template_row = encounter.get("template_row") or [0, 0, 48, 64]
                body_w = int(template_row[2])
                body_h = int(template_row[3])
                body_target_x = int(intro_state.get("body_target_x", encounter.get("body_x", 0)) or encounter.get("body_x", 0))
                body_y_now = int(encounter.get("body_y", 0) or 0)
                body_bottom_y = body_y_now + body_h
                body_bottom_y = _move_toward_scalar(body_bottom_y, intro_state.get("body_target_bottom_y", body_bottom_y), drop_speed)
                encounter["body_y"] = body_bottom_y - body_h
                encounter["body_x"] = body_target_x
                encounter_orbs = encounter.get("orbs") or []
                encounter_orb_states = encounter.get("orb_states") or []
                encounter["anim_counter"] = int(encounter.get("anim_counter", 0) or 0) + 1
                si = 0
                while si < len(encounter_orbs):
                    orb = encounter_orbs[si]
                    orb_state = encounter_orb_states[si] if si < len(encounter_orb_states) else None
                    orb_x, orb_y = _monk_orb_slot_world_pos(
                        int(encounter.get("body_x", 0) or 0),
                        int(encounter.get("body_y", 0) or 0),
                        body_w,
                        body_h,
                        int(encounter.get("anim_counter", 0) or 0),
                        si,
                        monk_frame_w,
                        monk_frame_h,
                    )
                    orb["x"] = orb_x
                    orb["y"] = orb_y
                    if orb_state is not None:
                        orb_state["mode"] = _MONK_ORB_MODE_SCRIPTED_INTRO
                        orb_state["script_x"] = orb_x
                        orb_state["script_y"] = orb_y
                        orb_state["detached_x"] = orb_x
                        orb_state["detached_y"] = orb_y
                    si += 1
            body_done = int(encounter.get("body_y", 0) or 0) == int(intro_state.get("body_target_y", 0) or 0)
            intro_changed = True
            if body_done:
                intro_state["state"] = _MONK_INTRO_STATE_DONE
                if _runtime_verbose_enabled():
                    print("MONK_INTRO_DONE encounter=%d x=%d y=%d" % (ei, int(encounter.get("body_x", 0) or 0), int(encounter.get("body_y", 0) or 0)))
        ei += 1
    return intro_changed


def _instantiate_live_monk_from_encounter(encounter, enemy_rows, enemy_meta, enemy_states, enemy_rows_c_buf, enemy_rows_c_stride, monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count, monk_orb_states, monk_orb_c_buf=None, monk_orb_c_stride=0):
    if encounter is None:
        return -1
    template_row = encounter.get("template_row") or None
    template_meta = encounter.get("template_meta") or None
    if template_row is None or template_meta is None:
        return -1
    live_enemy_i = int(encounter.get("live_enemy_i", -1) or -1)
    new_live = not (live_enemy_i >= 0 and live_enemy_i < len(enemy_rows))
    if new_live:
        live_row = list(template_row)
        enemy_rows.append(live_row)
        enemy_meta.append(dict(template_meta))
        live_enemy_i = len(enemy_rows) - 1
    else:
        live_row = enemy_rows[live_enemy_i]
        if live_enemy_i < len(enemy_meta):
            enemy_meta[live_enemy_i] = dict(template_meta)
    live_row[0] = int(encounter.get("body_x", live_row[0]) or live_row[0])
    live_row[1] = int(encounter.get("body_y", live_row[1]) or live_row[1])
    live_row[2] = int(template_row[2])
    live_row[3] = int(template_row[3])
    live_row[4] = 1
    if hasattr(enemy_states, "_count") and hasattr(enemy_states, "_buf"):
        if new_live:
            enemy_states._buf.extend(bytearray(_ENEMY_STATE_STRIDE))
            enemy_states._count += 1
        if live_enemy_i < len(enemy_states):
            _reset_enemy_state(enemy_states[live_enemy_i], enemy_meta[live_enemy_i])
            enemy_states[live_enemy_i]["anim_counter"] = int(encounter.get("anim_counter", 0) or 0)
    if enemy_rows_c_buf is not None:
        if new_live:
            enemy_rows_c_buf.extend(bytearray(enemy_rows_c_stride))
        _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
        encounter["enemy_rows_c_count"] = len(enemy_rows)
    if monk_hover_c_buf is not None:
        if new_live:
            monk_hover_c_buf.extend(bytearray(monk_hover_c_stride))
        base = live_enemy_i * int(monk_hover_c_stride)
        if base >= 0 and (base + int(monk_hover_c_stride)) <= len(monk_hover_c_buf):
            hover_min_x = int(getattr(config, "MONK_HOVER_MIN_X", 1616) or 1616)
            hover_max_x = int(getattr(config, "MONK_HOVER_MAX_X", 1856) or 1856)
            hover_base_y = int(getattr(config, "MONK_HOVER_BASE_Y", 112) or 112)
            hover_retarget_frames = int(getattr(config, "MONK_HOVER_RETARGET_FRAMES", 30) or 30)
            if hover_retarget_frames < 1:
                hover_retarget_frames = 1
            hover_target_x = hover_min_x + ((hover_max_x - hover_min_x) // 2)
            if hover_target_x < hover_min_x:
                hover_target_x = hover_min_x
            if hover_target_x > hover_max_x:
                hover_target_x = hover_max_x
            _buf_set_i16_le(monk_hover_c_buf, base + 0, hover_target_x)
            _buf_set_i16_le(monk_hover_c_buf, base + 2, hover_base_y)
            _buf_set_i16_le(monk_hover_c_buf, base + 4, hover_base_y)
            _buf_set_i16_le(monk_hover_c_buf, base + 6, 0)
            monk_hover_c_buf[base + 8] = hover_retarget_frames & 0xFF
            _buf_set_i16_le(monk_hover_c_buf, base + 9, int(getattr(config, "MONK_HOVER_SPEED_Q8", 512) or 512))
            encounter["monk_hover_c_count"] = live_enemy_i + 1
    encounter_orb_states = encounter.get("orb_states") or []
    if encounter_orb_states:
        si = 0
        while si < len(encounter_orb_states):
            orb_state = encounter_orb_states[si]
            if orb_state is not None:
                orb_state["mode"] = "orbit"
                orb_state["detached_x"] = int(orb_state.get("script_x", 0) or 0)
                orb_state["detached_y"] = int(orb_state.get("script_y", 0) or 0)
            si += 1
        while len(monk_orb_states) <= live_enemy_i:
            monk_orb_states.append(None)
        monk_orb_states[live_enemy_i] = encounter_orb_states
    else:
        slot_states = _build_monk_orb_states([live_row], [enemy_meta[live_enemy_i]])
        while len(monk_orb_states) <= live_enemy_i:
            monk_orb_states.append(None)
        monk_orb_states[live_enemy_i] = slot_states[0] if slot_states else None
    if monk_orb_c_buf is not None and monk_orb_c_stride >= _MONK_ORB_NATIVE_STRIDE and live_enemy_i < len(monk_orb_states):
        live_slots = monk_orb_states[live_enemy_i]
        si = 0
        while live_slots is not None and si < len(live_slots) and si < _MONK_ORB_COUNT:
            _sync_monk_orb_state_to_c(monk_orb_c_buf, monk_orb_c_stride, live_enemy_i, si, live_slots[si])
            si += 1
    encounter["live_enemy_i"] = live_enemy_i
    if _runtime_verbose_enabled():
        print("MONK_LIVE_INSTANTIATED idx=%d x=%d y=%d" % (live_enemy_i, live_row[0], live_row[1]))
    return live_enemy_i


def _reset_monk_for_respawn_reintro(enemy_rt):
    if enemy_rt.get("monk_defeated"):
        return False
    monk_encounters = enemy_rt.get("monk_encounters") or []
    if not monk_encounters:
        return False
    monk_intro_states = enemy_rt.get("monk_intro_states") or []
    enemy_rows = enemy_rt.get("enemy_rows") or []
    enemy_meta = enemy_rt.get("enemy_meta") or []
    enemy_states = enemy_rt.get("enemy_states")
    enemy_rows_c_buf = enemy_rt.get("enemy_rows_c_buf")
    enemy_rows_c_stride = int(enemy_rt.get("enemy_rows_c_stride", 0) or 0)
    monk_orb_states = enemy_rt.get("monk_orb_states") or []
    monk_orb_c_buf = enemy_rt.get("monk_orb_c_buf")
    monk_orb_c_stride = int(enemy_rt.get("monk_orb_c_stride", 0) or 0)
    monk_attack_c_buf = enemy_rt.get("monk_attack_c_buf")
    monk_attack_c_stride = int(enemy_rt.get("monk_attack_c_stride", 0) or 0)
    did_reset = False
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is not None:
            did_reset = True
            live_enemy_i = int(encounter.get("live_enemy_i", -1) or -1)
            if live_enemy_i >= 0 and live_enemy_i < len(enemy_rows):
                template_row = encounter.get("template_row") or enemy_rows[live_enemy_i]
                enemy_rows[live_enemy_i][0] = int(template_row[0])
                enemy_rows[live_enemy_i][1] = int(template_row[1])
                enemy_rows[live_enemy_i][4] = 0
                if enemy_states is not None and live_enemy_i < len(enemy_states):
                    meta = enemy_meta[live_enemy_i] if live_enemy_i < len(enemy_meta) else None
                    _reset_enemy_state(enemy_states[live_enemy_i], meta)
                if live_enemy_i < len(monk_orb_states):
                    monk_orb_states[live_enemy_i] = None
                if monk_orb_c_buf is not None and monk_orb_c_stride >= _MONK_ORB_NATIVE_STRIDE:
                    si = 0
                    while si < _MONK_ORB_COUNT:
                        base = ((live_enemy_i * _MONK_ORB_COUNT) + si) * monk_orb_c_stride
                        if base >= 0 and (base + _MONK_ORB_NATIVE_STRIDE) <= len(monk_orb_c_buf):
                            monk_orb_c_buf[base + 0] = _MONK_ORB_NATIVE_MODE_UNUSED
                            monk_orb_c_buf[base + 1] = si & 0xFF
                        si += 1
                if monk_attack_c_buf is not None and monk_attack_c_stride >= _MONK_ATTACK_NATIVE_STRIDE:
                    base = live_enemy_i * monk_attack_c_stride
                    if base >= 0 and (base + _MONK_ATTACK_NATIVE_STRIDE) <= len(monk_attack_c_buf):
                        monk_attack_c_buf[base + 0] = 0
                        monk_attack_c_buf[base + 1] = _MONK_HOVER_MOVING_CD
                        monk_attack_c_buf[base + 2] = 0xFF
                        monk_attack_c_buf[base + 3] = 0xFF
                        monk_attack_c_buf[base + 14] = 0
                        monk_attack_c_buf[base + 16] = 0xFF
                        monk_attack_c_buf[base + 17] = 0
                        _buf_set_i16_le(monk_attack_c_buf, base + 18, 0)
                        _buf_set_i16_le(monk_attack_c_buf, base + 20, 0)
            else:
                encounter["live_enemy_i"] = -1
            encounter["state"] = _MONK_ENCOUNTER_STATE_INACTIVE
            encounter["body_x"] = 0
            encounter["body_y"] = 0
            encounter["body_target_x"] = 0
            encounter["body_target_y"] = 0
            encounter["body_target_bottom_y"] = 0
            encounter["anim_counter"] = 0
            encounter["orbs"] = []
            encounter["orb_states"] = []
            encounter["enemy_rows_c_count"] = 0
            encounter["monk_hover_c_count"] = 0
            if "intro_native_buf" in encounter:
                del encounter["intro_native_buf"]
            intro_state = monk_intro_states[ei] if (monk_intro_states is not None and ei < len(monk_intro_states)) else None
            if intro_state is not None:
                intro_state["state"] = _MONK_INTRO_STATE_IDLE
                intro_state["armed"] = 1
                intro_state["body_target_x"] = 0
                intro_state["body_target_y"] = 0
                intro_state["body_target_bottom_y"] = 0
        ei += 1
    if did_reset and enemy_rows_c_buf is not None:
        _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
    return did_reset


def _monk_live_index_from_rt(enemy_rt):
    monk_encounters = enemy_rt.get("monk_encounters") or []
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is not None:
            live_enemy_i = int(encounter.get("live_enemy_i", -1) or -1)
            if live_enemy_i >= 0:
                return live_enemy_i
        ei += 1
    enemy_meta = enemy_rt.get("enemy_meta") or []
    ei = 0
    while ei < len(enemy_meta):
        meta = enemy_meta[ei]
        if meta is not None and str(meta.get("type", "bow") or "bow") == "monk":
            return ei
        ei += 1
    return -1


def _apply_monk_defeated_runtime(enemy_rt):
    live_enemy_i = _monk_live_index_from_rt(enemy_rt)
    enemy_rows = enemy_rt.get("enemy_rows") or []
    enemy_rows_c_buf = enemy_rt.get("enemy_rows_c_buf")
    enemy_rows_c_stride = int(enemy_rt.get("enemy_rows_c_stride", 0) or 0)
    if live_enemy_i >= 0 and live_enemy_i < len(enemy_rows):
        enemy_rows[live_enemy_i][4] = 0
        enemy_rows[live_enemy_i][5] = 0
    if enemy_rows_c_buf is not None and enemy_rows_c_stride >= _ENEMY_ROW_STRIDE and live_enemy_i >= 0:
        base = live_enemy_i * enemy_rows_c_stride
        if base >= 0 and (base + _ENEMY_ROW_STRIDE) <= len(enemy_rows_c_buf):
            enemy_rows_c_buf[base + 8] = 0
            enemy_rows_c_buf[base + 9] = 0
    monk_encounters = enemy_rt.get("monk_encounters") or []
    monk_intro_states = enemy_rt.get("monk_intro_states") or []
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is not None:
            encounter["state"] = _MONK_ENCOUNTER_STATE_DEFEATED
            encounter["orbs"] = []
            encounter["orb_states"] = []
        if ei < len(monk_intro_states):
            intro_state = monk_intro_states[ei]
            if intro_state is not None:
                intro_state["state"] = _MONK_INTRO_STATE_DONE
                intro_state["armed"] = 0
        ei += 1
    return live_enemy_i >= 0


def _update_monk_defeated_state(enemy_rt):
    if enemy_rt.get("monk_defeated"):
        return True
    live_enemy_i = _monk_live_index_from_rt(enemy_rt)
    if live_enemy_i < 0:
        return False
    monk_attack_c_buf = enemy_rt.get("monk_attack_c_buf")
    monk_attack_c_stride = int(enemy_rt.get("monk_attack_c_stride", 0) or 0)
    monk_attack_c_count = int(enemy_rt.get("monk_attack_c_count", 0) or 0)
    if monk_attack_c_buf is None or monk_attack_c_stride < _MONK_ATTACK_NATIVE_STRIDE or live_enemy_i >= monk_attack_c_count:
        return False
    abase = live_enemy_i * monk_attack_c_stride
    if abase < 0 or (abase + _MONK_ATTACK_NATIVE_STRIDE) > len(monk_attack_c_buf):
        return False
    if int(monk_attack_c_buf[abase + 0]) != _MONK_ATTACK_NATIVE_FINAL_PHASE_DEATH:
        return False
    enemy_rows_c_buf = enemy_rt.get("enemy_rows_c_buf")
    enemy_rows_c_stride = int(enemy_rt.get("enemy_rows_c_stride", 0) or 0)
    if enemy_rows_c_buf is None or enemy_rows_c_stride < _ENEMY_ROW_STRIDE:
        return False
    ebase = live_enemy_i * enemy_rows_c_stride
    if ebase < 0 or (ebase + _ENEMY_ROW_STRIDE) > len(enemy_rows_c_buf):
        return False
    if int(enemy_rows_c_buf[ebase + 8]) != 0:
        return False
    enemy_rt["monk_defeated"] = True
    _apply_monk_defeated_runtime(enemy_rt)
    print("MONK_DEFEATED_PERSISTENT idx=%d" % live_enemy_i)
    return True


def _update_monk_encounters(monk_encounters, enemy_rows, enemy_meta, enemy_states, enemy_rows_c_buf, enemy_rows_c_stride, monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count, monk_orb_states, camera_x, view_w, monk_orb_c_buf=None, monk_orb_c_stride=0):
    if not monk_encounters:
        return
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is None:
            ei += 1
            continue
        state = str(encounter.get("state", _MONK_ENCOUNTER_STATE_INACTIVE) or _MONK_ENCOUNTER_STATE_INACTIVE)
        if state == _MONK_ENCOUNTER_STATE_INACTIVE:
            if int(camera_x) >= 1600:
                encounter["state"] = _MONK_ENCOUNTER_STATE_INTRO
                if _runtime_verbose_enabled():
                    print("MONK_ENCOUNTER_STATE=intro_drop")
        elif state == _MONK_ENCOUNTER_STATE_INTRO:
            intro_state = encounter.get("intro_state") or None
            intro_done = False
            if _runtime_verbose_enabled() and intro_state is not None and int(intro_state.get("state", _MONK_INTRO_STATE_IDLE) or _MONK_INTRO_STATE_IDLE) == _MONK_INTRO_STATE_DROPPING:
                orbs = encounter.get("orbs") or []
                if orbs:
                    first_orb = orbs[0]
                    print(
                        "MONK_INTRO_DBG body=%d,%d target=%d,%d orb0=%d,%d orb0t=%d,%d"
                        % (
                            int(encounter.get("body_x", 0) or 0),
                            int(encounter.get("body_y", 0) or 0),
                            int(encounter.get("body_target_x", 0) or 0),
                            int(encounter.get("body_target_y", 0) or 0),
                            int(first_orb.get("x", 0) or 0),
                            int(first_orb.get("y", 0) or 0),
                            int(first_orb.get("target_x", 0) or 0),
                            int(first_orb.get("target_y", 0) or 0),
                        )
                    )
            if intro_state is not None:
                intro_done = str(intro_state.get("state", "") or "") == str(_MONK_INTRO_STATE_DONE)
            else:
                body_x = int(encounter.get("body_x", 0) or 0)
                body_y = int(encounter.get("body_y", 0) or 0)
                target_x = int(encounter.get("body_target_x", body_x) or body_x)
                target_y = int(encounter.get("body_target_y", body_y) or body_y)
                intro_done = (body_x == target_x) and (body_y == target_y)
            if intro_done:
                live_enemy_i = _instantiate_live_monk_from_encounter(
                    encounter,
                    enemy_rows,
                    enemy_meta,
                    enemy_states,
                    enemy_rows_c_buf,
                    enemy_rows_c_stride,
                    monk_hover_c_buf,
                    monk_hover_c_stride,
                    monk_hover_c_count,
                    monk_orb_states,
                    monk_orb_c_buf,
                    monk_orb_c_stride,
                )
                if live_enemy_i >= 0:
                    encounter["state"] = _MONK_ENCOUNTER_STATE_LIVE
                    if _runtime_verbose_enabled():
                        print("MONK_ENCOUNTER_STATE=live")
        ei += 1


def _move_toward_scalar(curr_v, target_v, speed_px):
    curr_i = int(curr_v)
    target_i = int(target_v)
    step = int(speed_px)
    if step < 1:
        step = 1
    delta = target_i - curr_i
    if delta > 0:
        curr_i += delta if delta < step else step
    elif delta < 0:
        delta = -delta
        curr_i -= delta if delta < step else step
    return curr_i


def _phase_frames_from_distance(max_delta, speed_px):
    speed_i = int(speed_px)
    if speed_i < 1:
        speed_i = 1
    delta_i = int(max_delta)
    if delta_i < 1:
        delta_i = 1
    return (delta_i + speed_i - 1) // speed_i


def _lerp_int(start_v, target_v, step_i, step_total):
    start_i = int(start_v)
    target_i = int(target_v)
    total_i = int(step_total)
    if total_i <= 0:
        return target_i
    step_now = int(step_i)
    if step_now < 0:
        step_now = 0
    if step_now > total_i:
        step_now = total_i
    delta = target_i - start_i
    return start_i + ((delta * step_now) // total_i)


def _monk_entered_waypoint_interval(prev_cd, current_cd):
    return int(prev_cd) == _MONK_HOVER_MOVING_CD and _MONK_HOVER_INTERVAL_MIN_CD <= int(current_cd) < _MONK_HOVER_MOVING_CD


def _begin_monk_attack_phase(attack_state, phase_name, orb_a, orb_b, ax, ay, bx, by, speed_px):
    ax0 = int(orb_a.get("script_x", 0) or 0)
    ay0 = int(orb_a.get("script_y", 0) or 0)
    bx0 = int(orb_b.get("script_x", 0) or 0)
    by0 = int(orb_b.get("script_y", 0) or 0)
    max_delta = 0
    for delta in (
        abs(int(ax) - ax0),
        abs(int(ay) - ay0),
        abs(int(bx) - bx0),
        abs(int(by) - by0),
    ):
        if delta > max_delta:
            max_delta = delta
    phase_frames = _phase_frames_from_distance(max_delta, speed_px)
    attack_state["phase"] = phase_name
    attack_state["timer"] = phase_frames
    attack_state["phase_total"] = phase_frames
    attack_state["a_start_x"] = ax0
    attack_state["a_start_y"] = ay0
    attack_state["a_target_x"] = int(ax)
    attack_state["a_target_y"] = int(ay)
    attack_state["b_start_x"] = bx0
    attack_state["b_start_y"] = by0
    attack_state["b_target_x"] = int(bx)
    attack_state["b_target_y"] = int(by)


def _find_floor_y_for_orb(world_x, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, map_h_px):
    probe_x = int(world_x)
    max_probe_y = int(map_h_px) - _MONK_ORB_H
    if max_probe_y < 0:
        max_probe_y = 0
    probe_y = 0
    while probe_y <= max_probe_y:
        if _aabb_collides_world(probe_x, probe_y + 1, _MONK_ORB_W, _MONK_ORB_H, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
            return probe_y
        probe_y += 1
    return max_probe_y


def _lock_monk_body_for_attack(enemy_i, attack_state, enemy_rows, monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count, enemy_rows_c_buf, enemy_rows_c_stride, enemy_meta):
    if attack_state is None or enemy_i < 0 or enemy_i >= len(enemy_rows):
        return False
    anchor_x = int(attack_state.get("body_anchor_x", enemy_rows[enemy_i][0]) or enemy_rows[enemy_i][0])
    anchor_y = int(attack_state.get("body_anchor_y", enemy_rows[enemy_i][1]) or enemy_rows[enemy_i][1])
    row = enemy_rows[enemy_i]
    changed = (int(row[0]) != anchor_x) or (int(row[1]) != anchor_y)
    row[0] = anchor_x
    row[1] = anchor_y
    if monk_hover_c_buf is not None and enemy_i < monk_hover_c_count:
        base = int(enemy_i) * int(monk_hover_c_stride)
        _buf_set_i16_le(monk_hover_c_buf, base + 0, anchor_x)
        _buf_set_i16_le(monk_hover_c_buf, base + 2, anchor_y)
        monk_hover_c_buf[base + 8] = _MONK_ATTACK_BODY_LOCK_CD & 0xFF
    if changed:
        _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
    return changed


def _pick_monk_attack_slots(slot_states):
    if not slot_states:
        return -1, -1
    orbit_slots = []
    si = 0
    while si < len(slot_states):
        orb_state = slot_states[si]
        mode = str(orb_state.get("mode", "orbit") or "orbit") if orb_state is not None else "orbit"
        if mode == "orbit":
            orbit_slots.append(si)
        si += 1
    if len(orbit_slots) < 2:
        return -1, -1
    slot_a = orbit_slots[0]
    slot_b = orbit_slots[2] if len(orbit_slots) > 2 else orbit_slots[1]
    return slot_a, slot_b


def _start_monk_attack(enemy_i, attack_state, enemy_rows, enemy_states, monk_orb_states, camera_x, view_w, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, map_h_px, monk_frame_w, monk_frame_h):
    if attack_state is None or enemy_i < 0 or enemy_i >= len(enemy_rows) or enemy_i >= len(enemy_states) or enemy_i >= len(monk_orb_states):
        return False
    slot_states = monk_orb_states[enemy_i]
    if not slot_states:
        return False
    slot_a, slot_b = _pick_monk_attack_slots(slot_states)
    if slot_a < 0 or slot_b < 0:
        return False
    row = enemy_rows[enemy_i]
    state = enemy_states[enemy_i]
    wx, wy, ow, oh, visible, _swappable = row
    if not visible:
        return False
    left_edge_x = int(camera_x)
    right_edge_x = int(camera_x) + int(view_w) - _MONK_ORB_W
    if right_edge_x < left_edge_x:
        right_edge_x = left_edge_x
    left_floor_y = _find_floor_y_for_orb(left_edge_x, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, map_h_px)
    right_floor_y = _find_floor_y_for_orb(right_edge_x, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, map_h_px)
    profile_idx = (int(state.get("anim_counter", 0) or 0) + enemy_i) % len(_MONK_ATTACK_PROFILE_LIFTS)
    left_lift, right_lift = _MONK_ATTACK_PROFILE_LIFTS[profile_idx]
    orb_a = slot_states[slot_a]
    orb_b = slot_states[slot_b]
    orb_a_x, orb_a_y = _monk_orb_current_world_pos(wx, wy, ow, oh, int(state.get("anim_counter", 0) or 0), slot_a, monk_frame_w, monk_frame_h, orb_a)
    orb_b_x, orb_b_y = _monk_orb_current_world_pos(wx, wy, ow, oh, int(state.get("anim_counter", 0) or 0), slot_b, monk_frame_w, monk_frame_h, orb_b)
    orb_a["mode"] = _MONK_ORB_MODE_SCRIPTED_ATTACK
    orb_a["script_x"] = orb_a_x
    orb_a["script_y"] = orb_a_y
    orb_b["mode"] = _MONK_ORB_MODE_SCRIPTED_ATTACK
    orb_b["script_x"] = orb_b_x
    orb_b["script_y"] = orb_b_y
    attack_state["active"] = 1
    attack_state["slot_a"] = slot_a
    attack_state["slot_b"] = slot_b
    attack_state["left_edge_x"] = left_edge_x
    attack_state["right_edge_x"] = right_edge_x
    attack_state["left_floor_y"] = left_floor_y
    attack_state["right_floor_y"] = right_floor_y
    attack_state["left_lift"] = left_lift
    attack_state["right_lift"] = right_lift
    attack_state["body_anchor_x"] = int(wx)
    attack_state["body_anchor_y"] = int(wy)
    _begin_monk_attack_phase(
        attack_state,
        _MONK_ATTACK_PHASE_SPLIT,
        orb_a,
        orb_b,
        left_edge_x,
        orb_a_y,
        right_edge_x,
        orb_b_y,
        _MONK_ATTACK_EDGE_SPEED,
    )
    return True


def _update_monk_attack_states(monk_attack_states, enemy_rows, enemy_states, monk_orb_states, enemy_meta, monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count, enemy_rows_c_buf, enemy_rows_c_stride, camera_x, view_w, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, map_h_px, monk_frame_w, monk_frame_h):
    if not monk_attack_states or not enemy_rows or not enemy_states or not monk_orb_states:
        return
    attack_enabled = _monk_attack_enabled()
    ei = 0
    while ei < len(monk_attack_states) and ei < len(enemy_rows):
        attack_state = monk_attack_states[ei]
        if attack_state is None:
            ei += 1
            continue
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        slot_states = monk_orb_states[ei] if ei < len(monk_orb_states) else None
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        if enemy_type != "monk" or state is None or not slot_states:
            ei += 1
            continue
        current_cd = _MONK_HOVER_MOVING_CD
        if monk_hover_c_buf is not None and ei < monk_hover_c_count:
            current_cd = int(monk_hover_c_buf[(int(ei) * int(monk_hover_c_stride)) + 8])
        if not attack_enabled:
            si = 0
            while si < len(slot_states):
                orb_state = slot_states[si]
                if orb_state is not None and str(orb_state.get("mode", "orbit") or "orbit") == _MONK_ORB_MODE_SCRIPTED_ATTACK:
                    orb_state["detached_x"] = int(orb_state.get("script_x", 0) or 0)
                    orb_state["detached_y"] = int(orb_state.get("script_y", 0) or 0)
                    orb_state["return_radius"] = _MONK_ORB_RADIUS
                    orb_state["mode"] = "detached"
                si += 1
            attack_state["active"] = 0
            attack_state["phase"] = ""
            attack_state["timer"] = 0
            attack_state["prev_cd"] = current_cd if monk_hover_c_buf is not None and ei < monk_hover_c_count else _MONK_HOVER_MOVING_CD
            ei += 1
            continue
        if attack_state.get("active"):
            _lock_monk_body_for_attack(ei, attack_state, enemy_rows, monk_hover_c_buf, monk_hover_c_stride, monk_hover_c_count, enemy_rows_c_buf, enemy_rows_c_stride, enemy_meta)
            slot_a = int(attack_state.get("slot_a", -1) or -1)
            slot_b = int(attack_state.get("slot_b", -1) or -1)
            if slot_a < 0 or slot_b < 0 or slot_a >= len(slot_states) or slot_b >= len(slot_states):
                attack_state["active"] = 0
                ei += 1
                continue
            orb_a = slot_states[slot_a]
            orb_b = slot_states[slot_b]
            phase = str(attack_state.get("phase", "") or "")
            if phase == _MONK_ATTACK_PHASE_SPLIT:
                phase_total = int(attack_state.get("phase_total", 0) or 0)
                phase_step = phase_total - int(attack_state.get("timer", 0) or 0)
                orb_a["script_x"] = _lerp_int(attack_state.get("a_start_x", 0), attack_state.get("a_target_x", 0), phase_step, phase_total)
                orb_a["script_y"] = _lerp_int(attack_state.get("a_start_y", 0), attack_state.get("a_target_y", 0), phase_step, phase_total)
                orb_b["script_x"] = _lerp_int(attack_state.get("b_start_x", 0), attack_state.get("b_target_x", 0), phase_step, phase_total)
                orb_b["script_y"] = _lerp_int(attack_state.get("b_start_y", 0), attack_state.get("b_target_y", 0), phase_step, phase_total)
                timer = int(attack_state.get("timer", 0) or 0)
                if timer > 0:
                    attack_state["timer"] = timer - 1
                else:
                    _begin_monk_attack_phase(
                        attack_state,
                        _MONK_ATTACK_PHASE_DROP,
                        orb_a,
                        orb_b,
                        int(attack_state.get("left_edge_x", 0) or 0),
                        int(attack_state.get("left_floor_y", 0) or 0) - int(attack_state.get("left_lift", 0) or 0),
                        int(attack_state.get("right_edge_x", 0) or 0),
                        int(attack_state.get("right_floor_y", 0) or 0) - int(attack_state.get("right_lift", 0) or 0),
                        _MONK_ATTACK_DROP_SPEED,
                    )
            elif phase == _MONK_ATTACK_PHASE_DROP:
                phase_total = int(attack_state.get("phase_total", 0) or 0)
                phase_step = phase_total - int(attack_state.get("timer", 0) or 0)
                orb_a["script_x"] = _lerp_int(attack_state.get("a_start_x", 0), attack_state.get("a_target_x", 0), phase_step, phase_total)
                orb_a["script_y"] = _lerp_int(attack_state.get("a_start_y", 0), attack_state.get("a_target_y", 0), phase_step, phase_total)
                orb_b["script_x"] = _lerp_int(attack_state.get("b_start_x", 0), attack_state.get("b_target_x", 0), phase_step, phase_total)
                orb_b["script_y"] = _lerp_int(attack_state.get("b_start_y", 0), attack_state.get("b_target_y", 0), phase_step, phase_total)
                timer = int(attack_state.get("timer", 0) or 0)
                if timer > 0:
                    attack_state["timer"] = timer - 1
                else:
                    _begin_monk_attack_phase(
                        attack_state,
                        _MONK_ATTACK_PHASE_SWEEP,
                        orb_a,
                        orb_b,
                        int(attack_state.get("right_edge_x", 0) or 0),
                        int(attack_state.get("left_floor_y", 0) or 0),
                        int(attack_state.get("left_edge_x", 0) or 0),
                        int(attack_state.get("right_floor_y", 0) or 0) - int(attack_state.get("right_lift", 0) or 0),
                        _MONK_ATTACK_SWEEP_SPEED,
                    )
            elif phase == _MONK_ATTACK_PHASE_SWEEP:
                phase_total = int(attack_state.get("phase_total", 0) or 0)
                phase_step = phase_total - int(attack_state.get("timer", 0) or 0)
                orb_a["script_x"] = _lerp_int(attack_state.get("a_start_x", 0), attack_state.get("a_target_x", 0), phase_step, phase_total)
                orb_a["script_y"] = _lerp_int(attack_state.get("a_start_y", 0), attack_state.get("a_target_y", 0), phase_step, phase_total)
                orb_b["script_x"] = _lerp_int(attack_state.get("b_start_x", 0), attack_state.get("b_target_x", 0), phase_step, phase_total)
                orb_b["script_y"] = _lerp_int(attack_state.get("b_start_y", 0), attack_state.get("b_target_y", 0), phase_step, phase_total)
                timer = int(attack_state.get("timer", 0) or 0)
                if timer > 0:
                    attack_state["timer"] = timer - 1
                else:
                    attack_state["phase"] = _MONK_ATTACK_PHASE_PAUSE
                    attack_state["timer"] = _MONK_ATTACK_PAUSE_FRAMES
            elif phase == _MONK_ATTACK_PHASE_PAUSE:
                timer = int(attack_state.get("timer", 0) or 0)
                if timer > 0:
                    attack_state["timer"] = timer - 1
                else:
                    orb_a["detached_x"] = int(orb_a.get("script_x", 0) or 0)
                    orb_a["detached_y"] = int(orb_a.get("script_y", 0) or 0)
                    orb_a["return_radius"] = _MONK_ORB_RADIUS
                    orb_a["mode"] = "detached"
                    orb_b["detached_x"] = int(orb_b.get("script_x", 0) or 0)
                    orb_b["detached_y"] = int(orb_b.get("script_y", 0) or 0)
                    orb_b["return_radius"] = _MONK_ORB_RADIUS
                    orb_b["mode"] = "detached"
                    attack_state["active"] = 0
                    attack_state["phase"] = ""
            attack_state["prev_cd"] = current_cd
            ei += 1
            continue
        prev_cd = int(attack_state.get("prev_cd", _MONK_HOVER_MOVING_CD) or _MONK_HOVER_MOVING_CD)
        if attack_enabled and _monk_entered_waypoint_interval(prev_cd, current_cd):
            _start_monk_attack(ei, attack_state, enemy_rows, enemy_states, monk_orb_states, camera_x, view_w, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, map_h_px, monk_frame_w, monk_frame_h)
        attack_state["prev_cd"] = current_cd
        ei += 1


def _step_monk_orb_state(orb_state, center_x, center_y, base_angle_rad):
    if orb_state is None:
        return "orbit"
    mode = str(orb_state.get("mode", "orbit") or "orbit")
    if mode == "orbit":
        return "orbit"
    if mode == "detached":
        detached_x = int(orb_state.get("detached_x", 0) or 0)
        detached_y = int(orb_state.get("detached_y", 0) or 0)
        radius_px, angle_rad = _quantize_monk_orb_polar(center_x, center_y, detached_x, detached_y)
        capture_eps = _MONK_ORB_CAPTURE_LINE_EPS
        if radius_px > _MONK_ORB_RADIUS:
            capture_eps += (radius_px - _MONK_ORB_RADIUS) // 12
        if capture_eps > 24:
            capture_eps = 24
        rel_x, rel_y = _monk_orb_rel_to_center(center_x, center_y, detached_x, detached_y)
        if math is not None:
            dir_x = math.cos(base_angle_rad)
            dir_y = math.sin(base_angle_rad)
            along = (float(rel_x) * dir_x) + (float(rel_y) * dir_y)
            perp = abs((float(rel_x) * dir_y) - (float(rel_y) * dir_x))
        else:
            base_angle_idx = int((base_angle_rad / _MONK_ORB_RAD_PER_IDX) + 0.5)
            angle_idx = int((angle_rad / _MONK_ORB_RAD_PER_IDX) + 0.5)
            angle_diff = _cyclic_idx_diff(base_angle_idx, angle_idx, _MONK_ORB_TABLE_SIZE)
            along = 1 if radius_px > 0 else 0
            perp = abs(angle_diff) * max(radius_px, 1) * _MONK_ORB_RAD_PER_IDX
        if along > 0 and perp <= capture_eps:
            orb_state["capture_lock"] = _MONK_ORB_CAPTURE_LOCK_FRAMES
            orb_state["mode"] = "captured_return"
            orb_state["return_radius"] = radius_px
            return "captured_return"
        return "detached"
    capture_lock = int(orb_state.get("capture_lock", 0) or 0)
    if capture_lock > 0:
        orb_state["capture_lock"] = capture_lock - 1
    radius_px = int(orb_state.get("return_radius", _MONK_ORB_RADIUS) or _MONK_ORB_RADIUS)
    if radius_px <= (_MONK_ORB_RADIUS + _MONK_ORB_RETURN_DONE_RADIUS_EPS):
        orb_state["return_radius"] = _MONK_ORB_RADIUS
        orb_state["mode"] = "orbit"
        return "orbit"
    shrink = (radius_px - _MONK_ORB_RADIUS) // _MONK_ORB_RETURN_RADIUS_DIV
    if shrink < _MONK_ORB_RETURN_RADIUS_MIN_STEP:
        shrink = _MONK_ORB_RETURN_RADIUS_MIN_STEP
    radius_px -= shrink
    if radius_px <= (_MONK_ORB_RADIUS + _MONK_ORB_RETURN_DONE_RADIUS_EPS):
        radius_px = _MONK_ORB_RADIUS
    if radius_px <= _MONK_ORB_RADIUS:
        orb_state["return_radius"] = _MONK_ORB_RADIUS
        orb_state["mode"] = "orbit"
        return "orbit"
    orb_state["return_radius"] = radius_px
    orb_state["mode"] = "captured_return"
    return "captured_return"


def _monk_orb_current_world_pos(wx, wy, ow, oh, anim_counter, slot_i, monk_frame_w, monk_frame_h, orb_state):
    base_x, base_y = _monk_orb_slot_world_pos(wx, wy, ow, oh, anim_counter, slot_i, monk_frame_w, monk_frame_h)
    center_x, center_y = _monk_center_world_pos(wx, wy, ow, oh, monk_frame_w, monk_frame_h)
    base_angle_rad = _monk_orb_slot_angle_rad(anim_counter, slot_i)
    if orb_state is not None and str(orb_state.get("mode", "orbit") or "orbit") in (_MONK_ORB_MODE_SCRIPTED_ATTACK, _MONK_ORB_MODE_SCRIPTED_INTRO):
        return int(orb_state.get("script_x", base_x) or base_x), int(orb_state.get("script_y", base_y) or base_y)
    if orb_state is not None and int(orb_state.get("native_current_valid", orb_state.get("current_valid", 0)) or 0):
        return int(orb_state.get("current_x", base_x) or base_x), int(orb_state.get("current_y", base_y) or base_y)
    mode = _step_monk_orb_state(orb_state, center_x, center_y, base_angle_rad)
    if mode == "orbit":
        return base_x, base_y
    if mode == "detached":
        return int(orb_state.get("detached_x", base_x) or base_x), int(orb_state.get("detached_y", base_y) or base_y)
    radius_px = int(orb_state.get("return_radius", _MONK_ORB_RADIUS) or _MONK_ORB_RADIUS)
    return _monk_orb_world_pos_from_angle(center_x, center_y, radius_px, base_angle_rad)


def _monk_orb_slot_world_pos(wx, wy, ow, oh, anim_counter, slot_i, monk_frame_w, monk_frame_h):
    center_x, center_y = _monk_center_world_pos(wx, wy, ow, oh, monk_frame_w, monk_frame_h)
    return _monk_orb_world_pos_from_angle(center_x, center_y, _MONK_ORB_RADIUS, _monk_orb_slot_angle_rad(anim_counter, slot_i))


def _special_kind_from_anim_id(anim_id):
    aid = str(anim_id or "")
    if aid == "respawn_stone":
        return _SPECIAL_KIND_RESPAWN_STONE
    if aid == "resurrection_anchor":
        return _SPECIAL_KIND_ANCHOR
    return -1


def _pack_special_object_descriptors(
    objects_rows,
    object_meta_rows,
    object_animations,
    object_anim_counter,
    anchor_active,
    anchor_x,
    anchor_y,
    anchor_anim_spec,
    anchor_anim_counter,
    camera_x=0,
    view_w=320,
    view_h=240,
):
    out = bytearray()
    stride = 8
    count = 0
    if objects_rows and object_meta_rows and object_animations:
        oi = 0
        while oi < len(objects_rows):
            meta = object_meta_rows[oi] if oi < len(object_meta_rows) else None
            if _is_special_render_object(meta):
                anim_id = meta.get("anim_id", "") if meta else ""
                kind = _special_kind_from_anim_id(anim_id)
                anim_spec = object_animations.get(anim_id)
                frame_index = _pick_animation_frame_index(anim_spec, object_anim_counter)
                if kind >= 0 and frame_index >= 0:
                    wx, wy, ow, oh, _solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = objects_rows[oi]
                    frame_w = int(anim_spec.get("frame_w", 0) or 0) if anim_spec else 0
                    frame_h = int(anim_spec.get("frame_h", 0) or 0) if anim_spec else 0
                    if visible and frame_w > 0 and frame_h > 0 and _aabb_near_view(wx, wy, ow, oh, camera_x, view_w, view_h, 48, 32):
                        _append_i16_le(out, wx)
                        _append_i16_le(out, wy)
                        out.append(kind & 0xFF)
                        out.append(frame_index & 0xFF)
                        out.append(0)
                        out.append(0)
                        count += 1
            oi += 1
    if anchor_active and anchor_anim_spec:
        frame_index = _pick_animation_frame_index(anchor_anim_spec, anchor_anim_counter)
        if frame_index >= 0:
            _append_i16_le(out, anchor_x)
            _append_i16_le(out, anchor_y)
            out.append(_SPECIAL_KIND_ANCHOR)
            out.append(frame_index & 0xFF)
            out.append(0)
            out.append(0)
            count += 1
    return out, stride, count

def _pack_monk_orb_descriptors(
    enemy_rows,
    enemy_states,
    monk_orb_states=None,
    enemy_meta=None,
    camera_x=0,
    view_w=320,
    view_h=240,
    monk_frame_w=32,
    monk_frame_h=48,
):
    out = bytearray()
    stride = 8
    count = 0
    if not enemy_rows or not enemy_states:
        return out, stride, count
    ei = 0
    while ei < len(enemy_rows):
        row = enemy_rows[ei]
        state = enemy_states[ei] if ei < len(enemy_states) else None
        slot_states = monk_orb_states[ei] if (monk_orb_states is not None and ei < len(monk_orb_states)) else None
        meta = enemy_meta[ei] if (enemy_meta is not None and ei < len(enemy_meta)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        if state is not None and enemy_type == "monk" and slot_states:
            wx, wy, ow, oh, visible, _swappable = row
            draw_x = int(wx)
            draw_y = int(wy)
            if int(monk_frame_w) > 0 and int(ow) != int(monk_frame_w):
                draw_x = int(wx) + ((int(ow) - int(monk_frame_w)) // 2)
            if int(monk_frame_h) > 0 and int(oh) != int(monk_frame_h):
                draw_y = int(wy) + (int(oh) - int(monk_frame_h))
            orb_extent = _MONK_ORB_RADIUS + (_MONK_ORB_W // 2)
            if visible and _aabb_near_view(draw_x - orb_extent, draw_y - orb_extent, int(monk_frame_w) + (orb_extent * 2), int(monk_frame_h) + (orb_extent * 2), camera_x, view_w, view_h, 48, 32):
                oi = 0
                while oi < len(slot_states):
                    orb_state = slot_states[oi]
                    orb_mode = _monk_orb_native_mode_from_state(orb_state)
                    if orb_mode == _MONK_ORB_NATIVE_MODE_UNUSED or orb_mode == _MONK_ORB_NATIVE_MODE_LOST:
                        oi += 1
                        continue
                    orb_x, orb_y = _monk_orb_current_world_pos(wx, wy, ow, oh, int(state.get("anim_counter", 0) or 0), oi, monk_frame_w, monk_frame_h, orb_state)
                    _append_i16_le(out, orb_x)
                    _append_i16_le(out, orb_y)
                    out.append(_SPECIAL_KIND_MONK_ORB)
                    out.append(oi & 0xFF)
                    out.append(orb_mode & 0xFF)
                    out.append(0)
                    count += 1
                    oi += 1
        ei += 1
    return out, stride, count


def _monk_orb_descriptors_native_ready():
    return bool(_lgfx is not None and hasattr(_lgfx, "pack_monk_orb_descriptors_native"))


def _monk_orb_states_have_scripted_mode(monk_orb_states):
    if not monk_orb_states:
        return False
    ei = 0
    while ei < len(monk_orb_states):
        slot_states = monk_orb_states[ei]
        if slot_states is not None:
            si = 0
            while si < len(slot_states):
                mode = str(slot_states[si].get("mode", "orbit") or "orbit")
                if mode == _MONK_ORB_MODE_SCRIPTED_INTRO:
                    return True
                si += 1
        ei += 1
    return False


def _pack_monk_orb_descriptors_native(
    enemy_rows_c_buf,
    enemy_rows_c_stride,
    enemy_rows_c_count,
    monk_orb_c_buf,
    monk_orb_c_stride,
    monk_orb_c_count,
    monk_orb_states=None,
    camera_x=0,
    view_w=320,
    view_h=240,
    monk_frame_w=32,
    monk_frame_h=48,
):
    stride = 8
    if not _monk_orb_descriptors_native_ready():
        return None
    if monk_orb_c_buf is None or monk_orb_c_count <= 0 or enemy_rows_c_buf is None or enemy_rows_c_count <= 0:
        return bytearray(), stride, 0
    if _monk_orb_states_have_scripted_mode(monk_orb_states):
        return None
    max_count = int(monk_orb_c_count)
    out = bytearray(max_count * stride)
    try:
        count = _lgfx.pack_monk_orb_descriptors_native(
            out,
            stride,
            enemy_rows_c_buf,
            enemy_rows_c_stride,
            enemy_rows_c_count,
            monk_orb_c_buf,
            monk_orb_c_stride,
            monk_orb_c_count,
            camera_x,
            view_w,
            view_h,
            monk_frame_w,
            monk_frame_h,
            max_count,
        )
        count = int(count)
        if count < 0:
            count = 0
        if count < max_count:
            out = out[:count * stride]
        return out, stride, count
    except Exception as exc:
        print("MONK_ORB_DESC_NATIVE_FAIL %r" % (exc,))
        return None


def _pack_monk_encounter_intro_orb_descriptors(monk_encounters, camera_x=0, view_w=320, view_h=240):
    out = bytearray()
    stride = 8
    count = 0
    if not monk_encounters:
        return out, stride, count
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is not None and str(encounter.get("state", "") or "") == _MONK_ENCOUNTER_STATE_INTRO:
            orbs = encounter.get("orbs") or []
            oi = 0
            while oi < len(orbs):
                orb = orbs[oi]
                orb_x = int(orb.get("x", 0) or 0)
                orb_y = int(orb.get("y", 0) or 0)
                if _aabb_near_view(orb_x, orb_y, _MONK_ORB_W, _MONK_ORB_H, camera_x, view_w, view_h, 48, 32):
                    _append_i16_le(out, orb_x)
                    _append_i16_le(out, orb_y)
                    out.append(_SPECIAL_KIND_MONK_ORB)
                    out.append(oi & 0xFF)
                    out.append(_MONK_ORB_NATIVE_MODE_SCRIPTED_INTRO)
                    out.append(0)
                    count += 1
                oi += 1
        ei += 1
    return out, stride, count


def _pack_monk_final_path_descriptors(monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count, camera_x=0, view_w=320, view_h=240):
    return bytearray(), 8, 0


def _pack_monk_encounter_intro_body_descriptors(monk_encounters, camera_x=0, view_w=320, view_h=240, monk_frame_w=32, monk_frame_h=48):
    out = bytearray()
    stride = 10
    count = 0
    if not monk_encounters:
        return out, stride, count
    ei = 0
    while ei < len(monk_encounters):
        encounter = monk_encounters[ei]
        if encounter is not None and str(encounter.get("state", "") or "") == _MONK_ENCOUNTER_STATE_INTRO:
            body_x = int(encounter.get("body_x", 0) or 0)
            body_y = int(encounter.get("body_y", 0) or 0)
            template_row = encounter.get("template_row") or [0, 0, 48, 64]
            body_w = int(template_row[2])
            body_h = int(template_row[3])
            draw_x, draw_y = _monk_enemy_draw_origin(body_x, body_y, body_w, body_h, monk_frame_w, monk_frame_h)
            if _aabb_near_view(draw_x, draw_y, monk_frame_w, monk_frame_h, camera_x, view_w, view_h, 48, 32):
                _append_i16_le(out, draw_x)
                _append_i16_le(out, draw_y)
                _append_u16_le(out, int(encounter.get("anim_counter", 0) or 0))
                out.append(_ENEMY_STATE_IDLE & 0xFF)
                out.append(1)
                out.append(1)
                out.append(0)
                count += 1
        ei += 1
    return out, stride, count


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
        static_enemy = 0
        if meta is not None:
            mf = str(meta.get("facing", "R") or "R").upper()
            default_facing = 1 if mf != "L" else -1
            static_enemy = 1 if int(meta.get("static", 0) or 0) else 0
        _buf_set_i16_le(out, bi + 0, wx)
        _buf_set_i16_le(out, bi + 2, wy)
        _buf_set_i16_le(out, bi + 4, ow)
        _buf_set_i16_le(out, bi + 6, oh)
        out[bi + 8] = 1 if int(visible) else 0
        out[bi + 9] = 1 if int(swappable) else 0
        out[bi + 10] = 1 if default_facing >= 0 else 0
        out[bi + 11] = 1 if static_enemy else 0
        bi += _ENEMY_ROW_STRIDE
        oi += 1
    return out, _ENEMY_ROW_STRIDE, len(rows)


def _pack_monk_hover_states_for_c(rows, meta_rows=None, map_w_px=0):
    if not rows:
        return bytearray(), _MONK_HOVER_STATE_STRIDE, 0
    out = bytearray(len(rows) * _MONK_HOVER_STATE_STRIDE)
    hover_enabled = bool(getattr(config, "MONK_HOVER_ENABLED", True))
    hover_min_x = int(getattr(config, "MONK_HOVER_MIN_X", 1616))
    hover_max_x = int(getattr(config, "MONK_HOVER_MAX_X", 1856))
    hover_min_y = int(getattr(config, "MONK_HOVER_BASE_Y", 96)) - int(getattr(config, "MONK_HOVER_AMP", 8))
    hover_max_y = int(getattr(config, "MONK_HOVER_BASE_Y", 96)) + int(getattr(config, "MONK_HOVER_AMP", 8))
    hover_base_y = int(getattr(config, "MONK_HOVER_BASE_Y", 112))
    hover_phase_step = int(getattr(config, "MONK_HOVER_PHASE_STEP", 2))
    if hover_phase_step < 1:
        hover_phase_step = 1
    hover_retarget_frames = int(getattr(config, "MONK_HOVER_RETARGET_FRAMES", 30))
    if hover_retarget_frames < 1:
        hover_retarget_frames = 1
    hover_speed_q8 = int(getattr(config, "MONK_HOVER_SPEED_Q8", 256))
    if hover_speed_q8 < 1:
        hover_speed_q8 = 256
    if hover_speed_q8 > 4095:
        hover_speed_q8 = 4095
    if map_w_px > 0:
        if hover_min_x < 0:
            hover_min_x = 0
        if hover_max_x >= map_w_px:
            hover_max_x = map_w_px - 1
        if hover_max_x < hover_min_x:
            hover_max_x = hover_min_x
    oi = 0
    bi = 0
    while oi < len(rows):
        row = rows[oi]
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        enemy_type = str(meta.get("type", "bow") or "bow") if meta is not None else "bow"
        target_x = int(row[0])
        target_y = int(row[1])
        if hover_enabled and enemy_type == "monk":
            target_x = hover_min_x + ((hover_max_x - hover_min_x) // 2)
            target_y = hover_base_y
            phase = (oi * 13) & 0xFFFF
            _buf_set_i16_le(out, bi + 0, target_x)
            _buf_set_i16_le(out, bi + 2, target_y)
            _buf_set_i16_le(out, bi + 4, hover_base_y)
            _buf_set_i16_le(out, bi + 6, phase)
            out[bi + 8] = hover_retarget_frames & 0xFF
            _buf_set_i16_le(out, bi + 9, hover_speed_q8)
        else:
            _buf_set_i16_le(out, bi + 0, target_x)
            _buf_set_i16_le(out, bi + 2, target_y)
            _buf_set_i16_le(out, bi + 4, int(row[1]))
            _buf_set_i16_le(out, bi + 6, 0)
            out[bi + 8] = 0
            _buf_set_i16_le(out, bi + 9, 0)
        bi += _MONK_HOVER_STATE_STRIDE
        oi += 1
    return out, _MONK_HOVER_STATE_STRIDE, len(rows)


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
        static_enemy = 0
        if meta is not None:
            mf = str(meta.get("facing", "R") or "R").upper()
            default_facing = 1 if mf != "L" else -1
            static_enemy = 1 if int(meta.get("static", 0) or 0) else 0
        _buf_set_i16_le(enemy_rows_c_buf, base + 0, wx)
        _buf_set_i16_le(enemy_rows_c_buf, base + 2, wy)
        _buf_set_i16_le(enemy_rows_c_buf, base + 4, ow)
        _buf_set_i16_le(enemy_rows_c_buf, base + 6, oh)
        enemy_rows_c_buf[base + 8] = 1 if int(visible) else 0
        enemy_rows_c_buf[base + 9] = 1 if int(swappable) else 0
        enemy_rows_c_buf[base + 10] = 1 if default_facing >= 0 else 0
        enemy_rows_c_buf[base + 11] = 1 if static_enemy else 0
        oi += 1
    return limit


def _swap_preview_state_tuple(state):
    if state is None or len(state) < _SWAP_PREVIEW_STATE_STRIDE:
        return (0, 0, 0, _SWAP_TARGET_NONE, -1, -1, 0, 0, 0, 0, -1)
    return (
        int(state[0]),
        int(state[1]),
        int(state[2]),
        int(state[3]),
        _buf_get_i16_le(state, 4),
        _buf_get_i16_le(state, 6),
        _buf_get_i16_le(state, 8),
        _buf_get_i16_le(state, 10),
        _buf_get_i16_le(state, 12),
        _buf_get_i16_le(state, 14),
        _buf_get_i32_le(state, 16),
    )


def _swap_preview_write_state(state, active, valid, pick_far, kind, index, slot, x, y, w, h, d2):
    if state is None or len(state) < _SWAP_PREVIEW_STATE_STRIDE:
        return
    state[0] = 1 if active else 0
    state[1] = 1 if valid else 0
    state[2] = 1 if pick_far else 0
    state[3] = int(kind) & 0xFF
    _buf_set_i16_le(state, 4, index)
    _buf_set_i16_le(state, 6, slot)
    _buf_set_i16_le(state, 8, x)
    _buf_set_i16_le(state, 10, y)
    _buf_set_i16_le(state, 12, w)
    _buf_set_i16_le(state, 14, h)
    _buf_set_i32_le(state, 16, d2)
    age = (state[20] | (state[21] << 8)) if valid else 0
    if valid and age < 65535:
        age += 1
    state[20] = age & 0xFF
    state[21] = (age >> 8) & 0xFF
    state[22] = 0
    state[23] = 0


def _swap_preview_target_valid(target, objects_rows, enemy_rows, enemy_bullets, monk_orb_c_buf, monk_orb_c_stride):
    if target is None or int(target[1]) == 0:
        return False
    kind = int(target[3])
    index = int(target[4])
    slot = int(target[5])
    if kind == _SWAP_TARGET_OBJECT:
        if not objects_rows or index < 0 or index >= len(objects_rows):
            return False
        row = objects_rows[index]
        return bool(row[6] and row[7])
    if kind == _SWAP_TARGET_ENEMY:
        if not enemy_rows or index < 0 or index >= len(enemy_rows):
            return False
        row = enemy_rows[index]
        return bool(row[4] and row[5])
    if kind == _SWAP_TARGET_BULLET:
        if not enemy_bullets or index < 0 or index >= len(enemy_bullets):
            return False
        row = enemy_bullets[index]
        return bool(row[6])
    if kind == _SWAP_TARGET_MONK_ORB:
        mode = _monk_orb_c_mode(monk_orb_c_buf, monk_orb_c_stride, index, slot)
        return mode not in (_MONK_ORB_NATIVE_MODE_UNUSED, _MONK_ORB_NATIVE_MODE_SCRIPTED_INTRO, _MONK_ORB_NATIVE_MODE_CLASH_BOUNCE, _MONK_ORB_NATIVE_MODE_LOST, _MONK_ORB_NATIVE_MODE_PLAYER_ORBIT)
    return False


def _swap_hold_step(input_system, preview_state, state):
    b_now = 1 if bool(getattr(input_system, "btn_b_down", False)) else 0
    y_now = 1 if bool(getattr(input_system, "btn_y_down", False)) else 0
    b_edge = b_now and not state[0]
    y_edge = y_now and not state[1]
    b_release = (not b_now) and state[0]
    y_release = (not y_now) and state[1]
    state[0] = b_now
    state[1] = y_now
    triggered = False
    pick_far = False
    locked_target = None
    if not state[2]:
        if b_edge:
            state[2] = 1
            state[3] = 1
            state[4] = 1
            _swap_preview_write_state(preview_state, True, False, True, _SWAP_TARGET_NONE, -1, -1, 0, 0, 0, 0, -1)
        elif y_edge:
            state[2] = 1
            state[3] = 0
            state[4] = 2
            _swap_preview_write_state(preview_state, True, False, False, _SWAP_TARGET_NONE, -1, -1, 0, 0, 0, 0, -1)
    if state[2]:
        pick_far = bool(state[3])
        button = int(state[4])
        if (button == 1 and b_now) or (button == 2 and y_now):
            pass
        elif (button == 1 and b_release) or (button == 2 and y_release):
            locked_target = _swap_preview_state_tuple(preview_state)
            triggered = bool(locked_target[1])
            state[2] = 0
            state[4] = 0
            _swap_preview_write_state(preview_state, False, False, pick_far, _SWAP_TARGET_NONE, -1, -1, 0, 0, 0, 0, -1)
        elif not b_now and not y_now:
            state[2] = 0
            state[4] = 0
            _swap_preview_write_state(preview_state, False, False, pick_far, _SWAP_TARGET_NONE, -1, -1, 0, 0, 0, 0, -1)
    return triggered, pick_far, locked_target


def _swap_hold_cancel(input_system, preview_state, state):
    if state is not None and len(state) >= _SWAP_INPUT_STATE_STRIDE:
        state[0] = 1 if bool(getattr(input_system, "btn_b_down", False)) else 0
        state[1] = 1 if bool(getattr(input_system, "btn_y_down", False)) else 0
        pick_far = bool(state[3])
        state[2] = 0
        state[3] = 0
        state[4] = 0
    else:
        pick_far = False
    _swap_preview_write_state(preview_state, False, False, pick_far, _SWAP_TARGET_NONE, -1, -1, 0, 0, 0, 0, -1)


def _respawn_confirm_pressed(input_system):
    return bool(
        getattr(input_system, "btn_a_pressed", False)
        or getattr(input_system, "btn_b_pressed", False)
        or getattr(input_system, "btn_x_pressed", False)
        or getattr(input_system, "btn_y_pressed", False)
    )


def _map_exit_triggered(input_system, player_x):
    if not bool(getattr(config, "MAP_EXIT_ENABLED", False)):
        return False
    if not getattr(input_system, "btn_a_pressed", False):
        return False
    px = int(player_x)
    return int(getattr(config, "MAP_EXIT_X0", 2816)) <= px <= int(getattr(config, "MAP_EXIT_X1", 2879))


def _request_stage_reset(stage):
    try:
        with open("/sd/game/save/next_stage.txt", "w") as fp:
            fp.write(str(stage or "stage02"))
        raise RuntimeError("STAGE_SWITCH")
    except Exception as exc:
        if str(exc) == "STAGE_SWITCH":
            raise
        print("MAP_EXIT_REQUEST_FAIL %r" % (exc,))


def _swap_preview_update_native(
    preview_state,
    objects_rows,
    enemy_rows_c_buf,
    enemy_rows_c_stride,
    enemy_rows_c_count,
    enemy_bullets,
    monk_orb_c_buf,
    monk_orb_c_stride,
    monk_orb_c_count,
    player_x,
    player_y,
    player_w,
    player_h,
    pick_far,
    camera_x,
    band_top,
    view_w,
    view_h,
):
    if preview_state is None or len(preview_state) < _SWAP_PREVIEW_STATE_STRIDE:
        return False
    if _lgfx is None or not hasattr(_lgfx, "update_swap_preview_native"):
        return False
    bullet_buf = enemy_bullets._buf if hasattr(enemy_bullets, "_buf") else bytearray()
    bullet_count = len(enemy_bullets) if enemy_bullets is not None else 0
    object_buf = bytearray()
    object_stride = 10
    object_count = 0
    if objects_rows:
        object_count = len(objects_rows)
        object_buf = bytearray(object_count * object_stride)
        oi = 0
        while oi < object_count:
            row = objects_rows[oi]
            base = oi * object_stride
            _buf_set_i16_le(object_buf, base + 0, row[0])
            _buf_set_i16_le(object_buf, base + 2, row[1])
            _buf_set_i16_le(object_buf, base + 4, row[2])
            _buf_set_i16_le(object_buf, base + 6, row[3])
            object_buf[base + 8] = 1 if row[6] else 0
            object_buf[base + 9] = 1 if row[7] else 0
            oi += 1
    try:
        _lgfx.update_swap_preview_native(
            preview_state,
            object_buf,
            object_stride,
            object_count,
            enemy_rows_c_buf if enemy_rows_c_buf is not None else bytearray(),
            enemy_rows_c_stride,
            enemy_rows_c_count,
            bullet_buf,
            _BULLET_STATE_STRIDE,
            bullet_count,
            monk_orb_c_buf if monk_orb_c_buf is not None else bytearray(),
            monk_orb_c_stride,
            monk_orb_c_count,
            player_x,
            player_y,
            player_w,
            player_h,
            pick_far,
            camera_x,
            band_top,
            view_w,
            view_h,
            _SWAP_PREVIEW_HYSTERESIS_PX,
        )
        return True
    except Exception as exc:
        if _runtime_verbose_enabled():
            print("SWAP_PREVIEW_NATIVE_FAIL %r" % (exc,))
        return False


def _pack_swap_preview_descriptor(preview_state, camera_x=0, view_w=320, view_h=240):
    target = _swap_preview_state_tuple(preview_state)
    stride = 8
    if int(target[1]) == 0:
        return bytearray(), stride, 0
    x = int(target[6]) + 1
    y = int(target[7]) + 1
    w = int(target[8]) - 2
    h = int(target[9]) - 2
    if w <= 0 or h <= 0 or not _aabb_near_view(x, y, w, h, camera_x, view_w, view_h, 8, 8):
        return bytearray(), stride, 0
    out = bytearray()
    _append_i16_le(out, x)
    _append_i16_le(out, y)
    out.append(_SPECIAL_KIND_SWAP_PREVIEW)
    out.append(w & 0xFF)
    out.append(h & 0xFF)
    out.append(2)
    return out, stride, 1


def _clone_object_rows(rows):
    if not rows:
        return []
    return [list(row) for row in rows]


def _respawn_checkpoint_row(checkpoint_index, objects_rows, saved_rows):
    if checkpoint_index < 0:
        return None
    if saved_rows is not None and checkpoint_index < len(saved_rows):
        return saved_rows[checkpoint_index]
    if objects_rows is not None and checkpoint_index < len(objects_rows):
        return objects_rows[checkpoint_index]
    return None


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
    enemy_rows=None,
    enemy_meta=None,
    monk_sheet=None,
    monk_frame_w=0,
    monk_frame_h=0,
    monk_frame_count=0,
    monk_anim_counter=0,
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
    if m == _MODE_ROWS_SAFE_PROGRESSIVE:
        return m
    return _MODE_ROWS_SAFE_PROGRESSIVE


def _ensure_prerequisites(mode):
    if _lgfx is None:
        raise RuntimeError("CAMERA_TEST_FAIL_NO_LGFX")
    if not hasattr(_lgfx, "blit_rect565"):
        raise RuntimeError("CAMERA_TEST_FAIL_NO_BLIT")
    if os is None:
        raise RuntimeError("CAMERA_TEST_FAIL_NO_OS")

    if mode != _MODE_ROWS_SAFE_PROGRESSIVE:
        raise RuntimeError("CAMERA_TEST_FAIL_UNSUPPORTED_MODE")


def _zero_profile_counters():
    return (0,) * 36


def _unpack_band_profile_result(band_res):
    band_count = int(band_res[0])
    band_compose_us = int(band_res[1])
    kick_us = int(band_res[2])
    wait_us = int(band_res[3])
    sync_us = 0
    start_us = 0
    push_us = 0
    wait_dma_us = 0
    end_us = 0
    band_bg_us = 0
    band_tilemap_us = 0
    band_object_us = 0
    band_special_us = 0
    band_enemy_us = 0
    band_player_us = 0
    band_compose_each = [0, 0, 0, 0, 0, 0]
    band_wait_each = [0, 0, 0, 0, 0, 0]
    dma_elapsed_us = 0
    if len(band_res) >= 10:
        sync_us = int(band_res[4])
        start_us = int(band_res[5])
        push_us = int(band_res[6])
        wait_dma_us = int(band_res[7])
        end_us = int(band_res[8])
    if len(band_res) >= 16:
        band_bg_us = int(band_res[10])
        band_tilemap_us = int(band_res[11])
        band_object_us = int(band_res[12])
        band_special_us = int(band_res[13])
        band_enemy_us = int(band_res[14])
        band_player_us = int(band_res[15])
    if len(band_res) >= 28:
        band_compose_each = [int(v) for v in band_res[16:22]]
        band_wait_each = [int(v) for v in band_res[22:28]]
    if len(band_res) >= 29:
        dma_elapsed_us = int(band_res[28])
    return (
        band_count,
        band_compose_us,
        kick_us,
        wait_us,
        sync_us,
        start_us,
        push_us,
        wait_dma_us,
        end_us,
        band_bg_us,
        band_tilemap_us,
        band_object_us,
        band_special_us,
        band_enemy_us,
        band_player_us,
        band_compose_each[0],
        band_compose_each[1],
        band_compose_each[2],
        band_compose_each[3],
        band_compose_each[4],
        band_compose_each[5],
        band_wait_each[0],
        band_wait_each[1],
        band_wait_each[2],
        band_wait_each[3],
        band_wait_each[4],
        band_wait_each[5],
        dma_elapsed_us,
    )


def _print_profile_summary(
    avg_update_us,
    avg_bg_us,
    avg_world_us,
    avg_sprite_us,
    avg_hud_us,
    avg_submit_us,
    avg_submit_compose_us,
    avg_band_bg_us,
    avg_band_tilemap_us,
    avg_band_object_us,
    avg_band_special_us,
    avg_band_enemy_us,
    avg_band_player_us,
    avg_band0_compose_us,
    avg_band1_compose_us,
    avg_band2_compose_us,
    avg_band3_compose_us,
    avg_band4_compose_us,
    avg_band5_compose_us,
    avg_band0_wait_us,
    avg_band1_wait_us,
    avg_band2_wait_us,
    avg_band3_wait_us,
    avg_band4_wait_us,
    avg_band5_wait_us,
    avg_submit_wait_us,
    avg_submit_kick_us,
    avg_submit_sync_us,
    avg_submit_start_us,
    avg_submit_push_us,
    avg_submit_dma_wait_us,
    avg_submit_end_us,
    avg_submit_swap_us,
    avg_pace_us,
    avg_other_us,
    avg_total_us,
    fps_prof,
    avg_tail_overlap_update_us,
    avg_tail_overlap_residual_wait_us,
    avg_tail_overlap_total_wait_us,
    avg_descriptor_us=0,
    avg_swap_detail_us=0,
    avg_dma_elapsed_us=0,
    avg_tail_dma_elapsed_us=0,
):
    if not _runtime_verbose_enabled():
        return
    tail_hidden_us = avg_tail_overlap_total_wait_us - avg_tail_overlap_residual_wait_us
    if tail_hidden_us < 0:
        tail_hidden_us = 0
    avg_wait_us = avg_submit_wait_us
    dma_full_elapsed_us = avg_dma_elapsed_us + avg_tail_dma_elapsed_us
    dma_full_exposed_us = avg_submit_dma_wait_us
    dma_not_waitdma_us = dma_full_elapsed_us - dma_full_exposed_us
    if dma_not_waitdma_us < 0:
        dma_not_waitdma_us = 0
    spi_hz = int(getattr(config, "CAMERA_SPI_HZ", 40000000) or 40000000)
    dma_ideal_us = 0
    screen_w = int(getattr(config, "SCREEN_W", 320) or 320)
    screen_h = int(getattr(config, "SCREEN_H", 240) or 240)
    frame_bytes = screen_w * screen_h * 2
    if spi_hz > 0:
        dma_ideal_us = (frame_bytes * 8 * 1000000) // spi_hz
    dma_gap_us = dma_full_elapsed_us - dma_ideal_us
    print(
        "FRAME_WALL total_us=%d update_us=%d submit_call_us=%d tail_res_us=%d wait_exposed_us=%d fps=%.2f"
        % (
            avg_total_us,
            avg_update_us,
            avg_submit_us,
            avg_tail_overlap_residual_wait_us,
            avg_wait_us,
            fps_prof,
        )
    )
    print(
        "CPU_WORK update_us=%d compose_us=%d desc_us=%d kick_cpu_us=%d sync_us=%d start_us=%d push_us=%d swap_us=%d"
        % (
            avg_update_us,
            avg_submit_compose_us,
            avg_descriptor_us,
            avg_submit_kick_us,
            avg_submit_sync_us,
            avg_submit_start_us,
            avg_submit_push_us,
            avg_swap_detail_us,
        )
    )
    print(
        "CPU_COMP bg_us=%d tile_us=%d obj_us=%d enemy_us=%d special_us=%d player_us=%d"
        % (
            avg_band_bg_us,
            avg_band_tilemap_us,
            avg_band_object_us,
            avg_band_enemy_us,
            avg_band_special_us,
            avg_band_player_us,
        )
    )
    print(
        "DMA_SUM bytes=%d spi_hz=%d ideal_us=%d elapsed_us=%d gap_us=%d exposed_dma_us=%d not_waitdma_us=%d kick_us=%d wait_dma_us=%d end_us=%d tail_dma_us=%d tail_total_us=%d tail_res_us=%d"
        % (
            frame_bytes,
            spi_hz,
            dma_ideal_us,
            dma_full_elapsed_us,
            dma_gap_us,
            dma_full_exposed_us,
            dma_not_waitdma_us,
            avg_submit_kick_us,
            avg_submit_dma_wait_us,
            avg_submit_end_us,
            avg_tail_dma_elapsed_us,
            avg_tail_overlap_total_wait_us,
            avg_tail_overlap_residual_wait_us,
        )
    )
    print(
        "PIPE_OVERLAP band_comp_us=%d,%d,%d,%d,%d,%d band_wait_exposed_us=%d,%d,%d,%d,%d,%d tail_update_us=%d tail_hidden_us=%d"
        % (
            avg_band0_compose_us,
            avg_band1_compose_us,
            avg_band2_compose_us,
            avg_band3_compose_us,
            avg_band4_compose_us,
            avg_band5_compose_us,
            avg_band0_wait_us,
            avg_band1_wait_us,
            avg_band2_wait_us,
            avg_band3_wait_us,
            avg_band4_wait_us,
            avg_band5_wait_us,
            avg_tail_overlap_update_us,
            tail_hidden_us,
        )
    )
    if not bool(getattr(config, "CAMERA_RENDER_PROFILE_DETAIL", False)):
        return
    print(
        "RENDER_SUM fps=%.2f total_us=%d update_us=%d submit_us=%d compose_us=%d dma_wait_us=%d tail_res_us=%d"
        % (
            fps_prof,
            avg_total_us,
            avg_update_us,
            avg_submit_us,
            avg_submit_compose_us,
            avg_submit_dma_wait_us,
            avg_tail_overlap_residual_wait_us,
        )
    )
    print(
        "RENDER_COMP bg_us=%d tile_us=%d obj_us=%d enemy_us=%d special_us=%d player_us=%d"
        % (
            avg_band_bg_us,
            avg_band_tilemap_us,
            avg_band_object_us,
            avg_band_enemy_us,
            avg_band_special_us,
            avg_band_player_us,
        )
    )
    print(
        "RENDER_DMA kick_us=%d sync_us=%d start_us=%d push_us=%d wait_us=%d wait_dma_us=%d end_us=%d swap_us=%d"
        % (
            avg_submit_kick_us,
            avg_submit_sync_us,
            avg_submit_start_us,
            avg_submit_push_us,
            avg_submit_wait_us,
            avg_submit_dma_wait_us,
            avg_submit_end_us,
            avg_submit_swap_us,
        )
    )
    print(
        "RENDER_PIPE band_comp_us=%d,%d,%d,%d,%d,%d band_wait_us=%d,%d,%d,%d,%d,%d tail_total_us=%d tail_update_us=%d tail_hidden_us=%d"
        % (
            avg_band0_compose_us,
            avg_band1_compose_us,
            avg_band2_compose_us,
            avg_band3_compose_us,
            avg_band4_compose_us,
            avg_band5_compose_us,
            avg_band0_wait_us,
            avg_band1_wait_us,
            avg_band2_wait_us,
            avg_band3_wait_us,
            avg_band4_wait_us,
            avg_band5_wait_us,
            avg_tail_overlap_total_wait_us,
            avg_tail_overlap_update_us,
            tail_hidden_us,
        )
    )
    avg_render_us = avg_submit_compose_us + avg_bg_us + avg_world_us + avg_sprite_us + avg_hud_us
    print(
        "PROFILE_TABLE update_us=%d render_us=%d wait_us=%d desc_us=%d swap_us=%d total_us=%d fps=%.2f"
        % (
            avg_update_us,
            avg_render_us,
            avg_wait_us,
            avg_descriptor_us,
            avg_swap_detail_us,
            avg_total_us,
            fps_prof,
        )
    )
    print("PROFILE update_us=%d" % avg_update_us)
    print("PROFILE bg_us=%d" % avg_bg_us)
    print("PROFILE world_us=%d" % avg_world_us)
    print("PROFILE sprite_us=%d" % avg_sprite_us)
    print("PROFILE hud_us=%d" % avg_hud_us)
    print("PROFILE submit_us=%d" % avg_submit_us)
    print("PROFILE submit_compose_us=%d" % avg_submit_compose_us)
    print("PROFILE band_bg_us=%d" % avg_band_bg_us)
    print("PROFILE band_tilemap_us=%d" % avg_band_tilemap_us)
    print("PROFILE band_object_us=%d" % avg_band_object_us)
    print("PROFILE band_special_us=%d" % avg_band_special_us)
    print("PROFILE band_enemy_us=%d" % avg_band_enemy_us)
    print("PROFILE band_player_us=%d" % avg_band_player_us)
    print("PROFILE band0_compose_us=%d" % avg_band0_compose_us)
    print("PROFILE band1_compose_us=%d" % avg_band1_compose_us)
    print("PROFILE band2_compose_us=%d" % avg_band2_compose_us)
    print("PROFILE band3_compose_us=%d" % avg_band3_compose_us)
    print("PROFILE band4_compose_us=%d" % avg_band4_compose_us)
    print("PROFILE band5_compose_us=%d" % avg_band5_compose_us)
    print("PROFILE band0_wait_us=%d" % avg_band0_wait_us)
    print("PROFILE band1_wait_us=%d" % avg_band1_wait_us)
    print("PROFILE band2_wait_us=%d" % avg_band2_wait_us)
    print("PROFILE band3_wait_us=%d" % avg_band3_wait_us)
    print("PROFILE band4_wait_us=%d" % avg_band4_wait_us)
    print("PROFILE band5_wait_us=%d" % avg_band5_wait_us)
    print("PROFILE submit_wait_us=%d" % avg_submit_wait_us)
    print("PROFILE submit_kick_us=%d" % avg_submit_kick_us)
    print("PROFILE submit_sync_us=%d" % avg_submit_sync_us)
    print("PROFILE submit_start_us=%d" % avg_submit_start_us)
    print("PROFILE submit_push_us=%d" % avg_submit_push_us)
    print("PROFILE submit_dma_wait_us=%d" % avg_submit_dma_wait_us)
    print("PROFILE submit_end_us=%d" % avg_submit_end_us)
    print("PROFILE submit_swap_us=%d" % avg_submit_swap_us)
    print("PROFILE pacing_us=%d" % avg_pace_us)
    print("PROFILE other_us=%d" % avg_other_us)
    print("PROFILE total_us=%d" % avg_total_us)
    print("PROFILE fps=%.2f" % fps_prof)
    print("PROFILE tail_overlap_update_us=%d" % avg_tail_overlap_update_us)
    print("PROFILE tail_overlap_residual_wait_us=%d" % avg_tail_overlap_residual_wait_us)
    print("PROFILE tail_overlap_total_wait_us=%d" % avg_tail_overlap_total_wait_us)
    print("PROFILE descriptor_us=%d" % avg_descriptor_us)
    print("PROFILE swap_detail_us=%d" % avg_swap_detail_us)
    print("PROFILE dma_elapsed_us=%d" % avg_dma_elapsed_us)
    print("PROFILE tail_dma_elapsed_us=%d" % avg_tail_dma_elapsed_us)


def _avg_update_breakdown(profile_every, prof_update_us, prof_update_break_us):
    n = profile_every
    input_us = prof_update_break_us[0] // n
    object_us = prof_update_break_us[1] // n
    enemy_us = prof_update_break_us[2] // n
    monk_us = prof_update_break_us[3] // n
    swap_us = prof_update_break_us[4] // n
    physics_us = prof_update_break_us[5] // n
    camera_us = prof_update_break_us[6] // n
    respawn_us = prof_update_break_us[7] // n
    misc_us = (prof_update_us // n) - (
        input_us
        + object_us
        + enemy_us
        + monk_us
        + swap_us
        + physics_us
        + camera_us
        + respawn_us
    )
    if misc_us < 0:
        misc_us = 0
    return input_us, object_us, enemy_us, monk_us, swap_us, physics_us, camera_us, respawn_us, misc_us


def _profile_update_part(acc, idx, start_us):
    now_us = ticks_us()
    acc[idx] += ticks_diff(now_us, start_us)
    return now_us


def _emit_update_breakdown(profile_every, prof_update_us, prof_update_break_us):
    input_us, object_us, enemy_us, monk_us, swap_us, physics_us, camera_us, respawn_us, misc_us = _avg_update_breakdown(
        profile_every,
        prof_update_us,
        prof_update_break_us,
    )
    print(
        "UPDATE_BREAK input_us=%d object_us=%d enemy_us=%d monk_us=%d swap_us=%d physics_us=%d camera_us=%d respawn_us=%d misc_us=%d"
        % (input_us, object_us, enemy_us, monk_us, swap_us, physics_us, camera_us, respawn_us, misc_us)
    )


def _emit_step_debug(
    now,
    perf_window_start,
    dbg_every,
    top_hud_fps_text,
    coord_hud_enabled,
    coord_hud_text,
    use_sprite_player,
    frame,
    facing,
    anim_idx,
    moving,
    perf_prefix,
    player_x,
    camera_x,
    input_lr,
    sprite_draw_mode,
    draw_off_x,
    player_screen_x,
    boundary_clamp_last,
    partial_rect_experiment_disabled,
    dirty_last_camera_static,
    dirty_last_rects_count,
    dirty_last_bands_count,
):
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
        print("CAMERA_PLAYER_SPRITE_PERF frame_ms=%.2f fps=%.2f" % (avg_ms, fps))
    print("%s_DBG frame=%d player_x=%d camera_x=%d input_lr=%d" % (perf_prefix, frame, player_x, camera_x, input_lr))
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
    return top_hud_fps_text


def _emit_step4_profile(
    profile_every,
    prof_update_us,
    prof_bg_us,
    prof_world_us,
    prof_sprite_us,
    prof_hud_us,
    prof_submit_us,
    prof_submit_compose_us,
    prof_band_bg_us,
    prof_band_tilemap_us,
    prof_band_object_us,
    prof_band_special_us,
    prof_band_enemy_us,
    prof_band_player_us,
    prof_band0_compose_us,
    prof_band1_compose_us,
    prof_band2_compose_us,
    prof_band3_compose_us,
    prof_band4_compose_us,
    prof_band5_compose_us,
    prof_band0_wait_us,
    prof_band1_wait_us,
    prof_band2_wait_us,
    prof_band3_wait_us,
    prof_band4_wait_us,
    prof_band5_wait_us,
    prof_submit_wait_us,
    prof_submit_kick_us,
    prof_submit_sync_us,
    prof_submit_start_us,
    prof_submit_push_us,
    prof_submit_dma_wait_us,
    prof_submit_end_us,
    prof_submit_swap_us,
    prof_total_us,
    prof_pace_us,
    partial_rect_experiment_disabled,
    dirty_last_camera_static,
    dirty_last_rects_count,
    dirty_last_bands_count,
    dirty_us_acc,
    fallback_us_acc,
    submit_acc,
    avg_tail_overlap_update_us,
    avg_tail_overlap_residual_wait_us,
    avg_tail_overlap_total_wait_us,
    avg_descriptor_us=0,
    avg_swap_detail_us=0,
    prof_dma_elapsed_us=0,
    avg_tail_dma_elapsed_us=0,
):
    n = profile_every
    avg_update_us = prof_update_us // n
    avg_bg_us = prof_bg_us // n
    avg_world_us = prof_world_us // n
    avg_sprite_us = prof_sprite_us // n
    avg_hud_us = prof_hud_us // n
    avg_submit_us = prof_submit_us // n
    avg_submit_compose_us = prof_submit_compose_us // n
    avg_band_bg_us = prof_band_bg_us // n
    avg_band_tilemap_us = prof_band_tilemap_us // n
    avg_band_object_us = prof_band_object_us // n
    avg_band_special_us = prof_band_special_us // n
    avg_band_enemy_us = prof_band_enemy_us // n
    avg_band_player_us = prof_band_player_us // n
    avg_band0_compose_us = prof_band0_compose_us // n
    avg_band1_compose_us = prof_band1_compose_us // n
    avg_band2_compose_us = prof_band2_compose_us // n
    avg_band3_compose_us = prof_band3_compose_us // n
    avg_band4_compose_us = prof_band4_compose_us // n
    avg_band5_compose_us = prof_band5_compose_us // n
    avg_band0_wait_us = prof_band0_wait_us // n
    avg_band1_wait_us = prof_band1_wait_us // n
    avg_band2_wait_us = prof_band2_wait_us // n
    avg_band3_wait_us = prof_band3_wait_us // n
    avg_band4_wait_us = prof_band4_wait_us // n
    avg_band5_wait_us = prof_band5_wait_us // n
    avg_submit_wait_us = prof_submit_wait_us // n
    avg_submit_kick_us = prof_submit_kick_us // n
    avg_submit_sync_us = prof_submit_sync_us // n
    avg_submit_start_us = prof_submit_start_us // n
    avg_submit_push_us = prof_submit_push_us // n
    avg_submit_dma_wait_us = prof_submit_dma_wait_us // n
    avg_submit_end_us = prof_submit_end_us // n
    avg_submit_swap_us = prof_submit_swap_us // n
    avg_dma_elapsed_us = prof_dma_elapsed_us // n
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
    _print_profile_summary(
        avg_update_us,
        avg_bg_us,
        avg_world_us,
        avg_sprite_us,
        avg_hud_us,
        avg_submit_us,
        avg_submit_compose_us,
        avg_band_bg_us,
        avg_band_tilemap_us,
        avg_band_object_us,
        avg_band_special_us,
        avg_band_enemy_us,
        avg_band_player_us,
        avg_band0_compose_us,
        avg_band1_compose_us,
        avg_band2_compose_us,
        avg_band3_compose_us,
        avg_band4_compose_us,
        avg_band5_compose_us,
        avg_band0_wait_us,
        avg_band1_wait_us,
        avg_band2_wait_us,
        avg_band3_wait_us,
        avg_band4_wait_us,
        avg_band5_wait_us,
        avg_submit_wait_us,
        avg_submit_kick_us,
        avg_submit_sync_us,
        avg_submit_start_us,
        avg_submit_push_us,
        avg_submit_dma_wait_us,
        avg_submit_end_us,
        avg_submit_swap_us,
        avg_pace_us,
        avg_other_us,
        avg_total_us,
        fps_prof,
        avg_tail_overlap_update_us,
        avg_tail_overlap_residual_wait_us,
        avg_tail_overlap_total_wait_us,
        avg_descriptor_us,
        avg_swap_detail_us,
        avg_dma_elapsed_us,
        avg_tail_dma_elapsed_us,
    )
    if partial_rect_experiment_disabled:
        if not _runtime_verbose_enabled():
            return dirty_us_acc, fallback_us_acc, submit_acc, _zero_profile_counters()
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
    return dirty_us_acc, fallback_us_acc, submit_acc, _zero_profile_counters()


def _submit_native_band_frame(
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
    objects_rows,
    objects_meta,
    object_animations,
    object_anim_counter,
    anchor_active,
    anchor_x,
    anchor_y,
    anchor_anim_spec,
    anchor_anim_counter,
    enemy_rows,
    enemy_states,
    monk_orb_states,
    monk_encounters,
    enemy_meta,
    enemy_rows_c_buf,
    enemy_rows_c_stride,
    enemy_rows_c_count,
    monk_orb_c_buf,
    monk_orb_c_stride,
    monk_orb_c_count,
    monk_attack_c_buf,
    monk_attack_c_stride,
    monk_attack_c_count,
    enemy_monk_sheet,
    enemy_monk_frame_w,
    enemy_monk_frame_h,
    enemy_monk_frame_count,
    enemy_monk_frame_hold,
    enemy_bullets,
    enemy_bullet_native_sprite_right,
    enemy_bullet_native_sprite_left,
    enemy_bullet_w,
    enemy_bullet_h,
    enemy_bullet_cull_margin,
    enemy_render_margin_x,
    enemy_render_margin_y,
    objects_c_buf,
    objects_c_stride,
    objects_c_count,
    objects_atlas,
    objects_atlas_w,
    objects_atlas_h,
    sprite_left,
    sprite_right,
    anim_idx,
    facing,
    sprite_w,
    sprite_h,
    player_screen_x,
    draw_off_x,
    player_y,
    draw_off_y,
    band_top,
    respawn_sheet_native,
    respawn_frame_w,
    respawn_frame_h,
    respawn_frame_count,
    anchor_sheet_native,
    anchor_frame_w_native,
    anchor_frame_h_native,
    anchor_frame_count_native,
    enemy_render_enabled,
    enemy_sheet,
    enemy_sheet_w,
    enemy_sheet_h,
    enemy_frame_hold,
    enemy_monk_orb_atlas,
    enemy_monk_orb_atlas_w,
    enemy_monk_orb_atlas_h,
    native_probe_disable_tilemap,
    native_probe_disable_objects,
    native_probe_disable_enemies,
    native_probe_disable_overlays,
    native_probe_disable_far,
    dirty_log_countdown,
    defer_final_wait,
    swap_preview_state=None,
):
    submit_t0 = ticks_us()
    desc_t0 = submit_t0
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
    special_desc_buf, special_desc_stride, special_desc_count = _pack_special_object_descriptors(
        objects_rows,
        objects_meta,
        object_animations,
        object_anim_counter,
        anchor_active,
        anchor_x,
        anchor_y,
        anchor_anim_spec,
        anchor_anim_counter,
        camera_x,
        sw,
        sh,
    )
    monk_orb_desc_native = _pack_monk_orb_descriptors_native(
        enemy_rows_c_buf,
        enemy_rows_c_stride,
        enemy_rows_c_count,
        monk_orb_c_buf,
        monk_orb_c_stride,
        monk_orb_c_count,
        monk_orb_states,
        camera_x,
        sw,
        sh,
        enemy_monk_frame_w,
        enemy_monk_frame_h,
    )
    if monk_orb_desc_native is None:
        monk_orb_desc_buf, monk_orb_desc_stride, monk_orb_desc_count = _pack_monk_orb_descriptors(
            enemy_rows,
            enemy_states,
            monk_orb_states,
            enemy_meta,
            camera_x,
            sw,
            sh,
            enemy_monk_frame_w,
            enemy_monk_frame_h,
        )
    else:
        monk_orb_desc_buf, monk_orb_desc_stride, monk_orb_desc_count = monk_orb_desc_native
    intro_orb_desc_buf, intro_orb_desc_stride, intro_orb_desc_count = _pack_monk_encounter_intro_orb_descriptors(
        monk_encounters,
        camera_x,
        sw,
        sh,
    )
    if intro_orb_desc_count > 0:
        if monk_orb_desc_count <= 0:
            monk_orb_desc_buf = intro_orb_desc_buf
            monk_orb_desc_stride = intro_orb_desc_stride
            monk_orb_desc_count = intro_orb_desc_count
        else:
            monk_orb_desc_buf.extend(intro_orb_desc_buf)
            monk_orb_desc_count += intro_orb_desc_count
    final_path_desc_buf, final_path_desc_stride, final_path_desc_count = _pack_monk_final_path_descriptors(
        monk_attack_c_buf,
        monk_attack_c_stride,
        monk_attack_c_count,
        camera_x,
        sw,
        sh,
    )
    if final_path_desc_count > 0:
        if special_desc_count <= 0:
            special_desc_buf = final_path_desc_buf
            special_desc_stride = final_path_desc_stride
            special_desc_count = final_path_desc_count
        else:
            special_desc_buf.extend(final_path_desc_buf)
            special_desc_count += final_path_desc_count
    if monk_orb_desc_count > 0:
        if special_desc_count <= 0:
            special_desc_buf = monk_orb_desc_buf
            special_desc_stride = monk_orb_desc_stride
            special_desc_count = monk_orb_desc_count
        else:
            special_desc_buf.extend(monk_orb_desc_buf)
            special_desc_count += monk_orb_desc_count
    preview_desc_buf, preview_desc_stride, preview_desc_count = _pack_swap_preview_descriptor(
        swap_preview_state,
        camera_x,
        sw,
        sh,
    )
    if preview_desc_count > 0:
        if special_desc_count <= 0:
            special_desc_buf = preview_desc_buf
            special_desc_stride = preview_desc_stride
            special_desc_count = preview_desc_count
        else:
            special_desc_buf.extend(preview_desc_buf)
            special_desc_count += preview_desc_count
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
        enemy_rows,
        enemy_meta,
        enemy_monk_sheet,
        enemy_monk_frame_w,
        enemy_monk_frame_h,
        enemy_monk_frame_count,
        object_anim_counter // enemy_monk_frame_hold,
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
        enemy_meta,
        camera_x,
        sw,
        sh,
        enemy_render_margin_x,
        enemy_render_margin_y,
        enemy_monk_frame_w,
        enemy_monk_frame_h,
    )
    _apply_monk_death_render_state(
        enemy_desc_buf,
        enemy_desc_stride,
        enemy_desc_count,
        monk_attack_c_buf,
        monk_attack_c_stride,
        monk_attack_c_count,
    )
    intro_enemy_desc_buf, intro_enemy_desc_stride, intro_enemy_desc_count = _pack_monk_encounter_intro_body_descriptors(
        monk_encounters,
        camera_x,
        sw,
        sh,
        enemy_monk_frame_w,
        enemy_monk_frame_h,
    )
    if intro_enemy_desc_count > 0:
        if enemy_desc_count <= 0:
            enemy_desc_buf = intro_enemy_desc_buf
            enemy_desc_stride = intro_enemy_desc_stride
            enemy_desc_count = intro_enemy_desc_count
        else:
            enemy_desc_buf.extend(intro_enemy_desc_buf)
            enemy_desc_count += intro_enemy_desc_count
    descriptor_us = ticks_diff(ticks_us(), desc_t0)
    native_object_count = objects_c_count
    native_enemy_count = enemy_desc_count
    native_overlay_count = overlay_count
    native_tilemap_w = tilemap_w
    native_tilemap_h = tilemap_h
    if native_probe_disable_tilemap:
        native_tilemap_w = 0
        native_tilemap_h = 0
    if native_probe_disable_objects:
        native_object_count = 0
    if native_probe_disable_enemies:
        native_enemy_count = 0
    if native_probe_disable_overlays:
        native_overlay_count = 0
    native_probe_flags = 0
    if native_probe_disable_far:
        native_probe_flags |= 0x1
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
                native_tilemap_w,
                native_tilemap_h,
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
                native_object_count,
                spr_rgb,
                sprite_w,
                sprite_h,
                spr_x,
                sprite_y,
                player_colorkey_raw,
                overlay_desc_buf,
                overlay_stride,
                native_overlay_count,
                overlay_frames,
                special_desc_buf,
                special_desc_stride,
                special_desc_count,
                respawn_sheet_native,
                respawn_frame_w,
                respawn_frame_h,
                respawn_frame_count,
                anchor_sheet_native,
                anchor_frame_w_native,
                anchor_frame_h_native,
                anchor_frame_count_native,
                object_colorkey,
                enemy_desc_buf,
                enemy_desc_stride,
                native_enemy_count,
                enemy_sheet,
                enemy_sheet_w,
                enemy_sheet_h,
                enemy_monk_sheet,
                enemy_monk_frame_w,
                enemy_monk_frame_h,
                enemy_monk_frame_count,
                enemy_monk_frame_hold,
                enemy_monk_orb_atlas if enemy_monk_orb_atlas is not None else b"",
                enemy_monk_orb_atlas_w,
                enemy_monk_orb_atlas_h,
                object_colorkey,
                enemy_frame_hold,
                native_probe_flags,
                False,
                defer_final_wait,
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
                native_tilemap_w,
                native_tilemap_h,
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
                native_object_count,
                spr_rgb,
                sprite_w,
                sprite_h,
                spr_x,
                sprite_y,
                player_colorkey_raw,
                overlay_desc_buf,
                overlay_stride,
                native_overlay_count,
                overlay_frames,
                special_desc_buf,
                special_desc_stride,
                special_desc_count,
                respawn_sheet_native,
                respawn_frame_w,
                respawn_frame_h,
                respawn_frame_count,
                anchor_sheet_native,
                anchor_frame_w_native,
                anchor_frame_h_native,
                anchor_frame_count_native,
                object_colorkey,
                native_probe_flags,
                False,
                defer_final_wait,
            )
    except Exception:
        print("BAND_PIPELINE_NATIVE_FAIL")
        raise
    us = ticks_diff(ticks_us(), submit_t0)
    (
        band_count,
        band_compose_us,
        kick_us,
        wait_us,
        sync_us,
        start_us,
        push_us,
        wait_dma_us,
        end_us,
        band_bg_us,
        band_tilemap_us,
        band_object_us,
        band_special_us,
        band_enemy_us,
        band_player_us,
        band0_compose_us,
        band1_compose_us,
        band2_compose_us,
        band3_compose_us,
        band4_compose_us,
        band5_compose_us,
        band0_wait_us,
        band1_wait_us,
        band2_wait_us,
        band3_wait_us,
        band4_wait_us,
        band5_wait_us,
        dma_elapsed_us,
    ) = _unpack_band_profile_result(band_res)
    if dirty_log_countdown <= 0:
        print("BAND_PIPELINE_SUBMIT_OK")
        dirty_log_countdown = 30
    if dirty_log_countdown > 0:
        dirty_log_countdown -= 1
    return (
        sprite_x,
        sprite_y,
        spr_y,
        us,
        band_count,
        band_compose_us,
        kick_us,
        wait_us,
        sync_us,
        start_us,
        push_us,
        wait_dma_us,
        end_us,
        band_bg_us,
        band_tilemap_us,
        band_object_us,
        band_special_us,
        band_enemy_us,
        band_player_us,
        band0_compose_us,
        band1_compose_us,
        band2_compose_us,
        band3_compose_us,
        band4_compose_us,
        band5_compose_us,
        band0_wait_us,
        band1_wait_us,
        band2_wait_us,
        band3_wait_us,
        band4_wait_us,
        band5_wait_us,
        dma_elapsed_us,
        dirty_log_countdown,
        descriptor_us,
    )


def _print_camera_test_start(mode):
    print("APP_RUN_START_PHASE_CAMERA_TEST_V2")
    print("CAMERA_TEST_START")
    print("CAMERA_TEST_BOOT_SOURCE=%s" % _boot_source_tag)
    print("CAMERA_TEST_MODE=%s" % mode)
    if mode == _MODE_ROWS_SAFE_PROGRESSIVE:
        print("CAMERA_ROWS_SAFE_POLICY_ACTIVE")


def run(max_frames=None):
    mode = _normalize_mode(getattr(config, "CAMERA_TEST_MODE", _MODE_ROWS_SAFE_PROGRESSIVE))

    _ensure_prerequisites(mode)

    _print_camera_test_start(mode)

    _lgfx.init()
    try:
        _lgfx.rotation(1)
    except Exception:
        pass

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
            camera_x = 0
            monk_platform_camera_locked = False
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
            object_gravity_update_margin_x = int(getattr(config, "OBJECT_GRAVITY_UPDATE_MARGIN_X", 160))
            object_gravity_update_margin_y = int(getattr(config, "OBJECT_GRAVITY_UPDATE_MARGIN_Y", 80))
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
            last_swap_ms = -1000000
            map_exit_latched = False
            swap_preview_state = bytearray(_SWAP_PREVIEW_STATE_STRIDE)
            swap_input_state = bytearray(_SWAP_INPUT_STATE_STRIDE)
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
            (
                prof_update_us,
                prof_bg_us,
                prof_world_us,
                prof_sprite_us,
                prof_hud_us,
                prof_submit_us,
                prof_submit_compose_us,
                prof_band_bg_us,
                prof_band_tilemap_us,
                prof_band_object_us,
                prof_band_special_us,
                prof_band_enemy_us,
                prof_band_player_us,
                prof_band0_compose_us,
                prof_band1_compose_us,
                prof_band2_compose_us,
                prof_band3_compose_us,
                prof_band4_compose_us,
                prof_band5_compose_us,
                prof_band0_wait_us,
                prof_band1_wait_us,
                prof_band2_wait_us,
                prof_band3_wait_us,
                prof_band4_wait_us,
                prof_band5_wait_us,
                prof_submit_wait_us,
                prof_submit_kick_us,
                prof_submit_sync_us,
                prof_submit_start_us,
                prof_submit_push_us,
                prof_submit_dma_wait_us,
                prof_submit_end_us,
                prof_submit_swap_us,
                prof_total_us,
                prof_pace_us,
                prof_dma_elapsed_us,
            ) = _zero_profile_counters()
            prof_desc_us = 0
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
            tail_overlap_update_acc = 0
            tail_overlap_residual_wait_acc = 0
            tail_overlap_total_wait_acc = 0
            tail_dma_elapsed_acc = 0
            prof_update_break_us = [0, 0, 0, 0, 0, 0, 0, 0]
            native_tail_inflight = False
            floor_layer_enabled = bool(getattr(config, "FLOOR_LAYER_ENABLED", False))
            tilemap_enabled = bool(getattr(config, "TILEMAP_ENABLED", True))
            tilemap_rows = None
            if tilemap_enabled:
                csv_path = _resolve_asset_path(getattr(config, "TILEMAP_CSV_PATH", "game/Tilemap/map_tilemap.csv"))
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
            objects_atlas_path = _resolve_asset_path(getattr(config, "OBJECTS_ATLAS_RGB565_PATH", "game/picture/object/object_altes_wire.rgb565"))
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
            (
                objects_rows,
                objects_meta,
                objects_atlas,
                objects_c_buf,
                objects_c_stride,
                objects_c_count,
                object_state_c_buf,
                object_state_c_stride,
                object_state_c_count,
                object_solids,
                object_solids_c_buf,
                object_solids_c_stride,
                object_solids_c_count,
            ) = object_native.init_buffers(objects_rows, objects_meta, objects_atlas, objects_compose_impl_cfg, _lgfx)
            enemy_rt = _load_enemy_runtime_assets(objects_atlas, objects_atlas_w, objects_atlas_h, objects_atlas_path)
            enemy_detect_x = enemy_rt["enemy_detect_x"]
            enemy_flee_x = enemy_rt["enemy_flee_x"]
            enemy_detect_y = enemy_rt["enemy_detect_y"]
            enemy_move_speed = enemy_rt["enemy_move_speed"]
            enemy_gravity_step = enemy_rt["enemy_gravity_step"]
            enemy_shoot_interval = enemy_rt["enemy_shoot_interval"]
            enemy_shoot_fire_frame = enemy_rt["enemy_shoot_fire_frame"]
            enemy_bullet_w = enemy_rt["enemy_bullet_w"]
            enemy_bullet_h = enemy_rt["enemy_bullet_h"]
            enemy_bullet_speed = enemy_rt["enemy_bullet_speed"]
            enemy_max_bullets = enemy_rt["enemy_max_bullets"]
            enemy_update_margin_x = enemy_rt["enemy_update_margin_x"]
            enemy_update_margin_y = enemy_rt["enemy_update_margin_y"]
            enemy_render_margin_x = enemy_rt["enemy_render_margin_x"]
            enemy_render_margin_y = enemy_rt["enemy_render_margin_y"]
            enemy_bullet_cull_margin = enemy_rt["enemy_bullet_cull_margin"]
            enemy_bullet_color = enemy_rt["enemy_bullet_color"]
            enemy_rows = enemy_rt["enemy_rows"]
            enemy_meta = enemy_rt["enemy_meta"]
            enemy_rows_initial = enemy_rt["enemy_rows_initial"]
            monk_encounters = enemy_rt["monk_encounters"]
            enemy_rows_c_buf = enemy_rt["enemy_rows_c_buf"]
            enemy_rows_c_stride = enemy_rt["enemy_rows_c_stride"]
            enemy_rows_c_count = enemy_rt["enemy_rows_c_count"]
            monk_hover_c_buf = enemy_rt["monk_hover_c_buf"]
            monk_hover_c_stride = enemy_rt["monk_hover_c_stride"]
            monk_hover_c_count = enemy_rt["monk_hover_c_count"]
            enemy_states = enemy_rt["enemy_states"]
            enemy_sheet = enemy_rt["enemy_sheet"]
            enemy_sheet_w = enemy_rt["enemy_sheet_w"]
            enemy_sheet_h = enemy_rt["enemy_sheet_h"]
            enemy_frame_w = enemy_rt["enemy_frame_w"]
            enemy_frame_h = enemy_rt["enemy_frame_h"]
            enemy_frame_hold = enemy_rt["enemy_frame_hold"]
            enemy_monk_sheet = enemy_rt["enemy_monk_sheet"]
            enemy_monk_frame_w = enemy_rt["enemy_monk_frame_w"]
            enemy_monk_frame_h = enemy_rt["enemy_monk_frame_h"]
            enemy_monk_frame_count = enemy_rt["enemy_monk_frame_count"]
            enemy_monk_frame_hold = enemy_rt["enemy_monk_frame_hold"]
            enemy_monk_orb_atlas = enemy_rt["enemy_monk_orb_atlas"]
            enemy_monk_orb_atlas_w = enemy_rt["enemy_monk_orb_atlas_w"]
            enemy_monk_orb_atlas_h = enemy_rt["enemy_monk_orb_atlas_h"]
            monk_orb_states = enemy_rt["monk_orb_states"]
            monk_orb_c_buf = enemy_rt["monk_orb_c_buf"]
            monk_orb_c_stride = enemy_rt["monk_orb_c_stride"]
            monk_orb_c_count = enemy_rt["monk_orb_c_count"]
            monk_attack_c_buf = enemy_rt["monk_attack_c_buf"]
            monk_attack_c_stride = enemy_rt["monk_attack_c_stride"]
            monk_attack_c_count = enemy_rt["monk_attack_c_count"]
            monk_attack_states = enemy_rt["monk_attack_states"]
            monk_intro_states = enemy_rt["monk_intro_states"]
            enemy_bullets = enemy_rt["enemy_bullets"]
            enemy_update_native_ready = enemy_rt["enemy_update_native_ready"]
            enemy_render_enabled = enemy_rt["enemy_render_enabled"]
            if enemy_rows:
                print("ENEMY_MODE_ON")
                print("ENEMY_COUNT=%d" % len(enemy_rows))
                print("ENEMY_RENDER_READY=%d" % (1 if enemy_render_enabled else 0))
                print("ENEMY_UPDATE_IMPL=%s" % ("C_API" if enemy_update_native_ready else "PYTHON"))
                print("MONK_ORB_UPDATE_IMPL=%s" % ("C_API" if _monk_orb_native_ready() else "PYTHON"))
                print("MONK_ORB_DESC_IMPL=%s" % ("C_API" if _monk_orb_descriptors_native_ready() else "PYTHON"))
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
            respawn_anim_spec = object_animations.get("respawn_stone")
            respawn_sheet_native = respawn_anim_spec.get("sheet") if respawn_anim_spec else None
            respawn_frame_w = int(respawn_anim_spec.get("frame_w", 0) or 0) if respawn_anim_spec else 0
            respawn_frame_h = int(respawn_anim_spec.get("frame_h", 0) or 0) if respawn_anim_spec else 0
            respawn_frame_count = int(respawn_anim_spec.get("frame_count", len(respawn_anim_spec.get("frames") or [])) or 0) if respawn_anim_spec else 0
            anchor_sheet_native = anchor_anim_spec.get("sheet") if anchor_anim_spec else None
            anchor_frame_w_native = int(anchor_anim_spec.get("frame_w", 0) or 0) if anchor_anim_spec else 0
            anchor_frame_h_native = int(anchor_anim_spec.get("frame_h", 0) or 0) if anchor_anim_spec else 0
            anchor_frame_count_native = int(anchor_anim_spec.get("frame_count", len(anchor_anim_spec.get("frames") or [])) or 0) if anchor_anim_spec else 0
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

            submit_async_cfg = bool(getattr(config, "CAMERA_RENDER_BACK_BUFFER", True))
            submit_wire_order_cfg = bool(getattr(config, "CAMERA_RENDER_WIRE_ORDER", True))
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
            native_probe_disable_objects = bool(getattr(config, "CAMERA_PROBE_DISABLE_OBJECT_BAND", False))
            native_probe_disable_enemies = bool(getattr(config, "CAMERA_PROBE_DISABLE_ENEMY_BAND", False))
            native_probe_disable_overlays = bool(getattr(config, "CAMERA_PROBE_DISABLE_OVERLAY_BAND", False))
            native_probe_disable_tilemap = bool(getattr(config, "CAMERA_PROBE_DISABLE_TILEMAP_BAND", False))
            native_probe_disable_far = bool(getattr(config, "CAMERA_PROBE_DISABLE_FAR_BAND", False))
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
                print(
                    "BAND_PROBE_DISABLE far=%d tilemap=%d objects=%d enemies=%d overlays=%d"
                    % (
                        1 if native_probe_disable_far else 0,
                        1 if native_probe_disable_tilemap else 0,
                        1 if native_probe_disable_objects else 0,
                        1 if native_probe_disable_enemies else 0,
                        1 if native_probe_disable_overlays else 0,
                    )
                )
            elif bool(getattr(config, "CAMERA_BAND_PIPELINE_NATIVE", False)):
                print("BAND_PIPELINE_NATIVE_FALLBACK")
            native_tail_overlap_enabled = (
                native_band_pipeline_enabled
                and hasattr(_lgfx, "band_pipeline_tail_wait")
                and bool(getattr(config, "CAMERA_BAND_TAIL_OVERLAP_UPDATE", False))
            )

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
                update_part_t0 = seg_t0
                input_system.update(now)
                input_lr = int(getattr(input_system, "joy_x_axis", 0))
                move_x = 0
                if input_lr > 20:
                    move_x = speed
                    facing = 1
                elif input_lr < -20:
                    move_x = -speed
                    facing = -1

                if death_state == 0 and _map_exit_triggered(input_system, player_x):
                    if not map_exit_latched:
                        map_exit_latched = True
                        next_stage = str(getattr(config, "MAP_EXIT_NEXT_STAGE", "stage02") or "stage02")
                        print("MAP_EXIT_TRIGGER next=%s x=%d" % (next_stage, int(player_x)))
                        _request_stage_reset(next_stage)
                elif not getattr(input_system, "btn_a_down", False):
                    map_exit_latched = False

                # User-mapped keys: B=far swap, Y=near swap.
                if death_state == 0:
                    swap_triggered, swap_pick_far, swap_locked_target = _swap_hold_step(input_system, swap_preview_state, swap_input_state)
                else:
                    swap_triggered = False
                    swap_pick_far = False
                    swap_locked_target = None
                    _swap_hold_cancel(input_system, swap_preview_state, swap_input_state)

                if swap_triggered:
                    if _runtime_verbose_enabled():
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
                update_part_t0 = _profile_update_part(prof_update_break_us, 0, update_part_t0)

                object_solids, object_solids_c_count = object_native.update_frame(
                    objects_rows,
                    objects_meta,
                    _lgfx,
                    _runtime_verbose_enabled(),
                    object_state_c_buf,
                    object_state_c_stride,
                    object_state_c_count,
                    objects_c_buf,
                    objects_c_stride,
                    object_solids,
                    object_solids_c_buf,
                    object_solids_c_stride,
                    object_solids_c_count,
                    tilemap_idx,
                    tilemap_w,
                    tilemap_h,
                    tile_size,
                    object_gravity_enabled,
                    object_gravity_step,
                    map_h_px,
                    death_margin,
                    camera_x,
                    sw,
                    sh,
                    object_gravity_update_margin_x,
                    object_gravity_update_margin_y,
                    _aabb_near_view,
                    _aabb_collides_tilemap,
                )
                update_part_t0 = _profile_update_part(prof_update_break_us, 1, update_part_t0)
                if death_state == 0:
                    enemy_update_out = _update_enemies_and_bullets_native(
                        enemy_rows,
                        enemy_meta,
                        enemy_states,
                        enemy_bullets,
                        enemy_rows_c_buf,
                        enemy_rows_c_stride,
                        enemy_rows_c_count,
                        monk_hover_c_buf,
                        monk_hover_c_stride,
                        monk_hover_c_count,
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
                    update_part_t0 = _profile_update_part(prof_update_break_us, 2, update_part_t0)

                    if monk_orb_c_count != (len(monk_orb_states) * _MONK_ORB_COUNT):
                        monk_orb_c_buf, monk_orb_c_stride, monk_orb_c_count = _pack_monk_orbs_for_c(monk_orb_states)
                        enemy_rt["monk_orb_c_buf"] = monk_orb_c_buf
                        enemy_rt["monk_orb_c_stride"] = monk_orb_c_stride
                        enemy_rt["monk_orb_c_count"] = monk_orb_c_count
                    monk_attack_c_buf, monk_attack_c_stride, monk_attack_c_count = _ensure_monk_attack_c_count(
                        monk_attack_c_buf,
                        monk_attack_c_stride,
                        monk_attack_c_count,
                        len(enemy_rows),
                    )
                    enemy_rt["monk_attack_c_buf"] = monk_attack_c_buf
                    enemy_rt["monk_attack_c_stride"] = monk_attack_c_stride
                    enemy_rt["monk_attack_c_count"] = monk_attack_c_count
                    monk_attack_was_active = _monk_attack_c_has_active(
                        monk_attack_c_buf,
                        monk_attack_c_stride,
                        monk_attack_c_count,
                    )
                    if monk_attack_was_active:
                        _update_monk_attack_native(
                            monk_attack_c_buf,
                            monk_attack_c_stride,
                            monk_attack_c_count,
                            enemy_rows_c_buf,
                            enemy_rows_c_stride,
                            enemy_rows_c_count,
                            monk_hover_c_buf,
                            monk_hover_c_stride,
                            monk_hover_c_count,
                            monk_orb_c_buf,
                            monk_orb_c_stride,
                            monk_orb_c_count,
                            player_x,
                            player_w,
                            player_y,
                            player_h,
                            camera_x,
                            sw,
                            sh,
                        )
                        _sync_enemy_rows_from_c(enemy_rows, enemy_rows_c_buf, enemy_rows_c_stride)
                        if _update_monk_defeated_state(enemy_rt):
                            monk_platform_camera_locked = False
                    if not _update_monk_orbs_native(
                        monk_orb_states,
                        monk_orb_c_buf,
                        monk_orb_c_stride,
                        monk_orb_c_count,
                        enemy_rows_c_buf,
                        enemy_rows_c_stride,
                        enemy_rows_c_count,
                        enemy_states,
                        enemy_monk_frame_w,
                        enemy_monk_frame_h,
                    ):
                        ei = 0
                        while ei < len(monk_orb_states):
                            slot_states = monk_orb_states[ei]
                            if slot_states is not None:
                                si = 0
                                while si < len(slot_states):
                                    slot_states[si]["native_current_valid"] = 0
                                    si += 1
                            ei += 1

                    if not monk_attack_was_active:
                        _update_monk_attack_native(
                            monk_attack_c_buf,
                            monk_attack_c_stride,
                            monk_attack_c_count,
                            enemy_rows_c_buf,
                            enemy_rows_c_stride,
                            enemy_rows_c_count,
                            monk_hover_c_buf,
                            monk_hover_c_stride,
                            monk_hover_c_count,
                            monk_orb_c_buf,
                            monk_orb_c_stride,
                            monk_orb_c_count,
                            player_x,
                            player_w,
                            player_y,
                            player_h,
                            camera_x,
                            sw,
                            sh,
                        )
                        _sync_enemy_rows_from_c(enemy_rows, enemy_rows_c_buf, enemy_rows_c_stride)
                        if _update_monk_defeated_state(enemy_rt):
                            monk_platform_camera_locked = False
                    update_part_t0 = _profile_update_part(prof_update_break_us, 3, update_part_t0)

                    if swap_input_state[2]:
                        _swap_preview_update_native(
                            swap_preview_state,
                            objects_rows,
                            enemy_rows_c_buf,
                            enemy_rows_c_stride,
                            enemy_rows_c_count,
                            enemy_bullets,
                            monk_orb_c_buf,
                            monk_orb_c_stride,
                            monk_orb_c_count,
                            player_x,
                            player_y,
                            player_w,
                            player_h,
                            swap_pick_far,
                            camera_x,
                            band_top,
                            sw,
                            scene_h,
                        )

                    if swap_triggered and swap_locked_target is not None:
                        if not _swap_preview_target_valid(swap_locked_target, objects_rows, enemy_rows, enemy_bullets, monk_orb_c_buf, monk_orb_c_stride):
                            swap_triggered = False
                            swap_locked_target = None

                    player_x, player_y, vel_y, object_solids = _perform_world_swap(
                        swap_triggered,
                        swap_pick_far,
                        objects_rows,
                        objects_meta,
                        enemy_rows,
                        enemy_states,
                        monk_orb_states,
                        enemy_meta,
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
                        enemy_monk_frame_w,
                        enemy_monk_frame_h,
                        monk_intro_states,
                        monk_orb_c_buf,
                        monk_orb_c_stride,
                        monk_orb_c_count,
                        enemy_rows_c_buf,
                        enemy_rows_c_stride,
                        enemy_rows_c_count,
                        swap_locked_target,
                    )
                    if swap_triggered:
                        _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
                        object_solids_c_count = object_native.sync_solids_from_list(object_solids_c_buf, object_solids_c_stride, object_solids)
                        object_native.sync_states_from_rows(object_state_c_buf, object_state_c_stride, objects_rows, objects_meta)
                    update_part_t0 = _profile_update_part(prof_update_break_us, 4, update_part_t0)

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
                    update_part_t0 = _profile_update_part(prof_update_break_us, 5, update_part_t0)

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

                    monk_orb_kill = None
                    if monk_orb_damage is not None:
                        monk_orb_kill = monk_orb_damage.action_hit_player(
                            monk_orb_c_buf,
                            monk_orb_c_stride,
                            monk_orb_c_count,
                            player_x,
                            player_y,
                            player_w,
                            player_h,
                        )
                    if monk_orb_kill is not None:
                        orb_index, orb_mode, orb_x, orb_y = monk_orb_kill
                        player_y = map_h_px + death_margin + 1
                        print("PLAYER_KILLED_BY_MONK_ORB index=%d mode=%d x=%d y=%d" % (orb_index, orb_mode, orb_x, orb_y))

                    if death_state == 0 and player_y > (map_h_px + death_margin):
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
                        row = _respawn_checkpoint_row(checkpoint_index, objects_rows, objects_rows_initial)
                        if row is not None:
                            death_camera_target_x = _clamp(int(row[0]) + (int(row[2]) // 2) - screen_half, 0, camera_max)
                        else:
                            death_camera_target_x = 0
                        print("PLAYER_DEAD_WAIT_RESPAWN checkpoint=%d camera_target=%d" % (checkpoint_index, death_camera_target_x))

                    if death_state == 0:
                        player_center_x = player_x + (player_w // 2)
                        target_camera_x = player_center_x - screen_half
                        if monk_platform_camera_locked and not enemy_rt.get("monk_defeated"):
                            camera_x = 1600
                        else:
                            camera_x = _clamp(target_camera_x, 0, camera_max)
                            if camera_x >= 1600 and not enemy_rt.get("monk_defeated"):
                                camera_x = 1600
                                monk_platform_camera_locked = True
                                if monk_intro_states:
                                    ei = 0
                                    while ei < len(monk_intro_states):
                                        intro_state = monk_intro_states[ei]
                                        if intro_state is not None and int(intro_state.get("state", _MONK_INTRO_STATE_IDLE) or _MONK_INTRO_STATE_IDLE) == _MONK_INTRO_STATE_IDLE:
                                            intro_state["armed"] = 1
                                        ei += 1
                        if _runtime_verbose_enabled() and camera_x >= 1500 and (frame % 30) == 0:
                            print("CAMERA_LOCK_DBG camera_x=%d target=%d locked=%d player_x=%d" % (int(camera_x), int(target_camera_x), 1 if monk_platform_camera_locked else 0, int(player_x)))
                        _update_monk_encounters(
                            monk_encounters,
                            enemy_rows,
                            enemy_meta,
                            enemy_states,
                            enemy_rows_c_buf,
                            enemy_rows_c_stride,
                            monk_hover_c_buf,
                            monk_hover_c_stride,
                            monk_hover_c_count,
                            monk_orb_states,
                            camera_x,
                            sw,
                            monk_orb_c_buf,
                            monk_orb_c_stride,
                        )
                        if monk_encounters:
                            ei = 0
                            while ei < len(monk_encounters):
                                encounter = monk_encounters[ei]
                                if encounter is not None:
                                    new_enemy_rows_c_count = int(encounter.get("enemy_rows_c_count", enemy_rows_c_count) or enemy_rows_c_count)
                                    if new_enemy_rows_c_count > enemy_rows_c_count:
                                        enemy_rows_c_count = new_enemy_rows_c_count
                                    new_monk_hover_c_count = int(encounter.get("monk_hover_c_count", monk_hover_c_count) or monk_hover_c_count)
                                    if new_monk_hover_c_count > monk_hover_c_count:
                                        monk_hover_c_count = new_monk_hover_c_count
                                ei += 1
                        if monk_platform_camera_locked and not enemy_rt.get("monk_defeated"):
                            _update_monk_intro_states(
                                monk_intro_states,
                                monk_encounters,
                                camera_x,
                                sw,
                            )
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
                    update_part_t0 = _profile_update_part(prof_update_break_us, 6, update_part_t0)
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
                            row = _respawn_checkpoint_row(checkpoint_index, objects_rows, objects_rows_initial)
                            if row is not None:
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
                        if anchor_active and _respawn_confirm_pressed(input_system):
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
                            object_native.restore_rows(
                                objects_rows,
                                objects_rows_initial,
                                objects_c_buf,
                                objects_c_stride,
                                objects_meta,
                                object_state_c_buf,
                                object_state_c_stride,
                            )
                            _restore_enemy_rows(enemy_rows, enemy_rows_initial, enemy_states, enemy_meta)
                            _sync_enemy_rows_c_from_rows(enemy_rows_c_buf, enemy_rows_c_stride, enemy_rows, enemy_meta)
                            if enemy_rt.get("monk_defeated"):
                                _apply_monk_defeated_runtime(enemy_rt)
                            _clear_enemy_bullets(enemy_bullets)
                            if hasattr(enemy_bullets, "ensure_capacity"):
                                enemy_bullets.ensure_capacity(enemy_max_bullets)
                            object_solids = object_native.rebuild_solids(objects_rows)
                            object_solids_c_count = object_native.sync_solids_from_list(object_solids_c_buf, object_solids_c_stride, object_solids)
                            monk_respawn_min_x = int(getattr(config, "MONK_RESPAWN_REINTRO_MIN_X", 1500) or 1500)
                            if (not enemy_rt.get("monk_defeated")) and int(player_x) >= monk_respawn_min_x and _reset_monk_for_respawn_reintro(enemy_rt):
                                monk_platform_camera_locked = True
                                camera_x = 1600
                                print("MONK_RESPAWN_REINTRO_RESET player_x=%d" % int(player_x))
                            death_state = 0
                            monk_platform_camera_locked = True if (camera_x >= 1600 and not enemy_rt.get("monk_defeated")) else False
                            player_center_x = player_x + (player_w // 2)
                            target_camera_x = player_center_x - screen_half
                            if monk_platform_camera_locked and not enemy_rt.get("monk_defeated"):
                                camera_x = 1600
                            else:
                                camera_x = _clamp(target_camera_x, 0, camera_max)
                            player_screen_x = player_x - camera_x
                            print("PLAYER_RESPAWN_OK x=%d y=%d" % (player_x, player_y))
                    player_screen_x = -4096
                    update_part_t0 = _profile_update_part(prof_update_break_us, 7, update_part_t0)

                frame_update_us = ticks_diff(ticks_us(), seg_t0)
                prof_update_us += frame_update_us
                if native_band_pipeline_enabled and hasattr(_lgfx, "band_pipeline_tail_wait"):
                    try:
                        tail_wait_res = _lgfx.band_pipeline_tail_wait()
                        tail_total_wait_us = int(tail_wait_res[0])
                        tail_residual_wait_us = int(tail_wait_res[1])
                        tail_residual_dma_wait_us = int(tail_wait_res[2])
                        tail_end_us = int(tail_wait_res[3])
                        tail_dma_elapsed_us = tail_total_wait_us
                        if len(tail_wait_res) >= 5:
                            tail_dma_elapsed_us = int(tail_wait_res[4])
                    except Exception:
                        native_tail_inflight = False
                        native_tail_overlap_enabled = False
                        print("TAIL_OVERLAP_FALLBACK")
                    else:
                        native_tail_inflight = False
                        overlap_update_us = tail_total_wait_us - tail_residual_wait_us
                        if overlap_update_us < 0:
                            overlap_update_us = 0
                        if overlap_update_us > frame_update_us:
                            overlap_update_us = frame_update_us
                        tail_overlap_update_acc += overlap_update_us
                        tail_overlap_residual_wait_acc += tail_residual_wait_us
                        tail_overlap_total_wait_acc += tail_total_wait_us
                        tail_dma_elapsed_acc += tail_dma_elapsed_us
                        prof_submit_wait_us += tail_residual_wait_us
                        prof_submit_dma_wait_us += tail_residual_dma_wait_us
                        prof_submit_end_us += tail_end_us

                frame_native_band_enabled = native_band_pipeline_enabled

                if frame_native_band_enabled:
                    (
                        sprite_x,
                        sprite_y,
                        spr_y,
                        us,
                        band_count,
                        band_compose_us,
                        kick_us,
                        wait_us,
                        sync_us,
                        start_us,
                        push_us,
                        wait_dma_us,
                        end_us,
                        band_bg_us,
                        band_tilemap_us,
                        band_object_us,
                        band_special_us,
                        band_enemy_us,
                        band_player_us,
                        band0_compose_us,
                        band1_compose_us,
                        band2_compose_us,
                        band3_compose_us,
                        band4_compose_us,
                        band5_compose_us,
                        band0_wait_us,
                        band1_wait_us,
                        band2_wait_us,
                        band3_wait_us,
                        band4_wait_us,
                        band5_wait_us,
                        dma_elapsed_us,
                        dirty_log_countdown,
                        descriptor_us,
                    ) = _submit_native_band_frame(
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
                        objects_rows,
                        objects_meta,
                        object_animations,
                        object_anim_counter,
                        anchor_active,
                        anchor_x,
                        anchor_y,
                        anchor_anim_spec,
                        anchor_anim_counter,
                        enemy_rows,
                        enemy_states,
                        monk_orb_states,
                        monk_encounters,
                        enemy_meta,
                        enemy_rows_c_buf,
                        enemy_rows_c_stride,
                        enemy_rows_c_count,
                        monk_orb_c_buf,
                        monk_orb_c_stride,
                        monk_orb_c_count,
                        monk_attack_c_buf,
                        monk_attack_c_stride,
                        monk_attack_c_count,
                        enemy_monk_sheet,
                        enemy_monk_frame_w,
                        enemy_monk_frame_h,
                        enemy_monk_frame_count,
                        enemy_monk_frame_hold,
                        enemy_bullets,
                        enemy_bullet_native_sprite_right,
                        enemy_bullet_native_sprite_left,
                        enemy_bullet_w,
                        enemy_bullet_h,
                        enemy_bullet_cull_margin,
                        enemy_render_margin_x,
                        enemy_render_margin_y,
                        objects_c_buf,
                        objects_c_stride,
                        objects_c_count,
                        objects_atlas,
                        objects_atlas_w,
                        objects_atlas_h,
                        sprite_left,
                        sprite_right,
                        anim_idx,
                        facing,
                        sprite_w,
                        sprite_h,
                        player_screen_x,
                        draw_off_x,
                        player_y,
                        draw_off_y,
                        band_top,
                        respawn_sheet_native,
                        respawn_frame_w,
                        respawn_frame_h,
                        respawn_frame_count,
                        anchor_sheet_native,
                        anchor_frame_w_native,
                        anchor_frame_h_native,
                        anchor_frame_count_native,
                        enemy_render_enabled,
                        enemy_sheet,
                        enemy_sheet_w,
                        enemy_sheet_h,
                        enemy_frame_hold,
                        enemy_monk_orb_atlas,
                        enemy_monk_orb_atlas_w,
                        enemy_monk_orb_atlas_h,
                        native_probe_disable_tilemap,
                        native_probe_disable_objects,
                        native_probe_disable_enemies,
                        native_probe_disable_overlays,
                        native_probe_disable_far,
                        dirty_log_countdown,
                        native_tail_overlap_enabled,
                        swap_preview_state,
                    )
                    swap_us = 0
                    submit_acc += us
                    prof_submit_us += us
                    prof_submit_compose_us += band_compose_us
                    prof_band_bg_us += band_bg_us
                    prof_band_tilemap_us += band_tilemap_us
                    prof_band_object_us += band_object_us
                    prof_band_special_us += band_special_us
                    prof_band_enemy_us += band_enemy_us
                    prof_band_player_us += band_player_us
                    prof_band0_compose_us += band0_compose_us
                    prof_band1_compose_us += band1_compose_us
                    prof_band2_compose_us += band2_compose_us
                    prof_band3_compose_us += band3_compose_us
                    prof_band4_compose_us += band4_compose_us
                    prof_band5_compose_us += band5_compose_us
                    prof_band0_wait_us += band0_wait_us
                    prof_band1_wait_us += band1_wait_us
                    prof_band2_wait_us += band2_wait_us
                    prof_band3_wait_us += band3_wait_us
                    prof_band4_wait_us += band4_wait_us
                    prof_band5_wait_us += band5_wait_us
                    prof_submit_wait_us += wait_us
                    prof_submit_kick_us += kick_us
                    prof_submit_sync_us += sync_us
                    prof_submit_start_us += start_us
                    prof_submit_push_us += push_us
                    prof_submit_dma_wait_us += wait_dma_us
                    prof_submit_end_us += end_us
                    prof_submit_swap_us += swap_us
                    prof_desc_us += descriptor_us
                    prof_dma_elapsed_us += dma_elapsed_us
                    native_tail_inflight = native_tail_overlap_enabled
                    dirty_last_rects_count = band_count
                    dirty_last_bands_count = band_count
                    dirty_last_camera_static = 1 if camera_x == prev_camera_x else 0
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
                    prof_desc_us += 0
                    dirty_last_rects_count = 2
                    dirty_last_bands_count = 1
                    dirty_last_camera_static = 1 if camera_x == prev_camera_x else 0
                    if _runtime_verbose_enabled():
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
                if _runtime_verbose_enabled():
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
                    if _runtime_verbose_enabled():
                        if coord_hud_enabled and not coord_hud_logged:
                            print("CAMERA_TOP_HUD_DRAW_OK")
                            print("CAMERA_TOP_HUD_POS fps_x=4 fps_y=4 coord_x=%d coord_y=4" % top_hud_coord_x)
                            print("CAMERA_TOP_HUD_VALUE fps=%s coord=%s" % (top_hud_fps_text, coord_hud_text))
                            coord_hud_logged = True
                    drew_once = True

                if _runtime_verbose_enabled() and (frame % dbg_every) == 0:
                    top_hud_fps_text = _emit_step_debug(
                        now,
                        perf_window_start,
                        dbg_every,
                        top_hud_fps_text,
                        coord_hud_enabled,
                        coord_hud_text,
                        use_sprite_player,
                        frame,
                        facing,
                        anim_idx,
                        moving,
                        perf_prefix,
                        player_x,
                        camera_x,
                        input_lr,
                        sprite_draw_mode,
                        draw_off_x,
                        player_screen_x,
                        boundary_clamp_last,
                        partial_rect_experiment_disabled,
                        dirty_last_camera_static,
                        dirty_last_rects_count,
                        dirty_last_bands_count,
                    )
                    perf_window_start = now

                if _runtime_verbose_enabled() and (frame % profile_every) == 0:
                    avg_tail_overlap_update_us = 0
                    avg_tail_overlap_residual_wait_us = 0
                    avg_tail_overlap_total_wait_us = 0
                    avg_tail_dma_elapsed_us = 0
                    if native_tail_overlap_enabled:
                        avg_tail_overlap_update_us = tail_overlap_update_acc // profile_every
                        avg_tail_overlap_residual_wait_us = tail_overlap_residual_wait_acc // profile_every
                        avg_tail_overlap_total_wait_us = tail_overlap_total_wait_acc // profile_every
                        avg_tail_dma_elapsed_us = tail_dma_elapsed_acc // profile_every
                    _input_us, _object_us, _enemy_us, _monk_us, avg_swap_detail_us, _physics_us, _camera_us, _respawn_us, _misc_us = _avg_update_breakdown(
                        profile_every,
                        prof_update_us,
                        prof_update_break_us,
                    )
                    dirty_us_acc, fallback_us_acc, submit_acc, profile_counters = _emit_step4_profile(
                        profile_every,
                        prof_update_us,
                        prof_bg_us,
                        prof_world_us,
                        prof_sprite_us,
                        prof_hud_us,
                        prof_submit_us,
                        prof_submit_compose_us,
                        prof_band_bg_us,
                        prof_band_tilemap_us,
                        prof_band_object_us,
                        prof_band_special_us,
                        prof_band_enemy_us,
                        prof_band_player_us,
                        prof_band0_compose_us,
                        prof_band1_compose_us,
                        prof_band2_compose_us,
                        prof_band3_compose_us,
                        prof_band4_compose_us,
                        prof_band5_compose_us,
                        prof_band0_wait_us,
                        prof_band1_wait_us,
                        prof_band2_wait_us,
                        prof_band3_wait_us,
                        prof_band4_wait_us,
                        prof_band5_wait_us,
                        prof_submit_wait_us,
                        prof_submit_kick_us,
                        prof_submit_sync_us,
                        prof_submit_start_us,
                        prof_submit_push_us,
                        prof_submit_dma_wait_us,
                        prof_submit_end_us,
                        prof_submit_swap_us,
                        prof_total_us,
                        prof_pace_us,
                        partial_rect_experiment_disabled,
                        dirty_last_camera_static,
                        dirty_last_rects_count,
                        dirty_last_bands_count,
                        dirty_us_acc,
                        fallback_us_acc,
                        submit_acc,
                        avg_tail_overlap_update_us,
                        avg_tail_overlap_residual_wait_us,
                        avg_tail_overlap_total_wait_us,
                        prof_desc_us // profile_every,
                        avg_swap_detail_us,
                        prof_dma_elapsed_us,
                        avg_tail_dma_elapsed_us,
                    )
                    _emit_update_breakdown(profile_every, prof_update_us, prof_update_break_us)
                    prof_update_break_us = [0, 0, 0, 0, 0, 0, 0, 0]
                    prof_desc_us = 0
                    if native_tail_overlap_enabled:
                        tail_overlap_update_acc = 0
                        tail_overlap_residual_wait_acc = 0
                        tail_overlap_total_wait_acc = 0
                        tail_dma_elapsed_acc = 0
                    (
                        prof_update_us,
                        prof_bg_us,
                        prof_world_us,
                        prof_sprite_us,
                        prof_hud_us,
                        prof_submit_us,
                        prof_submit_compose_us,
                        prof_band_bg_us,
                        prof_band_tilemap_us,
                        prof_band_object_us,
                        prof_band_special_us,
                        prof_band_enemy_us,
                        prof_band_player_us,
                        prof_band0_compose_us,
                        prof_band1_compose_us,
                        prof_band2_compose_us,
                        prof_band3_compose_us,
                        prof_band4_compose_us,
                        prof_band5_compose_us,
                        prof_band0_wait_us,
                        prof_band1_wait_us,
                        prof_band2_wait_us,
                        prof_band3_wait_us,
                        prof_band4_wait_us,
                        prof_band5_wait_us,
                        prof_submit_wait_us,
                        prof_submit_kick_us,
                        prof_submit_sync_us,
                        prof_submit_start_us,
                        prof_submit_push_us,
                        prof_submit_dma_wait_us,
                        prof_submit_end_us,
                        prof_submit_swap_us,
                        prof_total_us,
                        prof_pace_us,
                        prof_dma_elapsed_us,
                    ) = profile_counters

                if max_frames is not None and frame >= int(max_frames):
                    break

            if submit_async_enabled and submit_async_inflight:
                try:
                    w_t0 = ticks_us()
                    _lgfx.blit_wait_done()
                    prof_submit_wait_us += ticks_diff(ticks_us(), w_t0)
                except Exception:
                    pass
            if native_tail_inflight and hasattr(_lgfx, "band_pipeline_tail_wait"):
                try:
                    _lgfx.band_pipeline_tail_wait()
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

    raise RuntimeError("CAMERA_TEST_FAIL_UNSUPPORTED_MODE")
