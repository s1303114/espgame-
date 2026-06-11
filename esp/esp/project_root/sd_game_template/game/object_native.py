OBJECT_STATE_STRIDE = 20
OBJECT_STATE_FLAG_VISIBLE = 1
OBJECT_STATE_FLAG_SOLID = 2
OBJECT_STATE_FLAG_SWAPPABLE = 4
OBJECT_STATE_FLAG_GRAVITY = 8
OBJECT_STATE_FLAG_SPECIAL_RENDER = 16
OBJECT_SOLID_STRIDE = 8


def _buf_get_i16_le(buf, off):
    val = buf[off] | (buf[off + 1] << 8)
    if val & 0x8000:
        val -= 0x10000
    return val


def _buf_get_u16_le(buf, off):
    return buf[off] | (buf[off + 1] << 8)


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


def is_special_render_object(meta):
    return bool(meta and meta.get("special_render"))


def state_flags(row, meta=None):
    flags = 0
    if row is not None:
        if int(row[6]):
            flags |= OBJECT_STATE_FLAG_VISIBLE
        if int(row[4]):
            flags |= OBJECT_STATE_FLAG_SOLID
        if int(row[7]):
            flags |= OBJECT_STATE_FLAG_SWAPPABLE
    if meta is not None:
        if int(meta.get("gravity", 0) or 0) != 0:
            flags |= OBJECT_STATE_FLAG_GRAVITY
        if is_special_render_object(meta):
            flags |= OBJECT_STATE_FLAG_SPECIAL_RENDER
    return flags


def sync_entry_from_row(buf, stride, row_index, row, meta=None):
    if buf is None or stride < OBJECT_STATE_STRIDE or row_index < 0:
        return
    base = int(row_index) * int(stride)
    if base < 0 or (base + OBJECT_STATE_STRIDE) > len(buf):
        return
    _buf_set_i16_le(buf, base + 0, row[0])
    _buf_set_i16_le(buf, base + 2, row[1])
    _buf_set_i16_le(buf, base + 4, row[2])
    _buf_set_i16_le(buf, base + 6, row[3])
    _buf_set_i16_le(buf, base + 8, row[8])
    _buf_set_i16_le(buf, base + 10, row[9])
    _buf_set_i16_le(buf, base + 12, row[10])
    _buf_set_i16_le(buf, base + 14, row[11])
    _buf_set_u16_le(buf, base + 16, state_flags(row, meta))
    _buf_set_u16_le(buf, base + 18, 0)


def pack_states(rows, meta_rows=None):
    if not rows:
        return bytearray(), OBJECT_STATE_STRIDE, 0
    out = bytearray(len(rows) * OBJECT_STATE_STRIDE)
    oi = 0
    while oi < len(rows):
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        sync_entry_from_row(out, OBJECT_STATE_STRIDE, oi, rows[oi], meta)
        oi += 1
    return out, OBJECT_STATE_STRIDE, len(rows)


def sync_states_from_rows(buf, stride, rows, meta_rows=None):
    if buf is None or stride < OBJECT_STATE_STRIDE or not rows:
        return 0
    limit = len(buf) // int(stride)
    if len(rows) < limit:
        limit = len(rows)
    oi = 0
    while oi < limit:
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        sync_entry_from_row(buf, stride, oi, rows[oi], meta)
        oi += 1
    return limit


def sync_rows_from_state(rows, buf, stride):
    if not rows or buf is None or stride < OBJECT_STATE_STRIDE:
        return
    limit = len(buf) // int(stride)
    if len(rows) < limit:
        limit = len(rows)
    i = 0
    while i < limit:
        base = i * int(stride)
        row = rows[i]
        row[0] = _buf_get_i16_le(buf, base + 0)
        row[1] = _buf_get_i16_le(buf, base + 2)
        row[2] = _buf_get_i16_le(buf, base + 4)
        row[3] = _buf_get_i16_le(buf, base + 6)
        row[8] = _buf_get_i16_le(buf, base + 8)
        row[9] = _buf_get_i16_le(buf, base + 10)
        row[10] = _buf_get_i16_le(buf, base + 12)
        row[11] = _buf_get_i16_le(buf, base + 14)
        flags = _buf_get_u16_le(buf, base + 16)
        row[4] = 1 if (flags & OBJECT_STATE_FLAG_SOLID) else 0
        row[6] = 1 if (flags & OBJECT_STATE_FLAG_VISIBLE) else 0
        row[7] = 1 if (flags & OBJECT_STATE_FLAG_SWAPPABLE) else 0
        i += 1


