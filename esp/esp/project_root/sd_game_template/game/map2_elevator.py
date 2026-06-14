import config

_raw_print = print


def _quiet_logs_enabled():
    try:
        return bool(getattr(config, "CAMERA_QUIET_LOGS", False))
    except Exception:
        return False


def print(*args):
    if not _quiet_logs_enabled():
        _raw_print(*args)
        return
    text = ""
    if args:
        try:
            text = str(args[0])
        except Exception:
            text = ""
    if "FAIL" in text or "ERROR" in text or "CRASH" in text:
        _raw_print(*args)

try:
    import asset_cache
except Exception:
    asset_cache = None

_BOW_STATE_IDLE = 0
_BOW_STATE_SHOOT = 1
_BOW_STATE_DEATH = 3
_BOW_DEATH_FRAME_COUNT = 5
_SWAP_TARGET_NONE = 0
_SWAP_TARGET_BOW = 2
_SWAP_TARGET_ARROW = 3
_MAP2_BOW_STRIDE = 24
_MAP2_ARROW_STRIDE = 16
_MAP2_SWAP_STRIDE = 28
_MAP2_RESULT_STRIDE = 16
_MAP2_COLLECT_STRIDE = 16
_MAP2_ENV_STRIDE = 28
_MAP2_STAR_STRIDE = 16
_MAP2_BOW_COUNT = 2
_MAP2_COLLECT_REQ_LEFT = 0x0100
_MAP2_COLLECT_REQ_RIGHT = 0x0200
_MAP2_COLLECT_SEQ_MASK = 0x00FF
_SWAP_TARGET_STAR = 4


def _resolve(path):
    text = str(path or "")
    if not text:
        return text
    if text.startswith("/"):
        return text
    return "/sd/" + text


def _load_blob(path, exp_bytes):
    try:
        with open(path, "rb") as fp:
            data = fp.read()
    except Exception:
        return None
    if data is None or len(data) != exp_bytes:
        return None
    return data


def _swap16(value):
    return ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)


def _buf_set_i16(buf, off, value):
    v = int(value)
    if v < -32768:
        v = -32768
    elif v > 32767:
        v = 32767
    if v < 0:
        v += 65536
    buf[off] = v & 0xFF
    buf[off + 1] = (v >> 8) & 0xFF


def _buf_get_i16(buf, off):
    v = int(buf[off]) | (int(buf[off + 1]) << 8)
    if v & 0x8000:
        v -= 65536
    return v


def _buf_set_i32(buf, off, value):
    v = int(value)
    if v < -2147483648:
        v = -2147483648
    elif v > 2147483647:
        v = 2147483647
    if v < 0:
        v += 4294967296
    buf[off] = v & 0xFF
    buf[off + 1] = (v >> 8) & 0xFF
    buf[off + 2] = (v >> 16) & 0xFF
    buf[off + 3] = (v >> 24) & 0xFF


def _buf_get_i32(buf, off):
    v = int(buf[off]) | (int(buf[off + 1]) << 8) | (int(buf[off + 2]) << 16) | (int(buf[off + 3]) << 24)
    if v & 0x80000000:
        v -= 4294967296
    return v


def load_runtime(screen_w, screen_h):
    if asset_cache is not None:
        runtime = asset_cache.get_map2_runtime(config, screen_w, screen_h)
        if runtime is not None:
            return runtime
    wall_w = int(getattr(config, "MAP2_WALL_W", 64))
    wall_h = int(getattr(config, "MAP2_WALL_H", screen_h))
    door_w = int(getattr(config, "MAP2_DOOR_W", 256))
    door_h = int(getattr(config, "MAP2_DOOR_H", 112))
    floor_w = int(getattr(config, "MAP2_FLOOR_W", 256))
    floor_h = int(getattr(config, "MAP2_FLOOR_H", 32))
    object_atlas_w = int(getattr(config, "MAP2_OBJECT_ATLAS_W", getattr(config, "OBJECTS_ATLAS_W", 0)))
    object_atlas_h = int(getattr(config, "MAP2_OBJECT_ATLAS_H", getattr(config, "OBJECTS_ATLAS_H", 0)))
    bow_sheet_w = int(getattr(config, "MAP2_FLOOR_BOW_SHEET_W", getattr(config, "ENEMY_SHEET_W", 0)))
    bow_sheet_h = int(getattr(config, "MAP2_FLOOR_BOW_SHEET_H", getattr(config, "ENEMY_SHEET_H", 0)))
    far = _load_blob(_resolve(getattr(config, "MAP2_FAR_RGB565_PATH", "")), screen_w * screen_h * 2)
    wall = _load_blob(_resolve(getattr(config, "MAP2_WALL_RGB565_PATH", "")), wall_w * wall_h * 2)
    door = _load_blob(_resolve(getattr(config, "MAP2_DOOR_RGB565_PATH", "")), door_w * door_h * 2)
    floor = _load_blob(_resolve(getattr(config, "MAP2_FLOOR_RGB565_PATH", "")), floor_w * floor_h * 2)
    object_atlas = _load_blob(
        _resolve(getattr(config, "MAP2_OBJECT_ATLAS_RGB565_PATH", getattr(config, "OBJECTS_ATLAS_RGB565_PATH", ""))),
        object_atlas_w * object_atlas_h * 2,
    )
    bow_sheet = _load_blob(
        _resolve(getattr(config, "MAP2_FLOOR_BOW_SHEET_RGB565_PATH", getattr(config, "ENEMY_SHEET_RGB565_PATH", ""))),
        bow_sheet_w * bow_sheet_h * 2,
    )
    if far is None or wall is None or door is None or floor is None or object_atlas is None or bow_sheet is None:
        return None
    return {
        "far": far,
        "wall": wall,
        "wall_w": wall_w,
        "wall_h": wall_h,
        "door": door,
        "door_w": door_w,
        "door_h": door_h,
        "floor": floor,
        "floor_w": floor_w,
        "floor_h": floor_h,
        "object_atlas": object_atlas,
        "object_atlas_w": object_atlas_w,
        "object_atlas_h": object_atlas_h,
        "floor_bow_sheet": bow_sheet,
        "floor_bow_sheet_w": bow_sheet_w,
        "floor_bow_sheet_h": bow_sheet_h,
        "wall_scroll_y": 0,
        "door_y": int(getattr(config, "MAP2_DOOR_START_Y", 128)),
        "door_enabled": True,
        "lever_on": False,
        "lever_running": False,
        "floor_left_y": int(getattr(config, "MAP2_FLOOR_Y", 208)),
        "floor_right_y": int(getattr(config, "MAP2_FLOOR_Y", 208)),
        "floor_left_bow": 0,
        "floor_right_bow": 0,
        "floor_left_bow_bound": 1,
        "floor_right_bow_bound": 1,
        "floor_left_bow_x": 0,
        "floor_left_bow_y": 0,
        "floor_right_bow_x": 0,
        "floor_right_bow_y": 0,
        "floor_left_bow_state": 0,
        "floor_right_bow_state": 0,
        "floor_left_bow_anim": 0,
        "floor_right_bow_anim": 0,
        "floor_left_bow_cooldown": int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15))),
        "floor_right_bow_cooldown": int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15))),
        "floor_left_bow_fired": 0,
        "floor_right_bow_fired": 0,
        "floor_left_bow_gap": int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1)),
        "floor_right_bow_gap": int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1)),
        "floor_bow_rng": int(getattr(config, "MAP2_FLOOR_BOW_RNG_SEED", 0x2468)),
        "floor_bow_arrows": [],
        "collect_active": 0,
        "collect_pending": 1,
        "collect_slot": -1,
        "collect_x": 0,
        "collect_y": 0,
        "collect_count": 0,
        "collect_total": int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5)),
        "collect_wall_speed": 1,
        "collect_seq": 0,
        "star_active": 0,
        "star_started": 0,
        "star_x": 0,
        "star_y": -int(getattr(config, "MAP2_STAR_H", 16)),
        "star_vy": int(getattr(config, "MAP2_STAR_SPEED", 3)),
        "star_timer": 0,
        "swap_hold_active": 0,
        "swap_hold_far": 0,
        "swap_hold_button": 0,
        "swap_b_down_prev": 0,
        "swap_y_down_prev": 0,
        "swap_preview_active": 0,
        "swap_preview_valid": 0,
        "swap_preview_kind": 0,
        "swap_preview_index": -1,
        "swap_preview_x": 0,
        "swap_preview_y": 0,
        "swap_preview_w": 0,
        "swap_preview_h": 0,
        "swap_preview_d2": -1,
        "player_platform_slot": 1,
        "player_airborne": False,
        "player_vel_y": 0,
    }


