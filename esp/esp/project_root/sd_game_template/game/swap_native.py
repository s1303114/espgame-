try:
    import array as _array
except Exception:
    _array = None

SWAP_RESULT_LEN = 12
SWAP_TARGET_OBJECT = 1
SWAP_TARGET_ENEMY = 2
SWAP_TARGET_BULLET = 3
OBJECT_SOLID_STRIDE = 8
ENEMY_STATE_STRIDE = 8
BULLET_STATE_STRIDE = 16

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
        return _array.array("i", [0] * SWAP_RESULT_LEN)
    return [0] * SWAP_RESULT_LEN


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


def sync_python_after_native(result, objects_rows, enemy_rows, enemy_states, enemy_bullets, object_state_c_buf, object_state_c_stride, enemy_rows_c_buf, enemy_rows_c_stride, bullet_buf, bullet_stride):
    if result is None or int(result[0]) == 0:
        return
    kind = int(result[1])
    index = int(result[2])
    if kind == SWAP_TARGET_OBJECT:
        if objects_rows is not None and 0 <= index < len(objects_rows):
            row = objects_rows[index]
            # Native object state/render buffers already hold the authoritative value.
            # Python row is kept in step for checkpoint/death/high-level logic.
            changed = int(result[7])
            if changed >= 0 and object_state_c_buf is not None and object_state_c_stride > 0:
                row[0] = _buf_get_i16_le(object_state_c_buf, changed * int(object_state_c_stride) + 0)
                row[1] = _buf_get_i16_le(object_state_c_buf, changed * int(object_state_c_stride) + 2)
    elif kind == SWAP_TARGET_ENEMY:
        if enemy_rows is not None and 0 <= index < len(enemy_rows):
            row = enemy_rows[index]
            if enemy_rows_c_buf is not None and enemy_rows_c_stride > 0:
                row[0] = _buf_get_i16_le(enemy_rows_c_buf, index * int(enemy_rows_c_stride) + 0)
                row[1] = _buf_get_i16_le(enemy_rows_c_buf, index * int(enemy_rows_c_stride) + 2)
        if enemy_states is not None and 0 <= index < len(enemy_states):
            try:
                enemy_states[index]["vel_y"] = 0
            except Exception:
                pass
    elif kind == SWAP_TARGET_BULLET:
        if enemy_bullets is not None and 0 <= index < len(enemy_bullets):
            try:
                row = enemy_bullets[index]
                if bullet_buf is not None and bullet_stride > 0:
                    row[0] = _buf_get_i16_le(bullet_buf, index * int(bullet_stride) + 0)
                    row[1] = _buf_get_i16_le(bullet_buf, index * int(bullet_stride) + 2)
                if len(row) > 7:
                    row[7] = -1
            except Exception:
                pass


def perform_transaction(
    lgfx,
    result,
    target_kind,
    target_index,
    player_x,
    player_y,
    player_w,
    player_h,
    max_player_x,
    map_h_px,
    object_state_c_buf,
    object_state_c_stride,
    object_state_c_count,
    objects_c_buf,
    objects_c_stride,
    object_solids_c_buf,
    object_solids_c_stride,
    object_solids_capacity,
    enemy_rows_c_buf,
    enemy_rows_c_stride,
    enemy_rows_c_count,
    enemy_states,
    enemy_bullets,
    objects_rows=None,
    enemy_rows=None,
):
    global _native_disabled
    if result is None or _native_disabled:
        return False
    if target_kind not in (SWAP_TARGET_OBJECT, SWAP_TARGET_ENEMY, SWAP_TARGET_BULLET):
        return False
    if _array is None or lgfx is None or not hasattr(lgfx, "perform_swap_native"):
        return False
    if object_state_c_buf is None or objects_c_buf is None or object_solids_c_buf is None:
        return False
    if enemy_rows_c_buf is None or enemy_states is None or enemy_bullets is None:
        return False
    if not hasattr(enemy_states, "_buf") or not hasattr(enemy_bullets, "_buf"):
        return False
    bullet_count = len(enemy_bullets)
    try:
        ok = lgfx.perform_swap_native(
            int(target_kind),
            int(target_index),
            int(player_x),
            int(player_y),
            int(player_w),
            int(player_h),
            int(max_player_x),
            int(map_h_px),
            object_state_c_buf,
            int(object_state_c_stride),
            int(object_state_c_count),
            objects_c_buf,
            int(objects_c_stride),
            object_solids_c_buf,
            int(object_solids_c_stride),
            int(object_solids_capacity),
            enemy_rows_c_buf,
            int(enemy_rows_c_stride),
            int(enemy_rows_c_count),
            enemy_states._buf,
            ENEMY_STATE_STRIDE,
            enemy_bullets._buf,
            BULLET_STATE_STRIDE,
            int(bullet_count),
            result,
        )
    except Exception as exc:
        _native_disabled = True
        _normal_log("SWAP_NATIVE_FALLBACK %s" % exc)
        return False
    if not ok or int(result[0]) == 0:
        return False
    sync_python_after_native(result, objects_rows, enemy_rows, enemy_states, enemy_bullets, object_state_c_buf, int(object_state_c_stride), enemy_rows_c_buf, int(enemy_rows_c_stride), enemy_bullets._buf, BULLET_STATE_STRIDE)
    return True