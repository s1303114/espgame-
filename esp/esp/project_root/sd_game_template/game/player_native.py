try:
    import array as _array
except Exception:
    _array = None

_native_disabled = False


def _normal_log(text):
    try:
        import config
        if bool(getattr(config, "CAMERA_QUIET_LOGS", False)):
            return
    except Exception:
        pass
    print(text)


def new_result_buffer():
    if _array is not None:
        return _array.array("i", [0] * 8)
    return [0] * 8


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _tilemap_is_solid(tilemap_idx, tilemap_w, tilemap_h, tx, ty):
    if tilemap_idx is None or tx < 0 or ty < 0 or tx >= tilemap_w or ty >= tilemap_h:
        return False
    return tilemap_idx[(ty * tilemap_w) + tx] != 0


def _aabb_collides_tilemap(tilemap_idx, tilemap_w, tilemap_h, tile_size, x, y, w, h):
    if tilemap_idx is None or tilemap_w <= 0 or tilemap_h <= 0 or tile_size <= 0 or w <= 0 or h <= 0:
        return False
    tx0 = x // tile_size
    ty0 = y // tile_size
    tx1 = (x + w - 1) // tile_size
    ty1 = (y + h - 1) // tile_size
    ty = ty0
    while ty <= ty1:
        tx = tx0
        while tx <= tx1:
            if _tilemap_is_solid(tilemap_idx, tilemap_w, tilemap_h, tx, ty):
                return True
            tx += 1
        ty += 1
    return False


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


def _write_result(result, player_x, player_y, vel_y, grounded, hit_x, hit_y, unembed_steps, flags):
    result[0] = int(player_x)
    result[1] = int(player_y)
    result[2] = int(vel_y)
    result[3] = 1 if grounded else 0
    result[4] = 1 if hit_x else 0
    result[5] = 1 if hit_y else 0
    result[6] = int(unembed_steps)
    result[7] = int(flags)


def _fallback_update(result, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, player_x, player_y, player_w, player_h, move_x, vel_y, gravity, fall_speed_max, max_player_x):
    grounded = False
    hit_x = False
    hit_y = False
    unembed_steps = 0
    if tilemap_idx is not None or object_solids:
        unembed_guard = int(tile_size) * 4
        if unembed_guard < 16:
            unembed_guard = 16
        while unembed_guard > 0 and _aabb_collides_world(player_x, player_y, player_w, player_h, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids):
            player_y -= 1
            unembed_steps += 1
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
        player_x, player_y, hit_x, hit_y = _move_axis_world(tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, player_x, player_y, player_w, player_h, move_x, vel_y)
        if hit_y:
            vel_y = 0
        player_x = _clamp(player_x, 0, max_player_x)
        if player_y < 0:
            player_y = 0
            vel_y = 0
    else:
        player_x += move_x
        player_x = _clamp(player_x, 0, max_player_x)
    _write_result(result, player_x, player_y, vel_y, grounded, hit_x, hit_y, unembed_steps, 0)
    return False


def update_frame(lgfx, result, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, object_solids_c_buf, object_solids_c_stride, object_solids_c_count, player_x, player_y, player_w, player_h, move_x, vel_y, gravity, fall_speed_max, max_player_x):
    global _native_disabled
    if result is None:
        return False
    solid_count = int(object_solids_c_count)
    if object_solids_c_buf is None or object_solids_c_stride < 8 or solid_count <= 0:
        solid_count = 0
    else:
        max_count = len(object_solids_c_buf) // int(object_solids_c_stride)
        if solid_count > max_count:
            solid_count = max_count
    native_solids_ok = solid_count > 0 or not object_solids
    if (not _native_disabled) and _array is not None and lgfx is not None and hasattr(lgfx, "update_player_native") and native_solids_ok:
        try:
            lgfx.update_player_native(
                tilemap_idx,
                tilemap_w,
                tilemap_h,
                tile_size,
                object_solids_c_buf,
                object_solids_c_stride,
                solid_count,
                player_x,
                player_y,
                player_w,
                player_h,
                move_x,
                vel_y,
                gravity,
                fall_speed_max,
                max_player_x,
                result,
            )
            return True
        except Exception as exc:
            _native_disabled = True
            _normal_log("PLAYER_UPDATE_NATIVE_FALLBACK %s" % exc)
    return _fallback_update(result, tilemap_idx, tilemap_w, tilemap_h, tile_size, object_solids, player_x, player_y, player_w, player_h, move_x, vel_y, gravity, fall_speed_max, max_player_x)