def enter(player_h):
    player_x = int(getattr(config, "MAP2_RESPAWN_X", getattr(config, "MAP2_PLAYER_START_X", 154)))
    default_y = int(getattr(config, "MAP2_PLAYER_START_Y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h)))
    player_y = int(getattr(config, "MAP2_RESPAWN_Y", default_y))
    return player_x, player_y, 0, 0


def _aabb_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def _reset_run_state(runtime):
    floor_y = int(getattr(config, "MAP2_FLOOR_Y", 208))
    runtime["wall_scroll_y"] = 0
    runtime["door_y"] = int(getattr(config, "MAP2_DOOR_START_Y", 128))
    runtime["door_enabled"] = True
    runtime["lever_on"] = False
    runtime["lever_running"] = False
    runtime["floor_left_y"] = floor_y
    runtime["floor_right_y"] = floor_y
    runtime["floor_left_bow"] = 0
    runtime["floor_right_bow"] = 0
    runtime["floor_left_bow_bound"] = 1
    runtime["floor_right_bow_bound"] = 1
    runtime["floor_left_bow_x"] = 0
    runtime["floor_left_bow_y"] = 0
    runtime["floor_right_bow_x"] = 0
    runtime["floor_right_bow_y"] = 0
    runtime["floor_left_bow_vel_y"] = 0
    runtime["floor_right_bow_vel_y"] = 0
    runtime["floor_left_bow_state"] = 0
    runtime["floor_right_bow_state"] = 0
    runtime["floor_left_bow_anim"] = 0
    runtime["floor_right_bow_anim"] = 0
    runtime["floor_left_bow_fired"] = 0
    runtime["floor_right_bow_fired"] = 0
    runtime["floor_left_bow_cooldown"] = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15)))
    runtime["floor_right_bow_cooldown"] = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15)))
    runtime["floor_left_bow_gap"] = int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1))
    runtime["floor_right_bow_gap"] = int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1))
    runtime["floor_bow_rng"] = int(getattr(config, "MAP2_FLOOR_BOW_RNG_SEED", 0x2468))
    runtime["floor_bow_arrows"] = []
    runtime["collect_active"] = 0
    runtime["collect_pending"] = 1
    runtime["collect_slot"] = -1
    runtime["collect_x"] = 0
    runtime["collect_y"] = 0
    runtime["collect_count"] = 0
    runtime["collect_total"] = int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5))
    runtime["collect_wall_speed"] = 1
    runtime["collect_seq"] = 0
    runtime["star_active"] = 0
    runtime["star_started"] = 0
    runtime["star_x"] = 0
    runtime["star_y"] = -int(getattr(config, "MAP2_STAR_H", 16))
    runtime["star_vy"] = int(getattr(config, "MAP2_STAR_SPEED", 3))
    runtime["star_timer"] = 0
    _clear_swap_hold(runtime)
    runtime["player_platform_slot"] = 1
    runtime["player_airborne"] = False
    runtime["player_vel_y"] = 0
    runtime["player_y"] = int(getattr(config, "MAP2_RESPAWN_Y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(getattr(config, "CAMERA_TEST_PLAYER_H", 32))))
    runtime["map2_respawn_reset_latch"] = 1


def _reset_platforms(runtime):
    _reset_run_state(runtime)


def _respawn_player(runtime, player_h, reason="MAP2_PLAYER_FALL_DEATH"):
    _reset_run_state(runtime)
    player_x = int(getattr(config, "MAP2_RESPAWN_X", getattr(config, "MAP2_PLAYER_START_X", 154)))
    player_y = int(getattr(config, "MAP2_RESPAWN_Y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h)))
    runtime["player_y"] = int(player_y)
    print(reason)
    return player_x, player_y


def _runtime_int(runtime, key, default):
    value = runtime.get(key, default)
    if value is None:
        return int(default)
    return int(value)


def _floor_bow_prefix(slot):
    return "floor_left_bow" if int(slot) == 0 else "floor_right_bow"


def _floor_bow_side_key(slot):
    return _floor_bow_prefix(slot)


def _clear_swap_preview(runtime):
    runtime["swap_preview_active"] = 0
    runtime["swap_preview_valid"] = 0
    runtime["swap_preview_kind"] = 0
    runtime["swap_preview_index"] = -1
    runtime["swap_preview_x"] = 0
    runtime["swap_preview_y"] = 0
    runtime["swap_preview_w"] = 0
    runtime["swap_preview_h"] = 0
    runtime["swap_preview_d2"] = -1


def _clear_swap_hold(runtime):
    runtime["swap_hold_active"] = 0
    runtime["swap_hold_far"] = 0
    runtime["swap_hold_button"] = 0
    _clear_swap_preview(runtime)


def _request_collect_spawn(runtime, slot):
    seq = int(runtime.get("collect_seq", 0)) & _MAP2_COLLECT_SEQ_MASK
    if int(slot) == 0:
        seq |= _MAP2_COLLECT_REQ_LEFT
    elif int(slot) == 2:
        seq |= _MAP2_COLLECT_REQ_RIGHT
    runtime["collect_seq"] = seq


def _init_native_buffers(runtime):
    if runtime.get("map2_bow_buf") is None or len(runtime.get("map2_bow_buf")) != _MAP2_BOW_STRIDE * _MAP2_BOW_COUNT:
        runtime["map2_bow_buf"] = bytearray(_MAP2_BOW_STRIDE * _MAP2_BOW_COUNT)
    max_arrows = int(getattr(config, "MAP2_FLOOR_BOW_MAX_ARROWS", 4))
    if max_arrows < 1:
        max_arrows = 1
    if runtime.get("map2_arrow_buf") is None or len(runtime.get("map2_arrow_buf")) != _MAP2_ARROW_STRIDE * max_arrows:
        runtime["map2_arrow_buf"] = bytearray(_MAP2_ARROW_STRIDE * max_arrows)
    if runtime.get("map2_swap_buf") is None or len(runtime.get("map2_swap_buf")) != _MAP2_SWAP_STRIDE:
        runtime["map2_swap_buf"] = bytearray(_MAP2_SWAP_STRIDE)
    if runtime.get("map2_result_buf") is None or len(runtime.get("map2_result_buf")) != _MAP2_RESULT_STRIDE:
        runtime["map2_result_buf"] = bytearray(_MAP2_RESULT_STRIDE)
    if runtime.get("map2_collect_buf") is None or len(runtime.get("map2_collect_buf")) != _MAP2_COLLECT_STRIDE:
        runtime["map2_collect_buf"] = bytearray(_MAP2_COLLECT_STRIDE)
    if runtime.get("map2_env_buf") is None or len(runtime.get("map2_env_buf")) != _MAP2_ENV_STRIDE:
        runtime["map2_env_buf"] = bytearray(_MAP2_ENV_STRIDE)
    if runtime.get("map2_star_buf") is None or len(runtime.get("map2_star_buf")) != _MAP2_STAR_STRIDE:
        runtime["map2_star_buf"] = bytearray(_MAP2_STAR_STRIDE)
    runtime["map2_arrow_count"] = max_arrows
    return True


def _sync_runtime_to_env_buffer(runtime):
    _init_native_buffers(runtime)
    env_buf = runtime["map2_env_buf"]
    _buf_set_i16(env_buf, 0, int(runtime.get("wall_scroll_y", 0) or 0))
    _buf_set_i16(env_buf, 2, int(runtime.get("door_y", int(getattr(config, "MAP2_DOOR_START_Y", 128))) or 0))
    env_buf[4] = 1 if bool(runtime.get("door_enabled", False)) else 0
    env_buf[5] = 1 if bool(runtime.get("lever_running", False)) else 0
    _buf_set_i16(env_buf, 6, int(runtime.get("floor_left_y", int(getattr(config, "MAP2_FLOOR_Y", 208))) or 0))
    _buf_set_i16(env_buf, 8, int(runtime.get("floor_right_y", int(getattr(config, "MAP2_FLOOR_Y", 208))) or 0))
    _buf_set_i16(env_buf, 10, int(runtime.get("floor_left_bow_gap", int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1))) or 0))
    _buf_set_i16(env_buf, 12, int(runtime.get("floor_right_bow_gap", int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1))) or 0))
    _buf_set_i32(env_buf, 14, int(runtime.get("floor_bow_rng", int(getattr(config, "MAP2_FLOOR_BOW_RNG_SEED", 0x2468))) or 0))
    env_buf[18] = 0
    env_buf[19] = 0
    env_buf[20] = 0
    _buf_set_i16(env_buf, 22, int(runtime.get("collect_wall_speed", int(getattr(config, "MAP2_WALL_SCROLL_SPEED", 1))) or 1))
    _buf_set_i16(env_buf, 24, int(getattr(config, "MAP2_DOOR_SCROLL_SPEED", 1)))
    _buf_set_i16(env_buf, 26, int(getattr(config, "MAP2_FLOOR_PLATFORM_SPEED", 5)))


def _sync_env_buffer_to_runtime(runtime):
    env_buf = runtime.get("map2_env_buf")
    if not env_buf:
        return False
    runtime["wall_scroll_y"] = _buf_get_i16(env_buf, 0)
    runtime["door_y"] = _buf_get_i16(env_buf, 2)
    runtime["door_enabled"] = bool(env_buf[4])
    runtime["lever_running"] = bool(env_buf[5])
    runtime["lever_on"] = bool(env_buf[5])
    runtime["floor_left_y"] = _buf_get_i16(env_buf, 6)
    runtime["floor_right_y"] = _buf_get_i16(env_buf, 8)
    runtime["floor_left_bow_gap"] = _buf_get_i16(env_buf, 10)
    runtime["floor_right_bow_gap"] = _buf_get_i16(env_buf, 12)
    runtime["floor_bow_rng"] = _buf_get_i32(env_buf, 14)
    return bool(env_buf[20])


def _sync_env_side_buffers_to_runtime(runtime):
    bow_buf = runtime.get("map2_bow_buf")
    if bow_buf:
        for idx, slot in ((0, 0), (1, 2)):
            prefix = _floor_bow_prefix(slot)
            base = idx * _MAP2_BOW_STRIDE
            runtime[prefix + "_x"] = _buf_get_i16(bow_buf, base + 0)
            runtime[prefix + "_y"] = _buf_get_i16(bow_buf, base + 2)
            runtime[prefix] = int(bow_buf[base + 8])
            runtime[prefix + "_bound"] = int(bow_buf[base + 9])
            runtime[prefix + "_state"] = int(bow_buf[base + 12])
            runtime[prefix + "_fired"] = int(bow_buf[base + 13])
            runtime[prefix + "_anim"] = _buf_get_i16(bow_buf, base + 14)
            runtime[prefix + "_cooldown"] = _buf_get_i16(bow_buf, base + 16)
            runtime[prefix + "_vel_y"] = _buf_get_i16(bow_buf, base + 18)
    collect_buf = runtime.get("map2_collect_buf")
    if collect_buf:
        runtime["collect_active"] = int(collect_buf[0])
        runtime["collect_pending"] = int(collect_buf[1])
        runtime["collect_slot"] = _buf_get_i16(collect_buf, 2)
        runtime["collect_x"] = _buf_get_i16(collect_buf, 4)
        runtime["collect_y"] = _buf_get_i16(collect_buf, 6)
        runtime["collect_count"] = _buf_get_i16(collect_buf, 8)
        runtime["collect_total"] = _buf_get_i16(collect_buf, 10)
        runtime["collect_wall_speed"] = _buf_get_i16(collect_buf, 12)
        runtime["collect_seq"] = _buf_get_i16(collect_buf, 14)


def _sync_runtime_to_env_side_buffers(runtime):
    _init_native_buffers(runtime)
    bow_buf = runtime["map2_bow_buf"]
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    for idx, slot in ((0, 0), (1, 2)):
        prefix = _floor_bow_prefix(slot)
        base = idx * _MAP2_BOW_STRIDE
        _buf_set_i16(bow_buf, base + 0, _floor_bow_x(runtime, slot))
        _buf_set_i16(bow_buf, base + 2, _floor_bow_y(runtime, slot))
        _buf_set_i16(bow_buf, base + 4, bow_w)
        _buf_set_i16(bow_buf, base + 6, bow_h)
        bow_buf[base + 8] = 1 if int(runtime.get(prefix, 0)) else 0
        bow_buf[base + 9] = 1 if int(runtime.get(prefix + "_bound", 1)) else 0
        _buf_set_i16(bow_buf, base + 10, slot)
        bow_buf[base + 12] = int(runtime.get(prefix + "_state", 0)) & 0xFF
        bow_buf[base + 13] = int(runtime.get(prefix + "_fired", 0)) & 0xFF
        _buf_set_i16(bow_buf, base + 14, int(runtime.get(prefix + "_anim", 0) or 0))
        _buf_set_i16(bow_buf, base + 16, int(runtime.get(prefix + "_cooldown", 0) or 0))
        _buf_set_i16(bow_buf, base + 18, int(runtime.get(prefix + "_vel_y", 0) or 0))
    collect_buf = runtime["map2_collect_buf"]
    collect_buf[0] = int(runtime.get("collect_active", 0)) & 0xFF
    collect_buf[1] = int(runtime.get("collect_pending", 1)) & 0xFF
    _buf_set_i16(collect_buf, 2, int(runtime.get("collect_slot", -1)))
    _buf_set_i16(collect_buf, 4, int(runtime.get("collect_x", 0)))
    _buf_set_i16(collect_buf, 6, int(runtime.get("collect_y", 0)))
    _buf_set_i16(collect_buf, 8, int(runtime.get("collect_count", 0)))
    _buf_set_i16(collect_buf, 10, int(runtime.get("collect_total", int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5)))))
    _buf_set_i16(collect_buf, 12, int(runtime.get("collect_wall_speed", 1)))
    _buf_set_i16(collect_buf, 14, int(runtime.get("collect_seq", 0)))
    _sync_runtime_to_star_buffer(runtime)
    _sync_runtime_to_star_buffer(runtime)


def _sync_runtime_to_star_buffer(runtime):
    _init_native_buffers(runtime)
    star_buf = runtime["map2_star_buf"]
    star_w = int(getattr(config, "MAP2_STAR_W", 16))
    star_h = int(getattr(config, "MAP2_STAR_H", 16))
    star_speed = int(getattr(config, "MAP2_STAR_SPEED", 3))
    _buf_set_i16(star_buf, 0, int(runtime.get("star_x", 0) or 0))
    _buf_set_i16(star_buf, 2, int(runtime.get("star_y", -star_h) or 0))
    _buf_set_i16(star_buf, 4, int(runtime.get("star_vy", star_speed) or star_speed))
    _buf_set_i16(star_buf, 6, star_w)
    _buf_set_i16(star_buf, 8, star_h)
    star_buf[10] = int(runtime.get("star_active", 0)) & 0xFF
    star_buf[11] = int(runtime.get("star_started", 0)) & 0xFF
    _buf_set_i16(star_buf, 12, int(runtime.get("star_timer", 0) or 0))


def _sync_star_buffer_to_runtime(runtime):
    star_buf = runtime.get("map2_star_buf")
    if not star_buf:
        return
    runtime["star_x"] = _buf_get_i16(star_buf, 0)
    runtime["star_y"] = _buf_get_i16(star_buf, 2)
    runtime["star_vy"] = _buf_get_i16(star_buf, 4)
    runtime["star_active"] = int(star_buf[10])
    runtime["star_started"] = int(star_buf[11])
    runtime["star_timer"] = _buf_get_i16(star_buf, 12)