def restore_rows(rows, saved_rows, render_buf, render_stride, meta_rows=None, state_buf=None, state_stride=0):
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
        sync_entry_from_row(state_buf, state_stride, oi, row, meta)
        if row[6]:
            repack_render_entry(render_buf, render_stride, oi, row[0], row[1], row[8], row[9], row[10], row[11], meta)
        else:
            repack_render_entry(render_buf, render_stride, oi, row[0], row[1], 0, 0, 0, 0, meta)
        oi += 1


def pack_solids(object_solids):
    if not object_solids:
        return bytearray(), OBJECT_SOLID_STRIDE, 0
    out = bytearray(len(object_solids) * OBJECT_SOLID_STRIDE)
    i = 0
    bi = 0
    while i < len(object_solids):
        ox, oy, ow, oh = object_solids[i]
        _buf_set_i16_le(out, bi + 0, ox)
        _buf_set_i16_le(out, bi + 2, oy)
        _buf_set_i16_le(out, bi + 4, ow)
        _buf_set_i16_le(out, bi + 6, oh)
        bi += OBJECT_SOLID_STRIDE
        i += 1
    return out, OBJECT_SOLID_STRIDE, len(object_solids)


def sync_solids_from_list(buf, stride, object_solids):
    if buf is None or stride < OBJECT_SOLID_STRIDE:
        return 0
    limit = len(buf) // int(stride)
    src_count = 0 if not object_solids else len(object_solids)
    if src_count < limit:
        limit = src_count
    i = 0
    while i < limit:
        base = i * int(stride)
        ox, oy, ow, oh = object_solids[i]
        _buf_set_i16_le(buf, base + 0, ox)
        _buf_set_i16_le(buf, base + 2, oy)
        _buf_set_i16_le(buf, base + 4, ow)
        _buf_set_i16_le(buf, base + 6, oh)
        i += 1
    while i < (len(buf) // int(stride)):
        base = i * int(stride)
        _buf_set_i16_le(buf, base + 0, 0)
        _buf_set_i16_le(buf, base + 2, 0)
        _buf_set_i16_le(buf, base + 4, 0)
        _buf_set_i16_le(buf, base + 6, 0)
        i += 1
    return src_count


def pack_render(rows, meta_rows=None):
    if not rows:
        return bytearray(), 12, 0
    out = bytearray(len(rows) * 12)
    oi = 0
    while oi < len(rows):
        wx, wy, _ow, _oh, _solid, _layer, visible, _swappable, sx, sy, sw, sh = rows[oi]
        meta = meta_rows[oi] if (meta_rows is not None and oi < len(meta_rows)) else None
        if is_special_render_object(meta) or not visible:
            sx = 0
            sy = 0
            sw = 0
            sh = 0
        bi = oi * 12
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
    return out, 12, len(rows)


def repack_render_entry(buf, stride, row_index, wx, wy, sx, sy, sw, sh, meta=None):
    if buf is None or stride < 12 or row_index < 0:
        return
    base = int(row_index) * int(stride)
    if base + 12 > len(buf):
        return
    if is_special_render_object(meta):
        sx = 0
        sy = 0
        sw = 0
        sh = 0
    bi = base
    for v in (wx, wy, sx, sy, sw, sh):
        iv = int(v)
        if iv < -32768:
            iv = -32768
        if iv > 65535:
            iv = 65535
        uv = iv & 0xFFFF
        buf[bi] = uv & 0xFF
        buf[bi + 1] = (uv >> 8) & 0xFF
        bi += 2


def rebuild_solids(rows):
    out = []
    if not rows:
        return out
    i = 0
    while i < len(rows):
        wx, wy, ow, oh, solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = rows[i]
        if visible and solid:
            out.append((wx, wy, ow, oh))
        i += 1
    return out


def init_buffers(rows, meta_rows, atlas, compose_impl_cfg, lgfx):
    if rows and atlas is not None:
        solids = rebuild_solids(rows)
        solids_buf, solids_stride, solids_count = pack_solids(solids)
        render_buf, render_stride, render_count = pack_render(rows, meta_rows)
        state_buf, state_stride, state_count = pack_states(rows, meta_rows)
        print("OBJECT_MODE_ON")
        print("OBJECT_COUNT=%d" % len(rows))
        print("OBJECT_C_COUNT=%d" % render_count)
        print("OBJECT_STATE_C_COUNT=%d" % state_count)
        print("OBJECT_COMPOSE_IMPL_CFG=%s" % compose_impl_cfg)
        print("OBJECT_SOLID_COUNT=%d" % len(solids))
        print("OBJECT_UPDATE_IMPL=%s" % ("C_API" if (lgfx is not None and hasattr(lgfx, "update_objects_native")) else "PYTHON"))
        return rows, meta_rows, atlas, render_buf, render_stride, render_count, state_buf, state_stride, state_count, solids, solids_buf, solids_stride, solids_count
    print("OBJECT_MODE_OFF")
    return [], [], None, bytearray(), 12, 0, bytearray(), OBJECT_STATE_STRIDE, 0, [], bytearray(), OBJECT_SOLID_STRIDE, 0


def _visible_target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h):
    sx0 = int(wx) - int(camera_x)
    sy0 = int(wy) - int(band_top)
    sx1 = sx0 + int(ow)
    sy1 = sy0 + int(oh)
    cx0 = 0 if sx0 < 0 else sx0
    cy0 = 0 if sy0 < 0 else sy0
    cx1 = int(view_w) if sx1 > int(view_w) else sx1
    cy1 = int(view_h) if sy1 > int(view_h) else sy1
    if cx1 <= cx0 or cy1 <= cy0:
        return -1
    visible_w = cx1 - cx0
    visible_h = cy1 - cy0
    visible_area = visible_w * visible_h
    if visible_w < 10 or visible_h < 10 or visible_area < 128:
        return -1
    px = (int(player_x) - int(camera_x)) + (int(player_w) // 2)
    py = (int(player_y) - int(band_top)) + (int(player_h) // 2)
    ox = (cx0 + cx1) // 2
    oy = (cy0 + cy1) // 2
    dx = ox - px
    dy = oy - py
    return dx * dx + dy * dy


def pick_swappable_index(rows, player_x, player_y, player_w, player_h, pick_far, camera_x, band_top, view_w, view_h):
    if not rows:
        return -1
    best_i = -1
    best_d2 = -1
    oi = 0
    while oi < len(rows):
        wx, wy, ow, oh, _solid, _layer, visible, swappable, _sx, _sy, _sw, _sh = rows[oi]
        if visible and swappable:
            d2 = _visible_target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h, camera_x, band_top, view_w, view_h)
            if d2 >= 0:
                if best_i < 0 or (pick_far and d2 > best_d2) or ((not pick_far) and d2 < best_d2):
                    best_i = oi
                    best_d2 = d2
        oi += 1
    return best_i


def update_gravity_python(rows, meta_rows, render_buf, render_stride, solids, solids_buf, solids_stride, solids_count, tilemap_idx, tilemap_w, tilemap_h, tile_size, gravity_enabled, gravity_step, map_h_px, death_margin, camera_x, view_w, view_h, margin_x, margin_y, aabb_near_view, aabb_collides_tilemap):
    if not (gravity_enabled and gravity_step > 0 and rows and tilemap_idx is not None and tilemap_w > 0 and tilemap_h > 0):
        return solids, solids_count
    moved = False
    oi = 0
    while oi < len(rows):
        row = rows[oi]
        meta = meta_rows[oi] if oi < len(meta_rows) else None
        wx, wy, ow, oh, _solid, _layer, visible, _swappable, _sx, _sy, _sw, _sh = row
        gravity_on = 1 if meta is not None and int(meta.get("gravity", 0) or 0) != 0 else 0
        if visible and gravity_on and ow > 0 and oh > 0 and aabb_near_view(wx, wy, ow, oh, camera_x, view_w, view_h, margin_x, margin_y):
            steps = gravity_step
            moved_y = 0
            removed = False
            while steps > 0:
                ny = int(wy) + 1
                if aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, int(wx), ny, int(ow), int(oh)):
                    break
                wy = ny
                moved_y += 1
                if int(wy) > (map_h_px + death_margin):
                    removed = True
                    break
                steps -= 1
            if removed:
                row[1] = int(wy)
                row[6] = 0
                repack_render_entry(render_buf, render_stride, oi, row[0], row[1], 0, 0, 0, 0, meta)
                moved = True
            elif moved_y > 0:
                row[1] = int(wy)
                repack_render_entry(render_buf, render_stride, oi, row[0], row[1], row[8], row[9], row[10], row[11], meta)
                moved = True
        oi += 1
    if moved:
        solids = rebuild_solids(rows)
        solids_count = sync_solids_from_list(solids_buf, solids_stride, solids)
    return solids, solids_count