def _sync_runtime_to_native_buffers(runtime):
    _init_native_buffers(runtime)
    bow_buf = runtime["map2_bow_buf"]
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    for idx, slot in ((0, 0), (1, 2)):
        prefix = _floor_bow_prefix(slot)
        base = idx * _MAP2_BOW_STRIDE
        _buf_set_i16(bow_buf, base + 0, _floor_bow_x(runtime, slot))
        _buf_set_i16(bow_buf, base + 2, _floor_bow_y(runtime, slot))
        _buf_set_i16(bow_buf, base + 4, bow_w)
        _buf_set_i16(bow_buf, base + 6, bow_h)
        bow_buf[base + 8] = 1 if int(runtime.get(prefix, 0)) else 0
        bow_buf[base + 9] = 1 if int(runtime.get(prefix + "_bound", 1)) else 0
        _buf_set_i16(bow_buf, base + 10, slot)
        bow_buf[base + 12] = int(runtime.get(prefix + "_state", 0)) & 0xFF
        bow_buf[base + 13] = int(runtime.get(prefix + "_fired", 0)) & 0xFF
        _buf_set_i16(bow_buf, base + 14, int(runtime.get(prefix + "_anim", 0) or 0))
        _buf_set_i16(bow_buf, base + 16, int(runtime.get(prefix + "_cooldown", 0) or 0))
        _buf_set_i16(bow_buf, base + 18, int(runtime.get(prefix + "_vel_y", 0) or 0))
    arrow_buf = runtime["map2_arrow_buf"]
    max_arrows = int(runtime.get("map2_arrow_count", int(getattr(config, "MAP2_FLOOR_BOW_MAX_ARROWS", 4))))
    arrows = runtime.get("floor_bow_arrows") or []
    i = 0
    while i < max_arrows:
        base = i * _MAP2_ARROW_STRIDE
        if i < len(arrows):
            row = arrows[i]
            _buf_set_i16(arrow_buf, base + 0, int(row[0]))
            _buf_set_i16(arrow_buf, base + 2, int(row[1]))
            _buf_set_i16(arrow_buf, base + 4, int(row[2]))
            _buf_set_i16(arrow_buf, base + 6, 0)
            _buf_set_i16(arrow_buf, base + 8, int(row[3]))
            _buf_set_i16(arrow_buf, base + 10, int(row[4]))
            _buf_set_i16(arrow_buf, base + 12, int(row[5]))
            _buf_set_i16(arrow_buf, base + 14, int(row[6]) if len(row) > 6 else -1)
        else:
            j = 0
            while j < _MAP2_ARROW_STRIDE:
                arrow_buf[base + j] = 0
                j += 1
        i += 1
    swap_buf = runtime["map2_swap_buf"]
    swap_buf[0] = int(runtime.get("swap_hold_active", 0)) & 0xFF
    swap_buf[1] = int(runtime.get("swap_preview_valid", 0)) & 0xFF
    swap_buf[2] = int(runtime.get("swap_hold_far", 0)) & 0xFF
    swap_buf[3] = int(runtime.get("swap_preview_kind", 0)) & 0xFF
    _buf_set_i16(swap_buf, 4, int(runtime.get("swap_preview_index", -1)))
    _buf_set_i16(swap_buf, 6, int(runtime.get("swap_preview_x", 0)))
    _buf_set_i16(swap_buf, 8, int(runtime.get("swap_preview_y", 0)))
    _buf_set_i16(swap_buf, 10, int(runtime.get("swap_preview_w", 0)))
    _buf_set_i16(swap_buf, 12, int(runtime.get("swap_preview_h", 0)))
    _buf_set_i32(swap_buf, 14, int(runtime.get("swap_preview_d2", -1)))
    _buf_set_i16(swap_buf, 18, int(runtime.get("swap_hold_button", 0)))
    swap_buf[20] = int(runtime.get("swap_b_down_prev", 0)) & 0xFF
    swap_buf[21] = int(runtime.get("swap_y_down_prev", 0)) & 0xFF
    collect_buf = runtime["map2_collect_buf"]
    collect_buf[0] = int(runtime.get("collect_active", 0)) & 0xFF
    collect_buf[1] = int(runtime.get("collect_pending", 1)) & 0xFF
    _buf_set_i16(collect_buf, 2, int(runtime.get("collect_slot", -1)))
    _buf_set_i16(collect_buf, 4, int(runtime.get("collect_x", 0)))
    _buf_set_i16(collect_buf, 6, int(runtime.get("collect_y", 0)))
    _buf_set_i16(collect_buf, 8, int(runtime.get("collect_count", 0)))
    _buf_set_i16(collect_buf, 10, int(runtime.get("collect_total", int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5)))))
    _buf_set_i16(collect_buf, 12, int(runtime.get("collect_wall_speed", 1)))
    _buf_set_i16(collect_buf, 14, int(runtime.get("collect_seq", 0)))


def _sync_native_buffers_to_runtime(runtime):
    bow_buf = runtime.get("map2_bow_buf")
    if bow_buf:
        for idx, slot in ((0, 0), (1, 2)):
            prefix = _floor_bow_prefix(slot)
            base = idx * _MAP2_BOW_STRIDE
            runtime[prefix + "_x"] = _buf_get_i16(bow_buf, base + 0)
            runtime[prefix + "_y"] = _buf_get_i16(bow_buf, base + 2)
            runtime[prefix] = int(bow_buf[base + 8])
            runtime[prefix + "_bound"] = int(bow_buf[base + 9])
            runtime[prefix + "_state"] = int(bow_buf[base + 12])
            runtime[prefix + "_fired"] = int(bow_buf[base + 13])
            runtime[prefix + "_anim"] = _buf_get_i16(bow_buf, base + 14)
            runtime[prefix + "_cooldown"] = _buf_get_i16(bow_buf, base + 16)
            runtime[prefix + "_vel_y"] = _buf_get_i16(bow_buf, base + 18)
    arrow_buf = runtime.get("map2_arrow_buf")
    if arrow_buf:
        arrows = runtime.get("floor_bow_arrows")
        if arrows is None:
            arrows = []
            runtime["floor_bow_arrows"] = arrows
        max_arrows = int(runtime.get("map2_arrow_count", len(arrow_buf) // _MAP2_ARROW_STRIDE))
        while len(arrows) < max_arrows:
            arrows.append([0, 0, 0, int(getattr(config, "MAP2_FLOOR_BOW_ARROW_W", 16)), int(getattr(config, "MAP2_FLOOR_BOW_ARROW_H", 16)), 0, -1])
        i = 0
        while i < max_arrows:
            base = i * _MAP2_ARROW_STRIDE
            arrows[i][0] = _buf_get_i16(arrow_buf, base + 0)
            arrows[i][1] = _buf_get_i16(arrow_buf, base + 2)
            arrows[i][2] = _buf_get_i16(arrow_buf, base + 4)
            arrows[i][3] = _buf_get_i16(arrow_buf, base + 8)
            arrows[i][4] = _buf_get_i16(arrow_buf, base + 10)
            arrows[i][5] = _buf_get_i16(arrow_buf, base + 12)
            if len(arrows[i]) > 6:
                arrows[i][6] = _buf_get_i16(arrow_buf, base + 14)
            else:
                arrows[i].append(_buf_get_i16(arrow_buf, base + 14))
            i += 1
    swap_buf = runtime.get("map2_swap_buf")
    if swap_buf:
        runtime["swap_hold_active"] = int(swap_buf[0])
        runtime["swap_preview_valid"] = int(swap_buf[1])
        runtime["swap_hold_far"] = int(swap_buf[2])
        runtime["swap_preview_kind"] = int(swap_buf[3])
        runtime["swap_preview_index"] = _buf_get_i16(swap_buf, 4)
        runtime["swap_preview_x"] = _buf_get_i16(swap_buf, 6)
        runtime["swap_preview_y"] = _buf_get_i16(swap_buf, 8)
        runtime["swap_preview_w"] = _buf_get_i16(swap_buf, 10)
        runtime["swap_preview_h"] = _buf_get_i16(swap_buf, 12)
        runtime["swap_preview_d2"] = _buf_get_i32(swap_buf, 14)
        runtime["swap_hold_button"] = _buf_get_i16(swap_buf, 18)
        runtime["swap_b_down_prev"] = int(swap_buf[20])
        runtime["swap_y_down_prev"] = int(swap_buf[21])
        runtime["swap_preview_active"] = 1 if int(swap_buf[0]) else 0
    collect_buf = runtime.get("map2_collect_buf")
    if collect_buf:
        runtime["collect_active"] = int(collect_buf[0])
        runtime["collect_pending"] = int(collect_buf[1])
        runtime["collect_slot"] = _buf_get_i16(collect_buf, 2)
        runtime["collect_x"] = _buf_get_i16(collect_buf, 4)
        runtime["collect_y"] = _buf_get_i16(collect_buf, 6)
        runtime["collect_count"] = _buf_get_i16(collect_buf, 8)
        runtime["collect_total"] = _buf_get_i16(collect_buf, 10)
        runtime["collect_wall_speed"] = _buf_get_i16(collect_buf, 12)
        runtime["collect_seq"] = _buf_get_i16(collect_buf, 14)
    _sync_star_buffer_to_runtime(runtime)


def _ensure_runtime_state(runtime):
    if runtime is None:
        return None
    defaults = (
        ("floor_left_bow_bound", 1), ("floor_right_bow_bound", 1),
        ("floor_left_bow_x", 0), ("floor_left_bow_y", 0),
        ("floor_right_bow_x", 0), ("floor_right_bow_y", 0),
        ("floor_left_bow_vel_y", 0), ("floor_right_bow_vel_y", 0),
        ("swap_hold_active", 0), ("swap_hold_far", 0), ("swap_hold_button", 0),
        ("swap_b_down_prev", 0), ("swap_y_down_prev", 0),
        ("swap_preview_active", 0), ("swap_preview_valid", 0),
        ("swap_preview_kind", 0), ("swap_preview_index", -1),
        ("swap_preview_x", 0), ("swap_preview_y", 0),
        ("swap_preview_w", 0), ("swap_preview_h", 0),
        ("swap_preview_d2", -1),
        ("collect_active", 0), ("collect_pending", 1),
        ("collect_slot", -1), ("collect_x", 0), ("collect_y", 0),
        ("collect_count", 0), ("collect_total", int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5))),
        ("collect_wall_speed", 1), ("collect_seq", 0),
        ("star_active", 0), ("star_started", 0), ("star_x", 0),
        ("star_y", -int(getattr(config, "MAP2_STAR_H", 16))),
        ("star_vy", int(getattr(config, "MAP2_STAR_SPEED", 3))), ("star_timer", 0),
    )
    for key, value in defaults:
        if key not in runtime:
            runtime[key] = value
    arrows = runtime.get("floor_bow_arrows")
    if arrows:
        for row in arrows:
            if len(row) < 7:
                row.append(-1)
    _init_native_buffers(runtime)
    return runtime


def _set_swap_preview(runtime, active, valid, kind, index, x, y, w, h, d2):
    runtime["swap_preview_active"] = 1 if active else 0
    runtime["swap_preview_valid"] = 1 if valid else 0
    runtime["swap_preview_kind"] = int(kind)
    runtime["swap_preview_index"] = int(index)
    runtime["swap_preview_x"] = int(x)
    runtime["swap_preview_y"] = int(y)
    runtime["swap_preview_w"] = int(w)
    runtime["swap_preview_h"] = int(h)
    runtime["swap_preview_d2"] = int(d2)


def _visible_target_distance2(wx, wy, ow, oh, player_x, player_y, player_w, player_h, view_w, view_h):
    sx0 = int(wx)
    sy0 = int(wy)
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
    if visible_w < 10 or visible_h < 10 or (visible_w * visible_h) < 128:
        return -1
    px = int(player_x) + (int(player_w) // 2)
    py = int(player_y) + (int(player_h) // 2)
    ox = (cx0 + cx1) // 2
    oy = (cy0 + cy1) // 2
    dx = ox - px
    dy = oy - py
    return dx * dx + dy * dy


def _pick_swappable_bow(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h):
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    best_slot = -1
    best_d2 = -1
    best_x = 0
    best_y = 0
    for slot in (0, 2):
        if not _floor_bow_alive(runtime, slot):
            continue
        x = _floor_bow_x(runtime, slot)
        y = _floor_bow_y(runtime, slot)
        d2 = _visible_target_distance2(x, y, bow_w, bow_h, player_x, player_y, player_w, player_h, screen_w, screen_h)
        if d2 < 0:
            continue
        if best_slot < 0 or (pick_far and d2 > best_d2) or ((not pick_far) and d2 < best_d2):
            best_slot = int(slot)
            best_d2 = int(d2)
            best_x = int(x)
            best_y = int(y)
    return best_slot, best_x, best_y, bow_w, bow_h, best_d2


def _pick_swappable_arrow(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h):
    arrows = runtime.get("floor_bow_arrows") or []
    best_i = -1
    best_d2 = -1
    best_row = None
    i = 0
    while i < len(arrows):
        row = arrows[i]
        if int(row[5]):
            d2 = _visible_target_distance2(row[0], row[1], row[3], row[4], player_x, player_y, player_w, player_h, screen_w, screen_h)
            if d2 >= 0 and (best_i < 0 or (pick_far and d2 > best_d2) or ((not pick_far) and d2 < best_d2)):
                best_i = i
                best_d2 = int(d2)
                best_row = row
        i += 1
    if best_row is None:
        return -1, 0, 0, 0, 0, -1
    return best_i, int(best_row[0]), int(best_row[1]), int(best_row[3]), int(best_row[4]), best_d2


def _pick_swappable_star(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h):
    if not int(runtime.get("star_active", 0)):
        return -1, 0, 0, 0, 0, -1
    star_w = int(getattr(config, "MAP2_STAR_W", 16))
    star_h = int(getattr(config, "MAP2_STAR_H", 16))
    star_x = _runtime_int(runtime, "star_x", 0)
    star_y = _runtime_int(runtime, "star_y", -star_h)
    d2 = _visible_target_distance2(star_x, star_y, star_w, star_h, player_x, player_y, player_w, player_h, screen_w, screen_h)
    if d2 < 0:
        return -1, 0, 0, 0, 0, -1
    return 0, star_x, star_y, star_w, star_h, d2


def _pick_swap_target(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h):
    bow_i, bow_x, bow_y, bow_w, bow_h, bow_d2 = _pick_swappable_bow(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h)
    arrow_i, arrow_x, arrow_y, arrow_w, arrow_h, arrow_d2 = _pick_swappable_arrow(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h)
    star_i, star_x, star_y, star_w, star_h, star_d2 = _pick_swappable_star(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h)
    if bow_i < 0 and arrow_i < 0 and star_i < 0:
        return _SWAP_TARGET_NONE, -1, 0, 0, 0, 0, -1
    best_kind = _SWAP_TARGET_NONE
    best_i = -1
    best_x = 0
    best_y = 0
    best_w = 0
    best_h = 0
    best_d2 = -1
    if bow_i >= 0:
        best_kind, best_i, best_x, best_y, best_w, best_h, best_d2 = _SWAP_TARGET_BOW, bow_i, bow_x, bow_y, bow_w, bow_h, bow_d2
    if arrow_i >= 0 and (best_kind == _SWAP_TARGET_NONE or (pick_far and arrow_d2 > best_d2) or ((not pick_far) and arrow_d2 < best_d2)):
        best_kind, best_i, best_x, best_y, best_w, best_h, best_d2 = _SWAP_TARGET_ARROW, arrow_i, arrow_x, arrow_y, arrow_w, arrow_h, arrow_d2
    if star_i >= 0 and (best_kind == _SWAP_TARGET_NONE or (pick_far and star_d2 > best_d2) or ((not pick_far) and star_d2 < best_d2)):
        best_kind, best_i, best_x, best_y, best_w, best_h, best_d2 = _SWAP_TARGET_STAR, star_i, star_x, star_y, star_w, star_h, star_d2
    return best_kind, best_i, best_x, best_y, best_w, best_h, best_d2


def _update_swap_preview(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h):
    kind, index, x, y, w, h, d2 = _pick_swap_target(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h)
    if kind == _SWAP_TARGET_NONE:
        _set_swap_preview(runtime, True, False, _SWAP_TARGET_NONE, -1, 0, 0, 0, 0, -1)
    else:
        _set_swap_preview(runtime, True, True, kind, index, x, y, w, h, d2)


def _player_ground_state_after_swap(runtime, player_x, player_y, player_w, player_h, screen_h):
    runtime["player_y"] = int(player_y)
    slot = _platform_slot_for_player(player_x, player_w)
    if slot is not None:
        top = _platform_top_for_slot(runtime, slot, screen_h)
        if top is not None and int(player_y) + int(player_h) == int(top):
            runtime["player_airborne"] = False
            runtime["player_vel_y"] = 0
            runtime["player_platform_slot"] = int(slot)
            return
    runtime["player_airborne"] = True
    runtime["player_vel_y"] = 0


def _perform_swap(runtime, kind, index, player_x, player_y, player_w, player_h, screen_w, screen_h, pick_far):
    max_x = int(getattr(config, "MAP2_PLAYER_MAX_X", int(screen_w) - int(player_w)))
    min_x = int(getattr(config, "MAP2_PLAYER_MIN_X", 0))
    if max_x < min_x:
        max_x = min_x
    max_y = int(screen_h) - int(player_h)
    if max_y < 0:
        max_y = 0
    old_px = int(player_x)
    old_py = int(player_y)
    if int(kind) == _SWAP_TARGET_BOW:
        slot = int(index)
        if not _floor_bow_alive(runtime, slot):
            return player_x, player_y, False
        bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
        bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
        old_bx = _floor_bow_x(runtime, slot)
        old_by = _floor_bow_y(runtime, slot)
        player_x = old_bx + ((bow_w - int(player_w)) // 2)
        player_y = old_by + (bow_h - int(player_h))
        player_x = max(min_x, min(max_x, int(player_x)))
        player_y = max(0, min(max_y, int(player_y)))
        prefix = _floor_bow_prefix(slot)
        runtime[prefix + "_bound"] = 0
        runtime[prefix + "_x"] = old_px + ((int(player_w) - bow_w) // 2)
        runtime[prefix + "_y"] = old_py + (int(player_h) - bow_h)
        arrows = runtime.get("floor_bow_arrows") or []
        for row in arrows:
            if len(row) > 6 and int(row[6]) == slot:
                row[6] = -1
        _player_ground_state_after_swap(runtime, player_x, player_y, player_w, player_h, screen_h)
        print("MAP2_SWAP_%s_OK_BOW slot=%d px=%d py=%d" % ("FAR" if pick_far else "NEAR", slot, int(player_x), int(player_y)))
        return player_x, player_y, True
    if int(kind) == _SWAP_TARGET_ARROW:
        arrows = runtime.get("floor_bow_arrows") or []
        if int(index) < 0 or int(index) >= len(arrows):
            return player_x, player_y, False
        row = arrows[int(index)]
        if not int(row[5]):
            return player_x, player_y, False
        arrow_w = int(row[3])
        arrow_h = int(row[4])
        old_ax = int(row[0])
        old_ay = int(row[1])
        player_x = old_ax + ((arrow_w - int(player_w)) // 2)
        player_y = old_ay + (arrow_h - int(player_h))
        player_x = max(min_x, min(max_x, int(player_x)))
        player_y = max(0, min(max_y, int(player_y)))
        row[0] = old_px + ((int(player_w) - arrow_w) // 2)
        row[1] = old_py + (int(player_h) - arrow_h)
        if len(row) > 6:
            row[6] = -1
        else:
            row.append(-1)
        _player_ground_state_after_swap(runtime, player_x, player_y, player_w, player_h, screen_h)
        print("MAP2_SWAP_%s_OK_ARROW idx=%d px=%d py=%d" % ("FAR" if pick_far else "NEAR", int(index), int(player_x), int(player_y)))
        return player_x, player_y, True
    if int(kind) == _SWAP_TARGET_STAR:
        if not int(runtime.get("star_active", 0)):
            return player_x, player_y, False
        star_w = int(getattr(config, "MAP2_STAR_W", 16))
        star_h = int(getattr(config, "MAP2_STAR_H", 16))
        old_sx = _runtime_int(runtime, "star_x", 0)
        old_sy = _runtime_int(runtime, "star_y", -star_h)
        player_x = old_sx + ((star_w - int(player_w)) // 2)
        player_y = old_sy + (star_h - int(player_h))
        player_x = max(min_x, min(max_x, int(player_x)))
        player_y = max(0, min(max_y, int(player_y)))
        runtime["star_x"] = old_px + ((int(player_w) - star_w) // 2)
        runtime["star_y"] = old_py + (int(player_h) - star_h)
        runtime["star_vy"] = int(getattr(config, "MAP2_STAR_SPEED", 3))
        _player_ground_state_after_swap(runtime, player_x, player_y, player_w, player_h, screen_h)
        print("MAP2_SWAP_%s_OK_STAR px=%d py=%d" % ("FAR" if pick_far else "NEAR", int(player_x), int(player_y)))
        return player_x, player_y, True
    return player_x, player_y, False


def _swap_hold_step(runtime, player_x, player_y, player_w, player_h, btn_b_down, btn_y_down, screen_w, screen_h):
    b_now = 1 if btn_b_down else 0
    y_now = 1 if btn_y_down else 0
    b_prev = int(runtime.get("swap_b_down_prev", 0))
    y_prev = int(runtime.get("swap_y_down_prev", 0))
    b_edge = b_now and not b_prev
    y_edge = y_now and not y_prev
    b_release = (not b_now) and b_prev
    y_release = (not y_now) and y_prev
    runtime["swap_b_down_prev"] = b_now
    runtime["swap_y_down_prev"] = y_now
    triggered = False
    pick_far = False
    locked_kind = _SWAP_TARGET_NONE
    locked_index = -1
    if not int(runtime.get("swap_hold_active", 0)):
        if b_edge:
            runtime["swap_hold_active"] = 1
            runtime["swap_hold_far"] = 1
            runtime["swap_hold_button"] = 1
            _update_swap_preview(runtime, player_x, player_y, player_w, player_h, True, screen_w, screen_h)
        elif y_edge:
            runtime["swap_hold_active"] = 1
            runtime["swap_hold_far"] = 0
            runtime["swap_hold_button"] = 2
            _update_swap_preview(runtime, player_x, player_y, player_w, player_h, False, screen_w, screen_h)
    if int(runtime.get("swap_hold_active", 0)):
        pick_far = bool(runtime.get("swap_hold_far", 0))
        button = int(runtime.get("swap_hold_button", 0))
        if (button == 1 and b_now) or (button == 2 and y_now):
            _update_swap_preview(runtime, player_x, player_y, player_w, player_h, pick_far, screen_w, screen_h)
        elif (button == 1 and b_release) or (button == 2 and y_release):
            if int(runtime.get("swap_preview_valid", 0)):
                triggered = True
                locked_kind = int(runtime.get("swap_preview_kind", _SWAP_TARGET_NONE))
                locked_index = int(runtime.get("swap_preview_index", -1))
            _clear_swap_hold(runtime)
        elif not b_now and not y_now:
            _clear_swap_hold(runtime)
    elif not b_now and not y_now:
        _clear_swap_preview(runtime)
    return triggered, pick_far, locked_kind, locked_index


def _next_floor_bow_random(runtime):
    seed = (_runtime_int(runtime, "floor_bow_rng", int(getattr(config, "MAP2_FLOOR_BOW_RNG_SEED", 0x2468))) * 1103515245 + 12345) & 0x7FFFFFFF
    runtime["floor_bow_rng"] = seed
    return (seed >> 16) & 0x7FFF


def _roll_floor_bow(runtime, side_key, gap_key):
    slot = 0 if side_key == "floor_left_bow" else 2
    if not bool(getattr(config, "MAP2_FLOOR_BOW_ENABLED", True)):
        runtime[side_key] = 0
        return 0
    if int(runtime.get(side_key, 0)):
        return 1
    min_gap = int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1))
    if min_gap < 0:
        min_gap = 0
    gap = _runtime_int(runtime, gap_key, min_gap)
    if gap < min_gap:
        runtime[gap_key] = gap + 1
        runtime[side_key] = 0
        return 0
    chance = int(getattr(config, "MAP2_FLOOR_BOW_CHANCE", 50))
    if chance < 0:
        chance = 0
    if chance > 100:
        chance = 100
    spawn = 1 if (_next_floor_bow_random(runtime) % 100) < chance else 0
    runtime[gap_key] = 0 if spawn else gap + 1
    runtime[side_key] = spawn
    prefix = "floor_left_bow" if side_key == "floor_left_bow" else "floor_right_bow"
    runtime[prefix + "_bound"] = 1
    runtime[prefix + "_x"] = _floor_bow_bound_x(slot)
    runtime[prefix + "_y"] = _floor_bow_bound_y(runtime, slot)
    runtime[prefix + "_state"] = _BOW_STATE_IDLE
    runtime[prefix + "_anim"] = 0
    runtime[prefix + "_fired"] = 0
    runtime[prefix + "_vel_y"] = 0
    runtime[prefix + "_cooldown"] = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15)))
    print("MAP2_FLOOR_BOW_%s" % ("ON" if spawn else "OFF"))
    return spawn


def _floor_bow_bound_x(slot):
    floor_x = int(getattr(config, "MAP2_FLOOR_X", 32))
    left_w = int(getattr(config, "MAP2_FLOOR_LEFT_W", 96))
    middle_w = int(getattr(config, "MAP2_FLOOR_MIDDLE_W", 64))
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    if int(slot) == 0:
        offset = int(getattr(config, "MAP2_FLOOR_BOW_LEFT_OFFSET_X", 32))
        return floor_x + offset - (bow_w // 2)
    offset = int(getattr(config, "MAP2_FLOOR_BOW_RIGHT_OFFSET_X", 32))
    return floor_x + left_w + middle_w + offset - (bow_w // 2)


def _floor_bow_bound_y(runtime, slot):
    floor_y = int(getattr(config, "MAP2_FLOOR_Y", 208))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    if int(slot) == 0:
        return _runtime_int(runtime, "floor_left_y", floor_y) - bow_h
    return _runtime_int(runtime, "floor_right_y", floor_y) - bow_h


def _floor_bow_x(runtime, slot):
    prefix = _floor_bow_prefix(slot)
    if int(runtime.get(prefix + "_bound", 1)):
        x = _floor_bow_bound_x(slot)
        runtime[prefix + "_x"] = x
        return x
    return _runtime_int(runtime, prefix + "_x", _floor_bow_bound_x(slot))


def _floor_bow_y(runtime, slot):
    prefix = _floor_bow_prefix(slot)
    if int(runtime.get(prefix + "_bound", 1)):
        y = _floor_bow_bound_y(runtime, slot)
        runtime[prefix + "_y"] = y
        return y
    return _runtime_int(runtime, prefix + "_y", _floor_bow_bound_y(runtime, slot))


def _floor_bow_alive(runtime, slot):
    prefix = _floor_bow_prefix(slot)
    return int(runtime.get(prefix, 0)) and _runtime_int(runtime, prefix + "_state", _BOW_STATE_IDLE) != _BOW_STATE_DEATH


def _floor_bow_visible(runtime, slot):
    return int(runtime.get(_floor_bow_prefix(slot), 0))


def _kill_floor_bow(runtime, slot):
    prefix = _floor_bow_prefix(slot)
    if not int(runtime.get(prefix, 0)):
        return False
    if _runtime_int(runtime, prefix + "_state", _BOW_STATE_IDLE) == _BOW_STATE_DEATH:
        return False
    runtime[prefix + "_state"] = _BOW_STATE_DEATH
    runtime[prefix + "_anim"] = 0
    runtime[prefix + "_fired"] = 0
    runtime[prefix + "_cooldown"] = 0
    print("MAP2_FLOOR_BOW_DEATH slot=%d" % int(slot))
    return True


def _hide_floor_bow(runtime, slot):
    prefix = _floor_bow_prefix(slot)
    runtime[prefix] = 0
    runtime[prefix + "_bound"] = 1
    runtime[prefix + "_state"] = _BOW_STATE_IDLE
    runtime[prefix + "_anim"] = 0
    runtime[prefix + "_fired"] = 0
    runtime[prefix + "_vel_y"] = 0
    runtime[prefix + "_cooldown"] = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15)))


def _bow_overlaps_platform_x(bow_x, bow_w, slot):
    x0, x1 = _platform_bounds(slot)
    return int(bow_x) < x1 and int(bow_x) + int(bow_w) > x0


def _try_land_bow_on_platform(old_y, new_y, bow_x, bow_w, bow_h, runtime, screen_h):
    old_foot = int(old_y) + int(bow_h)
    new_foot = int(new_y) + int(bow_h)
    for slot in (0, 1, 2):
        top = _platform_top_for_slot(runtime, slot, screen_h)
        if top is None:
            continue
        if old_foot <= top and new_foot >= top and _bow_overlaps_platform_x(bow_x, bow_w, slot):
            return int(top) - int(bow_h)
    return None


def _update_free_floor_bow_physics(runtime, slot, screen_h):
    prefix = _floor_bow_prefix(slot)
    if not int(runtime.get(prefix, 0)) or int(runtime.get(prefix + "_bound", 1)):
        return
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    bow_x = _floor_bow_x(runtime, slot)
    bow_y = _floor_bow_y(runtime, slot)
    for platform_slot in (0, 1, 2):
        top = _platform_top_for_slot(runtime, platform_slot, screen_h)
        if top is not None and int(bow_y) + bow_h == int(top) and _bow_overlaps_platform_x(bow_x, bow_w, platform_slot):
            runtime[prefix + "_vel_y"] = 0
            return
    vel_y = _runtime_int(runtime, prefix + "_vel_y", 0) + int(getattr(config, "MAP2_PLAYER_GRAVITY", 2))
    max_fall = int(getattr(config, "MAP2_PLAYER_MAX_FALL_SPEED", 8))
    if vel_y > max_fall:
        vel_y = max_fall
    new_y = int(bow_y) + vel_y
    landed_y = _try_land_bow_on_platform(bow_y, new_y, bow_x, bow_w, bow_h, runtime, screen_h)
    if landed_y is None:
        runtime[prefix + "_y"] = new_y
        runtime[prefix + "_vel_y"] = vel_y
        if new_y > int(getattr(config, "MAP2_PLAYER_DEATH_Y", 272)):
            _hide_floor_bow(runtime, slot)
    else:
        runtime[prefix + "_y"] = landed_y
        runtime[prefix + "_vel_y"] = 0


def _floor_bow_frame(slot, state, anim):
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    hold = int(getattr(config, "ENEMY_FRAME_HOLD", 3))
    if hold < 1:
        hold = 1
    frame = int(anim) // hold
    if int(state) == _BOW_STATE_DEATH:
        if frame >= _BOW_DEATH_FRAME_COUNT:
            frame = _BOW_DEATH_FRAME_COUNT - 1
        src_y = bow_h * 3
        if int(slot) == 2:
            frame += _BOW_DEATH_FRAME_COUNT
        return frame * bow_w, src_y
    if int(state) == _BOW_STATE_SHOOT:
        max_frames = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_FRAMES", 10))
        if max_frames < 1:
            max_frames = 10
        if frame >= max_frames:
            frame = max_frames - 1
        src_y = 0 if int(slot) == 0 else bow_h
        return frame * bow_w, src_y
    idle_frames = int(getattr(config, "MAP2_FLOOR_BOW_IDLE_FRAMES", 5))
    if idle_frames < 1:
        idle_frames = 5
    frame %= idle_frames
    src_y = int(getattr(config, "MAP2_FLOOR_BOW_SRC_Y", bow_h * 2))
    if int(slot) == 2:
        frame += idle_frames
    return frame * bow_w, src_y


def _spawn_floor_bow_arrow(runtime, slot):
    arrows = runtime.get("floor_bow_arrows")
    if arrows is None:
        arrows = []
        runtime["floor_bow_arrows"] = arrows
    max_arrows = int(getattr(config, "MAP2_FLOOR_BOW_MAX_ARROWS", 4))
    if max_arrows < 1:
        max_arrows = 1
    arrow_w = int(getattr(config, "MAP2_FLOOR_BOW_ARROW_W", getattr(config, "ENEMY_BULLET_W", 16)))
    arrow_h = int(getattr(config, "MAP2_FLOOR_BOW_ARROW_H", getattr(config, "ENEMY_BULLET_H", 16)))
    speed = int(getattr(config, "MAP2_FLOOR_BOW_ARROW_SPEED", getattr(config, "ENEMY_BULLET_SPEED", 3)))
    if speed < 1:
        speed = 1
    bow_x = _floor_bow_x(runtime, slot)
    bow_y = _floor_bow_y(runtime, slot)
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    if int(slot) == 0:
        arrow_x = bow_x + bow_w
        vel_x = speed
    else:
        arrow_x = bow_x - arrow_w
        vel_x = -speed
    arrow_y = bow_y + ((bow_h - arrow_h) // 2)
    row = [int(arrow_x), int(arrow_y), int(vel_x), int(arrow_w), int(arrow_h), 1, int(slot)]
    i = 0
    while i < len(arrows):
        if not int(arrows[i][5]):
            arrows[i] = row
            return
        i += 1
    if len(arrows) < max_arrows:
        arrows.append(row)


def _update_floor_bow_actor(runtime, slot, side_key):
    if not int(runtime.get(side_key, 0)):
        return
    prefix = "floor_left_bow" if int(slot) == 0 else "floor_right_bow"
    interval = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15)))
    if interval < 1:
        interval = 15
    state_key = prefix + "_state"
    anim_key = prefix + "_anim"
    cooldown_key = prefix + "_cooldown"
    fired_key = prefix + "_fired"
    state = _runtime_int(runtime, state_key, 0)
    anim = _runtime_int(runtime, anim_key, 0) + 1
    if state == _BOW_STATE_DEATH:
        hold = int(getattr(config, "ENEMY_FRAME_HOLD", 3))
        if hold < 1:
            hold = 1
        if anim >= _BOW_DEATH_FRAME_COUNT * hold:
            _hide_floor_bow(runtime, slot)
            return
    elif state == _BOW_STATE_IDLE:
        cooldown = _runtime_int(runtime, cooldown_key, interval) - 1
        if cooldown <= 0:
            state = _BOW_STATE_SHOOT
            anim = 0
            runtime[fired_key] = 0
        runtime[cooldown_key] = cooldown
    else:
        fire_frame = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_FIRE_FRAME", getattr(config, "ENEMY_SHOOT_FIRE_FRAME", 4)))
        if fire_frame < 0:
            fire_frame = 0
        hold = int(getattr(config, "ENEMY_FRAME_HOLD", 3))
        if hold < 1:
            hold = 1
        if not int(runtime.get(fired_key, 0)) and (anim // hold) >= fire_frame:
            _spawn_floor_bow_arrow(runtime, slot)
            runtime[fired_key] = 1
        shoot_frames = int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_FRAMES", 10))
        if shoot_frames < 1:
            shoot_frames = 10
        if anim >= shoot_frames * hold:
            state = 0
            anim = 0
            runtime[fired_key] = 0
            runtime[cooldown_key] = interval
    runtime[state_key] = state
    runtime[anim_key] = anim


def _arrow_hits_wall(x, y, w, h, screen_h):
    strip_w = int(getattr(config, "MAP2_WALL_STRIP_W", 32))
    left_x = int(getattr(config, "MAP2_LEFT_WALL_X", 0))
    right_x = int(getattr(config, "MAP2_RIGHT_WALL_X", 288))
    if _aabb_overlap(int(x), int(y), int(w), int(h), left_x, 0, strip_w, int(screen_h)):
        return True
    if _aabb_overlap(int(x), int(y), int(w), int(h), right_x, 0, strip_w, int(screen_h)):
        return True
    return False


def _arrow_hits_floor(runtime, x, y, w, h, screen_h):
    for slot in (0, 1, 2):
        rect = _platform_rect(runtime, slot, screen_h)
        if rect is None:
            continue
        if _aabb_overlap(int(x), int(y), int(w), int(h), rect[0], rect[1], rect[2], rect[3]):
            return True
    return False


def _arrow_hits_bow_enemy(runtime, x, y, w, h, owner_slot, screen_h):
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    for slot in (0, 2):
        if int(owner_slot) == int(slot):
            continue
        if not _floor_bow_alive(runtime, slot):
            continue
        bow_x = _floor_bow_x(runtime, slot)
        bow_y = _floor_bow_y(runtime, slot)
        if bow_y >= int(screen_h) or bow_y + bow_h <= 0:
            continue
        if _aabb_overlap(int(x), int(y), int(w), int(h), bow_x, bow_y, bow_w, bow_h):
            _kill_floor_bow(runtime, slot)
            return True
    return False


def _update_floor_bow_arrows(runtime, screen_h):
    arrows = runtime.get("floor_bow_arrows")
    if not arrows:
        return
    screen_w = int(getattr(config, "SCREEN_W", 320))
    margin = int(getattr(config, "ENEMY_BULLET_CULL_MARGIN", 32))
    i = 0
    while i < len(arrows):
        row = arrows[i]
        if int(row[5]):
            row[0] = int(row[0]) + int(row[2])
            owner_slot = int(row[6]) if len(row) > 6 else -1
            if int(row[0]) + int(row[3]) < -margin or int(row[0]) > screen_w + margin or int(row[1]) + int(row[4]) < -margin or int(row[1]) > int(screen_h) + margin:
                row[5] = 0
            elif _arrow_hits_wall(row[0], row[1], row[3], row[4], screen_h):
                row[5] = 0
            elif _arrow_hits_floor(runtime, row[0], row[1], row[3], row[4], screen_h):
                row[5] = 0
            elif _arrow_hits_bow_enemy(runtime, row[0], row[1], row[3], row[4], owner_slot, screen_h):
                row[5] = 0
        i += 1


def _player_hits_floor_bow(runtime, player_x, player_y, player_w, player_h, screen_h):
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    if bow_w <= 0 or bow_h <= 0:
        return False
    for slot, side_key in ((0, "floor_left_bow"), (2, "floor_right_bow")):
        if not int(runtime.get(side_key, 0)):
            continue
        if not _floor_bow_alive(runtime, slot):
            continue
        bow_x = _floor_bow_x(runtime, slot)
        bow_y = _floor_bow_y(runtime, slot)
        if bow_y >= int(screen_h) or bow_y + bow_h <= 0:
            continue
        if _aabb_overlap(int(player_x), int(player_y), int(player_w), int(player_h), bow_x, bow_y, bow_w, bow_h):
            return True
    return False


def _player_hits_floor_bow_arrow(runtime, player_x, player_y, player_w, player_h):
    arrows = runtime.get("floor_bow_arrows")
    if not arrows:
        return False
    for row in arrows:
        if not int(row[5]):
            continue
        if _aabb_overlap(int(player_x), int(player_y), int(player_w), int(player_h), int(row[0]), int(row[1]), int(row[3]), int(row[4])):
            row[5] = 0
            return True
    return False


def _reset_star(runtime):
    star_h = int(getattr(config, "MAP2_STAR_H", 16))
    runtime["star_active"] = 0
    runtime["star_x"] = 0
    runtime["star_y"] = -star_h
    runtime["star_vy"] = int(getattr(config, "MAP2_STAR_SPEED", 3))


def _update_star_python(runtime, player_x, player_y, player_w, player_h, screen_h):
    if not bool(getattr(config, "MAP2_STAR_ENABLED", True)):
        _reset_star(runtime)
        return False
    star_w = int(getattr(config, "MAP2_STAR_W", 16))
    star_h = int(getattr(config, "MAP2_STAR_H", 16))
    speed = int(getattr(config, "MAP2_STAR_SPEED", 3))
    if speed < 1:
        speed = 3
    spawn_frames = int(getattr(config, "MAP2_STAR_SPAWN_FRAMES", 150))
    if spawn_frames < 1:
        spawn_frames = 150
    if int(runtime.get("star_started", 0)) and not int(runtime.get("star_active", 0)):
        timer = _runtime_int(runtime, "star_timer", 0) + 1
        if timer >= spawn_frames:
            lever_x = int(getattr(config, "MAP2_LEVER_X", 144))
            lever_w = int(getattr(config, "MAP2_LEVER_W", 32))
            runtime["star_x"] = lever_x + (lever_w // 2) - (star_w // 2)
            runtime["star_y"] = -star_h
            runtime["star_vy"] = speed
            runtime["star_active"] = 1
            timer = 0
        runtime["star_timer"] = timer
    if not int(runtime.get("star_active", 0)):
        return False
    x = _runtime_int(runtime, "star_x", 0)
    y = _runtime_int(runtime, "star_y", -star_h) + speed
    runtime["star_y"] = y
    if y > int(screen_h):
        _reset_star(runtime)
        return False
    if _aabb_overlap(int(player_x), int(player_y), int(player_w), int(player_h), x, y, star_w, star_h):
        _reset_star(runtime)
        return True
    for slot in (0, 2):
        if not _floor_bow_alive(runtime, slot):
            continue
        bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
        bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
        bow_x = _floor_bow_x(runtime, slot)
        bow_y = _floor_bow_y(runtime, slot)
        if _aabb_overlap(x, y, star_w, star_h, bow_x, bow_y, bow_w, bow_h):
            _kill_floor_bow(runtime, slot)
            _reset_star(runtime)
            return False
    if _arrow_hits_floor(runtime, x, y, star_w, star_h, screen_h):
        _reset_star(runtime)
        return False
    return False


def _update_environment_native(lgfx, runtime, current_slot, airborne, screen_h):
    if lgfx is None or not hasattr(lgfx, "update_map2_environment_native"):
        return False, False
    _ensure_runtime_state(runtime)
    _sync_runtime_to_env_side_buffers(runtime)
    _sync_runtime_to_env_buffer(runtime)
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    try:
        ok = lgfx.update_map2_environment_native(
            runtime["map2_env_buf"],
            _MAP2_ENV_STRIDE,
            runtime["map2_bow_buf"],
            _MAP2_BOW_STRIDE,
            _MAP2_BOW_COUNT,
            runtime["map2_collect_buf"],
            _MAP2_COLLECT_STRIDE,
            int(screen_h),
            int(getattr(config, "MAP2_FLOOR_X", 32)),
            int(getattr(config, "MAP2_FLOOR_Y", 208)),
            int(getattr(config, "MAP2_FLOOR_LEFT_W", 96)),
            int(getattr(config, "MAP2_FLOOR_MIDDLE_W", 64)),
            int(getattr(config, "MAP2_FLOOR_H", 32)),
            int(runtime.get("wall_h", int(getattr(config, "MAP2_WALL_H", screen_h))) or int(screen_h)),
            bow_w,
            bow_h,
            int(getattr(config, "MAP2_FLOOR_BOW_LEFT_OFFSET_X", 32)),
            int(getattr(config, "MAP2_FLOOR_BOW_RIGHT_OFFSET_X", 32)),
            bool(getattr(config, "MAP2_FLOOR_BOW_ENABLED", True)),
            int(getattr(config, "MAP2_FLOOR_BOW_CHANCE", 50)),
            int(getattr(config, "MAP2_FLOOR_BOW_MIN_GAP", 1)),
            int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15))),
            int(getattr(config, "MAP2_DOOR_SCROLL_SPEED", 1)),
            int(getattr(config, "MAP2_FLOOR_PLATFORM_SPEED", 5)),
            int(current_slot),
            bool(airborne),
            0,
            2,
            int(getattr(config, "MAP2_WALL_SCROLL_SPEED", 1)),
            int(getattr(config, "SCREEN_H", int(screen_h))),
            0,
            1,
            10,
            12,
            14,
        )
    except Exception as exc:
        if bool(getattr(config, "MAP2_NATIVE_UPDATE_VERBOSE", False)):
            print("MAP2_ENV_NATIVE_FALLBACK %r" % (exc,))
        return False, False
    if not ok:
        return False, False
    player_death = _sync_env_buffer_to_runtime(runtime)
    _sync_env_side_buffers_to_runtime(runtime)
    return True, player_death