def update_native(lgfx, runtime_verbose, state_buf, state_stride, state_count, render_buf, render_stride, solids_buf, solids_stride, solids_capacity, tilemap_idx, tilemap_w, tilemap_h, tile_size, gravity_enabled, gravity_step, map_h_px, death_margin, camera_x, view_w, view_h, margin_x, margin_y):
    if lgfx is None or not hasattr(lgfx, "update_objects_native"):
        return None
    if state_buf is None or state_count <= 0:
        return None
    if render_buf is None or solids_buf is None:
        return None
    if tilemap_idx is None or tilemap_w <= 0 or tilemap_h <= 0 or tile_size <= 0:
        return None
    try:
        out = lgfx.update_objects_native(
            state_buf,
            state_stride,
            state_count,
            render_buf,
            render_stride,
            solids_buf,
            solids_stride,
            solids_capacity,
            tilemap_idx,
            tilemap_w,
            tilemap_h,
            tile_size,
            bool(gravity_enabled),
            gravity_step,
            map_h_px,
            death_margin,
            camera_x,
            view_w,
            view_h,
            margin_x,
            margin_y,
        )
        return int(out[0]), int(out[1])
    except Exception as exc:
        if runtime_verbose:
            print("OBJECT_UPDATE_NATIVE_FALLBACK %r" % (exc,))
        return None