def _update_environment_python(runtime, current_slot, airborne, screen_h):
    player_death = False
    if bool(runtime.get("lever_running", False)):
        wall_h = int(runtime.get("wall_h", 240) or 240)
        wall_speed = int(runtime.get("collect_wall_speed", int(getattr(config, "MAP2_WALL_SCROLL_SPEED", 1))) or 1)
        if wall_speed < 1:
            wall_speed = 1
        scroll_y = int(runtime.get("wall_scroll_y", 0) or 0) + wall_speed
        if wall_h > 0:
            scroll_y %= wall_h
        runtime["wall_scroll_y"] = scroll_y
        floor_y = int(getattr(config, "MAP2_FLOOR_Y", 208))
        floor_h = int(getattr(config, "MAP2_FLOOR_H", 32))
        platform_speed = int(getattr(config, "MAP2_FLOOR_PLATFORM_SPEED", 5))
        slot = current_slot if not airborne else -1
        left_y = _runtime_int(runtime, "floor_left_y", floor_y) + platform_speed
        if slot == 0 and left_y >= int(screen_h):
            player_death = True
        if left_y > int(screen_h):
            left_y = -floor_h
            _roll_floor_bow(runtime, "floor_left_bow", "floor_left_bow_gap")
            _request_collect_spawn(runtime, 0)
        right_y = _runtime_int(runtime, "floor_right_y", floor_y) - platform_speed
        if slot == 2 and right_y < 0:
            player_death = True
        if right_y + floor_h < 0:
            right_y = int(screen_h)
            _roll_floor_bow(runtime, "floor_right_bow", "floor_right_bow_gap")
            _request_collect_spawn(runtime, 2)
        runtime["floor_left_y"] = left_y
        runtime["floor_right_y"] = right_y
        if runtime.get("door_enabled", False):
            door_y = int(runtime.get("door_y", int(getattr(config, "MAP2_DOOR_START_Y", 128))) or 0)
            door_y += int(getattr(config, "MAP2_DOOR_SCROLL_SPEED", 1))
            runtime["door_y"] = door_y
            if door_y >= int(getattr(config, "SCREEN_H", 240)):
                runtime["door_enabled"] = False
    return player_death


def _platform_slot_for_player(player_x, player_w):
    floor_x = int(getattr(config, "MAP2_FLOOR_X", 32))
    left_w = int(getattr(config, "MAP2_FLOOR_LEFT_W", 96))
    middle_w = int(getattr(config, "MAP2_FLOOR_MIDDLE_W", 64))
    right_w = int(getattr(config, "MAP2_FLOOR_RIGHT_W", 96))
    foot_x = int(player_x) + (int(player_w) // 2)
    left_x1 = floor_x + left_w
    middle_x1 = left_x1 + middle_w
    right_x1 = middle_x1 + right_w
    if foot_x < floor_x or foot_x >= right_x1:
        return None
    if foot_x < left_x1:
        return 0
    if foot_x < middle_x1:
        return 1
    return 2


def _platform_bounds(slot):
    floor_x = int(getattr(config, "MAP2_FLOOR_X", 32))
    left_w = int(getattr(config, "MAP2_FLOOR_LEFT_W", 96))
    middle_w = int(getattr(config, "MAP2_FLOOR_MIDDLE_W", 64))
    right_w = int(getattr(config, "MAP2_FLOOR_RIGHT_W", 96))
    if int(slot) == 0:
        return floor_x, floor_x + left_w
    if int(slot) == 1:
        return floor_x + left_w, floor_x + left_w + middle_w
    return floor_x + left_w + middle_w, floor_x + left_w + middle_w + right_w


def _clamp_player_to_slot(player_x, player_w, slot):
    x0, x1 = _platform_bounds(slot)
    half_w = int(player_w) // 2
    min_x = x0 - half_w
    max_x = x1 - 1 - half_w
    if max_x < min_x:
        max_x = min_x
    px = int(player_x)
    if px < min_x:
        return min_x
    if px > max_x:
        return max_x
    return px


def _platform_top_for_slot(runtime, slot, screen_h):
    floor_y = int(getattr(config, "MAP2_FLOOR_Y", 208))
    if int(slot) == 0:
        platform_y = _runtime_int(runtime, "floor_left_y", floor_y)
    elif int(slot) == 1:
        platform_y = floor_y
    else:
        platform_y = _runtime_int(runtime, "floor_right_y", floor_y)
    if platform_y < 0 or platform_y >= int(screen_h):
        return None
    return platform_y


def _platform_y_for_player(runtime, player_x, player_w, player_h, screen_h):
    slot = _platform_slot_for_player(player_x, player_w)
    if slot is None:
        return None
    platform_y = _platform_top_for_slot(runtime, slot, screen_h)
    if platform_y is None:
        return None
    return platform_y - int(player_h)


def _platform_rect(runtime, slot, screen_h):
    top = _platform_top_for_slot(runtime, slot, screen_h)
    if top is None:
        return None
    x0, x1 = _platform_bounds(slot)
    return x0, int(top), x1 - x0, int(getattr(config, "MAP2_FLOOR_H", 32))


def _current_platform_y(runtime, slot, player_h, screen_h):
    top = _platform_top_for_slot(runtime, slot, screen_h)
    if top is None:
        return None
    return int(top) - int(player_h)


def _player_overlaps_platform_x(player_x, player_w, slot):
    x0, x1 = _platform_bounds(slot)
    return int(player_x) < x1 and int(player_x) + int(player_w) > x0


def _block_platform_sides(old_x, new_x, player_y, player_w, player_h, runtime, current_slot, screen_h):
    px0 = int(old_x)
    px1 = int(new_x)
    py = int(player_y)
    ph = int(player_h)
    pw = int(player_w)
    for slot in (0, 1, 2):
        if slot == current_slot:
            continue
        rect = _platform_rect(runtime, slot, screen_h)
        if rect is None:
            continue
        rx, ry, rw, rh = rect
        if py >= ry + rh or py + ph <= ry:
            continue
        if px1 > px0 and px0 + pw <= rx and px1 + pw > rx:
            px1 = rx - pw
        elif px1 < px0 and px0 >= rx + rw and px1 < rx + rw:
            px1 = rx + rw
    return px1


def _try_land_on_platform(old_y, new_y, player_x, player_w, player_h, runtime, screen_h):
    old_foot = int(old_y) + int(player_h)
    new_foot = int(new_y) + int(player_h)
    for slot in (0, 1, 2):
        top = _platform_top_for_slot(runtime, slot, screen_h)
        if top is None:
            continue
        if old_foot <= top and new_foot >= top and _player_overlaps_platform_x(player_x, player_w, slot):
            runtime["player_airborne"] = False
            runtime["player_vel_y"] = 0
            runtime["player_platform_slot"] = int(slot)
            return int(top) - int(player_h)
    return None


def check_enter(lgfx, runtime, latched, btn_a_pressed, btn_a_down, player_x, player_h, screen_w, screen_h):
    if not btn_a_pressed:
        if not btn_a_down:
            latched = False
        return runtime, latched, None
    if latched:
        return runtime, latched, None
    if not bool(getattr(config, "MAP_EXIT_ENABLED", False)):
        return runtime, latched, None
    px = int(player_x)
    if px < int(getattr(config, "MAP_EXIT_X0", 2816)) or px > int(getattr(config, "MAP_EXIT_X1", 2879)):
        return runtime, latched, None
    latched = True
    next_stage = str(getattr(config, "MAP_EXIT_NEXT_STAGE", "stage02") or "stage02")
    print("MAP_EXIT_TRIGGER next=%s x=%d" % (next_stage, px))
    if next_stage != "stage02" or not bool(getattr(config, "MAP2_ENABLED", False)):
        return runtime, latched, None
    if runtime is None:
        runtime = load_runtime(screen_w, screen_h)
    if runtime is None or not hasattr(lgfx, "render_elevator_scene_bands_rgb565"):
        print("MAP2_STAGE_LOAD_FAIL")
        return runtime, latched, None
    entered = enter(player_h)
    print("MAP2_STAGE_ENTER x=%d y=%d" % (entered[0], entered[1]))
    return runtime, latched, entered


def update(lgfx, input_lr=None, speed=None, player_x=None, player_w=None, player_h=None, runtime=None, btn_a_pressed=False, btn_b_down=False, btn_y_down=False, screen_w=320, screen_h=240):
    if runtime is not None and not isinstance(runtime, dict):
        old_input_lr = lgfx
        old_speed = input_lr
        old_player_x = speed
        old_player_w = player_x
        old_player_h = player_w
        old_runtime = player_h
        old_btn_a_pressed = runtime
        old_btn_b_down = btn_a_pressed
        old_btn_y_down = btn_b_down
        old_screen_w = btn_y_down
        old_screen_h = screen_w
        lgfx = None
        input_lr = old_input_lr
        speed = old_speed
        player_x = old_player_x
        player_w = old_player_w
        player_h = old_player_h
        runtime = old_runtime
        btn_a_pressed = old_btn_a_pressed
        btn_b_down = old_btn_b_down
        btn_y_down = old_btn_y_down
        screen_w = old_screen_w
        screen_h = old_screen_h
    _ensure_runtime_state(runtime)
    move_x = 0
    if input_lr > 20:
        move_x = speed
    elif input_lr < -20:
        move_x = -speed
    min_x = int(getattr(config, "MAP2_PLAYER_MIN_X", 32))
    max_x = int(getattr(config, "MAP2_PLAYER_MAX_X", 276))
    if max_x < min_x:
        max_x = min_x
    current_slot = _runtime_int(runtime, "player_platform_slot", 1)
    airborne = bool(runtime.get("player_airborne", False))
    if airborne:
        player_y = _runtime_int(runtime, "player_y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h))
    else:
        player_y = _current_platform_y(runtime, current_slot, player_h, screen_h)
        if player_y is None:
            runtime["player_airborne"] = True
            airborne = True
            player_y = _runtime_int(runtime, "player_y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h))
    next_x = max(min_x, min(max_x, int(player_x) + int(move_x)))
    next_x = _block_platform_sides(player_x, next_x, player_y, player_w, player_h, runtime, current_slot if not airborne else -1, screen_h)
    player_x = next_x
    if not airborne and not _player_overlaps_platform_x(player_x, player_w, current_slot):
        runtime["player_airborne"] = True
        runtime["player_vel_y"] = 0
        airborne = True
    if btn_a_pressed:
        lever_x = int(getattr(config, "MAP2_LEVER_X", 144))
        lever_y = int(getattr(config, "MAP2_LEVER_Y", 192))
        lever_w = int(getattr(config, "MAP2_LEVER_W", 32))
        lever_h = int(getattr(config, "MAP2_LEVER_H", 22))
        if _aabb_overlap(int(player_x), int(player_y), int(player_w), int(player_h), lever_x, lever_y, lever_w, lever_h):
            running = not bool(runtime.get("lever_running", False))
            runtime["lever_on"] = running
            runtime["lever_running"] = running
            if running and not int(runtime.get("star_started", 0)):
                runtime["star_started"] = 1
                runtime["star_timer"] = 0
            print("MAP2_LEVER_%s x=%d y=%d" % ("RUN" if running else "STOP", int(player_x), int(player_y)))
    env_ok, env_player_death = _update_environment_native(lgfx, runtime, current_slot, airborne, screen_h)
    if not env_ok:
        env_player_death = _update_environment_python(runtime, current_slot, airborne, screen_h)
    if env_player_death:
        return _respawn_player(runtime, player_h)
    if bool(runtime.get("lever_running", False)) and not airborne:
        player_y = _current_platform_y(runtime, current_slot, player_h, screen_h)
        if player_y is None:
            runtime["player_airborne"] = True
            runtime["player_vel_y"] = 0
            airborne = True
    native_ok, player_x, player_y = _update_bow_arrow_subsystem_native(lgfx, player_x, player_y, player_w, player_h, runtime, btn_b_down, btn_y_down, screen_w, screen_h)
    if not native_ok:
        player_x, player_y = _update_bow_arrow_subsystem_python(runtime, player_x, player_y, player_w, player_h, btn_b_down, btn_y_down, screen_w, screen_h)
    current_slot = _runtime_int(runtime, "player_platform_slot", current_slot)
    airborne = bool(runtime.get("player_airborne", False))
    if airborne:
        old_y = int(player_y)
        vel_y = _runtime_int(runtime, "player_vel_y", 0) + int(getattr(config, "MAP2_PLAYER_GRAVITY", 2))
        max_fall = int(getattr(config, "MAP2_PLAYER_MAX_FALL_SPEED", 8))
        if vel_y > max_fall:
            vel_y = max_fall
        new_y = old_y + vel_y
        landed_y = _try_land_on_platform(old_y, new_y, player_x, player_w, player_h, runtime, screen_h)
        if landed_y is None:
            runtime["player_airborne"] = True
            runtime["player_vel_y"] = vel_y
            player_y = new_y
        else:
            player_y = landed_y
    runtime["player_y"] = int(player_y)
    if _player_hits_floor_bow_arrow(runtime, player_x, player_y, player_w, player_h):
        return _respawn_player(runtime, player_h, "MAP2_PLAYER_ARROW_DEATH")
    if int(player_y) > int(getattr(config, "MAP2_PLAYER_DEATH_Y", 272)):
        return _respawn_player(runtime, player_h)
    return player_x, player_y


def _update_bow_arrow_subsystem_native(lgfx, player_x, player_y, player_w, player_h, runtime, btn_b_down=False, btn_y_down=False, screen_w=320, screen_h=240):
    if lgfx is None or not hasattr(lgfx, "update_map2_elevator_native"):
        return False, player_x, player_y
    _ensure_runtime_state(runtime)
    _sync_runtime_to_native_buffers(runtime)
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    arrow_w = int(getattr(config, "MAP2_FLOOR_BOW_ARROW_W", getattr(config, "ENEMY_BULLET_W", 16)))
    arrow_h = int(getattr(config, "MAP2_FLOOR_BOW_ARROW_H", getattr(config, "ENEMY_BULLET_H", 16)))
    try:
        ok = lgfx.update_map2_elevator_native(
            runtime["map2_bow_buf"],
            _MAP2_BOW_STRIDE,
            _MAP2_BOW_COUNT,
            runtime["map2_arrow_buf"],
            _MAP2_ARROW_STRIDE,
            int(runtime.get("map2_arrow_count", 4)),
            runtime["map2_swap_buf"],
            _MAP2_SWAP_STRIDE,
            runtime["map2_result_buf"],
            _MAP2_RESULT_STRIDE,
            int(player_x),
            int(player_y),
            int(player_w),
            int(player_h),
            bool(btn_b_down),
            bool(btn_y_down),
            int(screen_w),
            int(screen_h),
            int(getattr(config, "MAP2_FLOOR_X", 32)),
            int(getattr(config, "MAP2_FLOOR_Y", 208)),
            int(getattr(config, "MAP2_FLOOR_LEFT_W", 96)),
            int(getattr(config, "MAP2_FLOOR_MIDDLE_W", 64)),
            int(getattr(config, "MAP2_FLOOR_RIGHT_W", 96)),
            int(getattr(config, "MAP2_FLOOR_H", 32)),
            int(getattr(config, "MAP2_LEFT_WALL_X", 0)),
            int(getattr(config, "MAP2_RIGHT_WALL_X", 288)),
            int(getattr(config, "MAP2_WALL_STRIP_W", 32)),
            int(getattr(config, "MAP2_PLAYER_MIN_X", 32)),
            int(getattr(config, "MAP2_PLAYER_MAX_X", 276)),
            int(getattr(config, "MAP2_PLAYER_GRAVITY", 2)),
            int(getattr(config, "MAP2_PLAYER_MAX_FALL_SPEED", 8)),
            int(getattr(config, "MAP2_PLAYER_DEATH_Y", 272)),
            bow_w,
            bow_h,
            int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_INTERVAL", getattr(config, "ENEMY_SHOOT_INTERVAL", 15))),
            int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_FIRE_FRAME", getattr(config, "ENEMY_SHOOT_FIRE_FRAME", 4))),
            int(getattr(config, "MAP2_FLOOR_BOW_SHOOT_FRAMES", 10)),
            int(getattr(config, "ENEMY_FRAME_HOLD", 3)),
            int(getattr(config, "MAP2_FLOOR_BOW_ARROW_SPEED", getattr(config, "ENEMY_BULLET_SPEED", 3))),
            arrow_w,
            arrow_h,
            int(getattr(config, "ENEMY_BULLET_CULL_MARGIN", 32)),
            int(runtime.get("floor_left_y", int(getattr(config, "MAP2_FLOOR_Y", 208))) or 0),
            int(runtime.get("floor_right_y", int(getattr(config, "MAP2_FLOOR_Y", 208))) or 0),
            runtime["map2_collect_buf"],
            _MAP2_COLLECT_STRIDE,
            int(getattr(config, "MAP2_COLLECTIBLE_W", 32)),
            int(getattr(config, "MAP2_COLLECTIBLE_H", 32)),
            int(getattr(config, "MAP2_COLLECTIBLE_LOCAL_X", 32)),
            int(getattr(config, "MAP2_COLLECTIBLE_LOCAL_Y", -32)),
            int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5)),
            runtime["map2_star_buf"],
            _MAP2_STAR_STRIDE,
            bool(getattr(config, "MAP2_STAR_ENABLED", True)),
            int(getattr(config, "MAP2_STAR_W", 16)),
            int(getattr(config, "MAP2_STAR_H", 16)),
            int(getattr(config, "MAP2_STAR_SPEED", 3)),
            int(getattr(config, "MAP2_STAR_SPAWN_FRAMES", 150)),
            int(getattr(config, "MAP2_LEVER_X", 144)),
            int(getattr(config, "MAP2_LEVER_W", 32)),
        )
    except Exception as exc:
        if bool(getattr(config, "MAP2_NATIVE_UPDATE_VERBOSE", False)):
            print("MAP2_NATIVE_UPDATE_FALLBACK %r" % (exc,))
        return False, player_x, player_y
    if not ok:
        return False, player_x, player_y
    _sync_native_buffers_to_runtime(runtime)
    result = runtime["map2_result_buf"]
    player_x = _buf_get_i16(result, 0)
    player_y = _buf_get_i16(result, 2)
    runtime["player_y"] = int(player_y)
    if int(result[10]):
        runtime["player_airborne"] = bool(result[5])
        slot = _buf_get_i16(result, 6)
        if slot >= 0:
            runtime["player_platform_slot"] = int(slot)
        runtime["player_vel_y"] = _buf_get_i16(result, 8)
    if int(result[4]):
        reason = "MAP2_PLAYER_STAR_DEATH" if int(result[4]) == 2 else "MAP2_PLAYER_ARROW_DEATH"
        respawn_x, respawn_y = _respawn_player(runtime, player_h, reason)
        return True, respawn_x, respawn_y
    return True, player_x, player_y


def _update_bow_arrow_subsystem_python(runtime, player_x, player_y, player_w, player_h, btn_b_down, btn_y_down, screen_w, screen_h):
    swap_triggered, swap_pick_far, swap_kind, swap_index = _swap_hold_step(runtime, player_x, player_y, player_w, player_h, btn_b_down, btn_y_down, screen_w, screen_h)
    if swap_triggered:
        player_x, player_y, _swapped = _perform_swap(runtime, swap_kind, swap_index, player_x, player_y, player_w, player_h, screen_w, screen_h, swap_pick_far)
    _update_free_floor_bow_physics(runtime, 0, screen_h)
    _update_free_floor_bow_physics(runtime, 2, screen_h)
    _update_floor_bow_actor(runtime, 0, "floor_left_bow")
    _update_floor_bow_actor(runtime, 2, "floor_right_bow")
    _update_floor_bow_arrows(runtime, screen_h)
    if _update_star_python(runtime, player_x, player_y, player_w, player_h, screen_h):
        return _respawn_player(runtime, player_h, "MAP2_PLAYER_STAR_DEATH")
    return player_x, player_y


def submit(lgfx, scene_buf, scene_buf_back, screen_w, screen_h, band_h, runtime, sprite_left, sprite_right, anim_idx, facing, sprite_w, sprite_h, player_x, draw_off_x, player_y, draw_off_y, defer_final_wait=False):
    _ensure_runtime_state(runtime)
    spr_x = int(player_x) + int(draw_off_x)
    spr_y = int(player_y) + int(draw_off_y)
    spr_rgb = sprite_left[anim_idx] if int(facing) < 0 else sprite_right[anim_idx]
    player_key = _swap16(int(getattr(config, "CAMERA_PLAYER_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
    layer_key = _swap16(int(getattr(config, "MAP2_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
    lever_running = bool(runtime.get("lever_running", False))
    lever_src_x = int(getattr(config, "MAP2_LEVER_ON_SRC_X", 64) if lever_running else getattr(config, "MAP2_LEVER_OFF_SRC_X", 32))
    lever_src_y = int(getattr(config, "MAP2_LEVER_ON_SRC_Y", 138) if lever_running else getattr(config, "MAP2_LEVER_OFF_SRC_Y", 138))
    bow_w = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_W", getattr(config, "ENEMY_FRAME_W", 32)))
    bow_h = int(getattr(config, "MAP2_FLOOR_BOW_FRAME_H", getattr(config, "ENEMY_FRAME_H", 32)))
    left_bow_x = _floor_bow_x(runtime, 0)
    left_bow_y = _floor_bow_y(runtime, 0)
    right_bow_x = _floor_bow_x(runtime, 2)
    right_bow_y = _floor_bow_y(runtime, 2)
    left_bow_src_x, left_bow_src_y = _floor_bow_frame(0, runtime.get("floor_left_bow_state", 0), runtime.get("floor_left_bow_anim", 0))
    right_bow_src_x, right_bow_src_y = _floor_bow_frame(2, runtime.get("floor_right_bow_state", 0), runtime.get("floor_right_bow_anim", 0))
    collect_w = int(getattr(config, "MAP2_COLLECTIBLE_W", 32))
    collect_h = int(getattr(config, "MAP2_COLLECTIBLE_H", 32))
    star_w = int(getattr(config, "MAP2_STAR_W", 16))
    star_h = int(getattr(config, "MAP2_STAR_H", 16))
    arrows = runtime.get("floor_bow_arrows") or []
    arrow_args = []
    max_arrows = int(getattr(config, "MAP2_FLOOR_BOW_MAX_ARROWS", 4))
    if max_arrows < 1:
        max_arrows = 1
    i = 0
    while i < 4:
        if i < len(arrows) and int(arrows[i][5]):
            row = arrows[i]
            arrow_args.extend((int(row[0]), int(row[1]), int(row[2]), True))
        else:
            arrow_args.extend((0, 0, 0, False))
        i += 1
    return lgfx.render_elevator_scene_bands_rgb565(
        scene_buf,
        scene_buf_back,
        screen_w,
        screen_h,
        band_h,
        runtime["far"],
        runtime["wall"],
        int(runtime["wall_w"]),
        int(runtime["wall_h"]),
        runtime["door"],
        int(runtime["door_w"]),
        int(runtime["door_h"]),
        runtime["floor"],
        int(runtime["floor_w"]),
        int(runtime["floor_h"]),
        runtime["object_atlas"],
        int(runtime["object_atlas_w"]),
        int(runtime["object_atlas_h"]),
        int(getattr(config, "MAP2_LEVER_X", 144)),
        int(getattr(config, "MAP2_LEVER_Y", 192)),
        int(getattr(config, "MAP2_LEVER_W", 32)),
        int(getattr(config, "MAP2_LEVER_H", 22)),
        lever_src_x,
        lever_src_y,
        int(getattr(config, "MAP2_FLOOR_X", 32)),
        int(getattr(config, "MAP2_FLOOR_Y", 208)),
        int(getattr(config, "MAP2_FLOOR_LEFT_W", 96)),
        int(getattr(config, "MAP2_FLOOR_MIDDLE_W", 64)),
        _runtime_int(runtime, "floor_left_y", int(getattr(config, "MAP2_FLOOR_Y", 208))),
        _runtime_int(runtime, "floor_right_y", int(getattr(config, "MAP2_FLOOR_Y", 208))),
        spr_rgb,
        sprite_w,
        sprite_h,
        spr_x,
        spr_y,
        player_key,
        int(runtime.get("wall_scroll_y", 0) or 0),
        int(runtime.get("door_y", 0) or 0),
        bool(runtime.get("door_enabled", False)),
        layer_key,
        runtime["floor_bow_sheet"],
        int(runtime["floor_bow_sheet_w"]),
        int(runtime["floor_bow_sheet_h"]),
        bow_w,
        bow_h,
        left_bow_src_x,
        right_bow_src_x,
        left_bow_src_y,
        left_bow_x,
        left_bow_y,
        bool(runtime.get("floor_left_bow", 0)),
        right_bow_x,
        right_bow_y,
        bool(runtime.get("floor_right_bow", 0)),
        right_bow_src_y,
        int(getattr(config, "MAP2_FLOOR_BOW_ARROW_W", getattr(config, "ENEMY_BULLET_W", 16))),
        int(getattr(config, "MAP2_FLOOR_BOW_ARROW_H", getattr(config, "ENEMY_BULLET_H", 16))),
        int(getattr(config, "MAP2_FLOOR_BOW_ARROW_SRC_X", getattr(config, "ENEMY_BULLET_SRC_X", 112))),
        int(getattr(config, "MAP2_FLOOR_BOW_ARROW_SRC_Y_RIGHT", getattr(config, "ENEMY_BULLET_SRC_Y_RIGHT", 96))),
        int(getattr(config, "MAP2_FLOOR_BOW_ARROW_SRC_Y_LEFT", getattr(config, "ENEMY_BULLET_SRC_Y_LEFT", 112))),
        arrow_args[0],
        arrow_args[1],
        arrow_args[2],
        arrow_args[3],
        arrow_args[4],
        arrow_args[5],
        arrow_args[6],
        arrow_args[7],
        arrow_args[8],
        arrow_args[9],
        arrow_args[10],
        arrow_args[11],
        arrow_args[12],
        arrow_args[13],
        arrow_args[14],
        arrow_args[15],
        bool(runtime.get("swap_preview_active", 0) and runtime.get("swap_preview_valid", 0)),
        int(runtime.get("swap_preview_x", 0) or 0),
        int(runtime.get("swap_preview_y", 0) or 0),
        int(runtime.get("swap_preview_w", 0) or 0),
        int(runtime.get("swap_preview_h", 0) or 0),
        int(runtime.get("swap_preview_kind", 0) or 0),
        bool(runtime.get("collect_active", 0) and int(runtime.get("collect_count", 0) or 0) < int(runtime.get("collect_total", int(getattr(config, "MAP2_COLLECTIBLE_TOTAL", 5))) or 5)),
        int(runtime.get("collect_x", 0) or 0),
        int(runtime.get("collect_y", 0) or 0),
        collect_w,
        collect_h,
        int(getattr(config, "MAP2_COLLECTIBLE_SRC_X", 96)),
        int(getattr(config, "MAP2_COLLECTIBLE_SRC_Y", 128)),
        bool(runtime.get("star_active", 0)),
        int(runtime.get("star_x", 0) or 0),
        int(runtime.get("star_y", -star_h) or -star_h),
        star_w,
        star_h,
        int(getattr(config, "MAP2_STAR_SRC_X", 48)),
        int(getattr(config, "MAP2_STAR_SRC_Y", 112)),
        False,
        bool(defer_final_wait),
    )


def step(lgfx, scene_buf, scene_buf_back, screen_w, screen_h, band_h, runtime, input_lr, speed, player_x, player_w, player_h, btn_a_pressed, sprite_left, sprite_right, anim_counter, anim_idx, facing, sprite_w, sprite_h, draw_off_x, draw_off_y, tail_inflight, btn_b_down=False, btn_y_down=False, tail_overlap_enabled=False):
    player_x, player_y = update(lgfx, input_lr, speed, player_x, player_w, player_h, runtime, btn_a_pressed, btn_b_down, btn_y_down, screen_w, screen_h)
    moving = input_lr > 20 or input_lr < -20
    if moving:
        anim_counter += 1
        anim_idx = (anim_counter // 4) & 0x03
    else:
        anim_counter = 0
        anim_idx = 0
    if tail_inflight and hasattr(lgfx, "band_pipeline_tail_wait"):
        try:
            lgfx.band_pipeline_tail_wait()
        except Exception:
            tail_overlap_enabled = False
    submit(
        lgfx,
        scene_buf,
        scene_buf_back,
        screen_w,
        screen_h,
        band_h,
        runtime,
        sprite_left,
        sprite_right,
        anim_idx,
        facing,
        sprite_w,
        sprite_h,
        player_x,
        draw_off_x,
        player_y,
        draw_off_y,
        bool(tail_overlap_enabled),
    )
    return player_x, player_y, anim_counter, anim_idx, bool(tail_overlap_enabled)