def update_frame(rows, meta_rows, lgfx, runtime_verbose, state_buf, state_stride, state_count, render_buf, render_stride, solids, solids_buf, solids_stride, solids_count, tilemap_idx, tilemap_w, tilemap_h, tile_size, gravity_enabled, gravity_step, map_h_px, death_margin, camera_x, view_w, view_h, margin_x, margin_y, aabb_near_view, aabb_collides_tilemap):
    solids_capacity = len(solids_buf) // int(solids_stride) if solids_stride > 0 else 0
    native_out = update_native(
        lgfx,
        runtime_verbose,
        state_buf,
        state_stride,
        state_count,
        render_buf,
        render_stride,
        solids_buf,
        solids_stride,
        solids_capacity,
        tilemap_idx,
        tilemap_w,
        tilemap_h,
        tile_size,
        gravity_enabled,
        gravity_step,
        map_h_px,
        death_margin,
        camera_x,
        view_w,
        view_h,
        margin_x,
        margin_y,
    )
    if native_out is None:
        return update_gravity_python(
            rows,
            meta_rows,
            render_buf,
            render_stride,
            solids,
            solids_buf,
            solids_stride,
            solids_count,
            tilemap_idx,
            tilemap_w,
            tilemap_h,
            tile_size,
            gravity_enabled,
            gravity_step,
            map_h_px,
            death_margin,
            camera_x,
            view_w,
            view_h,
            margin_x,
            margin_y,
            aabb_near_view,
            aabb_collides_tilemap,
        )
    moved_count, solids_count = native_out
    if moved_count > 0:
        sync_rows_from_state(rows, state_buf, state_stride)
        solids = rebuild_solids(rows)
    return solids, solids_count
