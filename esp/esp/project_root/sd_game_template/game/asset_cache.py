_blobs = {}
_player_frames = None
_player_frames_key = None
_map1_key = None
_map2_blobs = None
_map2_key = None


def _verbose(config):
    try:
        return bool(getattr(config, "ASSET_CACHE_VERBOSE", False))
    except Exception:
        return False


def _resolve(path):
    text = str(path or "")
    if not text:
        return text
    if text.startswith("/"):
        return text
    return "/sd/" + text


def _load_blob(path, exp_bytes):
    global _blobs
    abs_path = _resolve(path)
    cached = _blobs.get(abs_path)
    if cached is not None and len(cached) == int(exp_bytes):
        return cached
    try:
        with open(abs_path, "rb") as fp:
            data = fp.read()
    except Exception:
        return None
    if data is None or len(data) != int(exp_bytes):
        return None
    _blobs[abs_path] = data
    return data


def get_blob(path, exp_bytes):
    data = _blobs.get(_resolve(path))
    if data is not None and len(data) == int(exp_bytes):
        return data
    return None


def get_player_frames(frame_w, frame_h):
    global _player_frames, _player_frames_key
    key = (int(frame_w), int(frame_h))
    if _player_frames is not None and _player_frames_key == key:
        return _player_frames
    return None


def _slice_player_frames(sheet, frame_w, frame_h):
    global _player_frames, _player_frames_key
    sheet_w = 128
    frame_w = int(frame_w)
    frame_h = int(frame_h)
    if sheet is None or len(sheet) != sheet_w * frame_h * 2 * 2:
        return None
    frames_right = []
    frames_left = []
    frame_bytes = frame_w * frame_h * 2
    for row, out in ((0, frames_right), (1, frames_left)):
        for col in range(4):
            buf = bytearray(frame_bytes)
            di = 0
            y = 0
            while y < frame_h:
                off = (((row * frame_h + y) * sheet_w) + (col * frame_w)) * 2
                buf[di:di + frame_w * 2] = sheet[off:off + frame_w * 2]
                di += frame_w * 2
                y += 1
            out.append(bytes(buf))
    _player_frames = (frames_right, frames_left)
    _player_frames_key = (frame_w, frame_h)
    return _player_frames


def _preload_item(path, exp_bytes):
    if not path or int(exp_bytes) <= 0:
        return 0
    data = _load_blob(path, exp_bytes)
    if data is None:
        return -1
    return len(data)


def _preload_animation_sheets(config):
    try:
        import ujson as json
    except Exception:
        try:
            import json
        except Exception:
            json = None
    if json is None:
        return 0
    try:
        with open(_resolve(getattr(config, "OBJECT_ANIMATIONS_JSON_PATH", "")), "r") as fp:
            raw = json.load(fp)
    except Exception:
        return 0
    if not isinstance(raw, dict):
        return 0
    total = 0
    for anim_id in raw:
        spec = raw.get(anim_id)
        if not isinstance(spec, dict):
            continue
        path = spec.get("sheet_rgb565") or spec.get("rgb565") or spec.get("path")
        frame_w = int(spec.get("frame_w", 0) or 0)
        frame_h = int(spec.get("frame_h", 0) or 0)
        frame_count = int(spec.get("frames", 0) or 0)
        sheet_w = int(spec.get("sheet_w", frame_w * frame_count) or (frame_w * frame_count))
        sheet_h = int(spec.get("sheet_h", frame_h) or frame_h)
        loaded = _preload_item(path, sheet_w * sheet_h * 2)
        if loaded < 0:
            return -1
        total += loaded
    return total


def preload_map1(config, screen_w=None, screen_h=None):
    global _map1_key
    if not bool(getattr(config, "MAP1_PRELOAD_ENABLED", True)):
        return False
    sw = int(screen_w if screen_w is not None else getattr(config, "SCREEN_W", 320))
    sh = int(screen_h if screen_h is not None else getattr(config, "SCREEN_H", 240))
    player_w = int(getattr(config, "CAMERA_TEST_PLAYER_SPRITE_W", 32))
    player_h = int(getattr(config, "CAMERA_TEST_PLAYER_SPRITE_H", 32))
    tileset_w = int(getattr(config, "TILESET_ATLAS_W", 128))
    tileset_h = int(getattr(config, "TILESET_ATLAS_H", 128))
    objects_w = int(getattr(config, "OBJECTS_ATLAS_W", 0))
    objects_h = int(getattr(config, "OBJECTS_ATLAS_H", 0))
    enemy_w = int(getattr(config, "ENEMY_SHEET_W", 320))
    enemy_h = int(getattr(config, "ENEMY_SHEET_H", 128))
    monk_w = int(getattr(config, "ENEMY_MONK_FRAME_W", 32)) * int(getattr(config, "ENEMY_MONK_FRAME_COUNT", 4))
    monk_h = int(getattr(config, "ENEMY_MONK_FRAME_H", 48)) * int(getattr(config, "ENEMY_MONK_SHEET_ROWS", 1) or 1)
    orb_w = int(getattr(config, "ENEMY_MONK_ORB_ATLAS_W", objects_w))
    orb_h = int(getattr(config, "ENEMY_MONK_ORB_ATLAS_H", objects_h))
    key = (sw, sh, player_w, player_h, tileset_w, tileset_h, objects_w, objects_h, enemy_w, enemy_h, monk_w, monk_h, orb_w, orb_h)
    if _map1_key == key:
        return True
    total = 0
    specs = (
        (getattr(config, "CAMERA_TEST_ROOT_BG_FAR_RGB565", ""), sw * sh * 2),
        (getattr(config, "CAMERA_PLAYER_SPRITESHEET_PATH", ""), 128 * (player_h * 2) * 2),
        (getattr(config, "TILESET_RGB565_PATH", ""), tileset_w * tileset_h * 2),
        (getattr(config, "OBJECTS_ATLAS_RGB565_PATH", ""), objects_w * objects_h * 2),
        (getattr(config, "ENEMY_SHEET_RGB565_PATH", ""), enemy_w * enemy_h * 2),
        (getattr(config, "ENEMY_MONK_SHEET_RGB565_PATH", ""), monk_w * monk_h * 2),
        (getattr(config, "ENEMY_MONK_ORB_ATLAS_RGB565_PATH", ""), orb_w * orb_h * 2),
    )
    for path, size in specs:
        loaded = _preload_item(path, size)
        if loaded < 0:
            _map1_key = None
            print("MAP1_PRELOAD_FAIL")
            return False
        total += loaded
    _slice_player_frames(
        get_blob(getattr(config, "CAMERA_PLAYER_SPRITESHEET_PATH", ""), 128 * (player_h * 2) * 2),
        player_w,
        player_h,
    )
    anim_total = _preload_animation_sheets(config)
    if anim_total < 0:
        _map1_key = None
        print("MAP1_PRELOAD_FAIL")
        return False
    total += anim_total
    _map1_key = key
    if _verbose(config):
        print("MAP1_PRELOAD_READY bytes=%d" % total)
    return True


def preload_map2(config, screen_w=None, screen_h=None):
    global _map2_blobs, _map2_key
    if not bool(getattr(config, "MAP2_ENABLED", False)) or not bool(getattr(config, "MAP2_PRELOAD_ENABLED", True)):
        return False
    sw = int(screen_w if screen_w is not None else getattr(config, "SCREEN_W", 320))
    sh = int(screen_h if screen_h is not None else getattr(config, "SCREEN_H", 240))
    wall_w = int(getattr(config, "MAP2_WALL_W", 64))
    wall_h = int(getattr(config, "MAP2_WALL_H", sh))
    door_w = int(getattr(config, "MAP2_DOOR_W", 256))
    door_h = int(getattr(config, "MAP2_DOOR_H", 112))
    floor_w = int(getattr(config, "MAP2_FLOOR_W", 256))
    floor_h = int(getattr(config, "MAP2_FLOOR_H", 32))
    object_atlas_w = int(getattr(config, "MAP2_OBJECT_ATLAS_W", getattr(config, "OBJECTS_ATLAS_W", 0)))
    object_atlas_h = int(getattr(config, "MAP2_OBJECT_ATLAS_H", getattr(config, "OBJECTS_ATLAS_H", 0)))
    bow_sheet_w = int(getattr(config, "MAP2_FLOOR_BOW_SHEET_W", getattr(config, "ENEMY_SHEET_W", 0)))
    bow_sheet_h = int(getattr(config, "MAP2_FLOOR_BOW_SHEET_H", getattr(config, "ENEMY_SHEET_H", 0)))
    key = (sw, sh, wall_w, wall_h, door_w, door_h, floor_w, floor_h, object_atlas_w, object_atlas_h, bow_sheet_w, bow_sheet_h)
    if _map2_blobs is not None and _map2_key == key:
        return True
    far = _load_blob(getattr(config, "MAP2_FAR_RGB565_PATH", ""), sw * sh * 2)
    wall = _load_blob(getattr(config, "MAP2_WALL_RGB565_PATH", ""), wall_w * wall_h * 2)
    door = _load_blob(getattr(config, "MAP2_DOOR_RGB565_PATH", ""), door_w * door_h * 2)
    floor = _load_blob(getattr(config, "MAP2_FLOOR_RGB565_PATH", ""), floor_w * floor_h * 2)
    object_atlas = _load_blob(
        getattr(config, "MAP2_OBJECT_ATLAS_RGB565_PATH", getattr(config, "OBJECTS_ATLAS_RGB565_PATH", "")),
        object_atlas_w * object_atlas_h * 2,
    )
    bow_sheet = _load_blob(getattr(config, "MAP2_FLOOR_BOW_SHEET_RGB565_PATH", getattr(config, "ENEMY_SHEET_RGB565_PATH", "")), bow_sheet_w * bow_sheet_h * 2)
    if far is None or wall is None or door is None or floor is None or object_atlas is None or bow_sheet is None:
        _map2_blobs = None
        _map2_key = None
        print("MAP2_PRELOAD_FAIL")
        return False
    _map2_blobs = {
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
    }
    _map2_key = key
    if _verbose(config):
        print("MAP2_PRELOAD_READY bytes=%d" % (len(far) + len(wall) + len(door) + len(floor) + len(object_atlas)))
    return True


def get_map2_runtime(config, screen_w, screen_h):
    if not preload_map2(config, screen_w, screen_h):
        return None
    data = _map2_blobs
    return {
        "far": data["far"],
        "wall": data["wall"],
        "wall_w": data["wall_w"],
        "wall_h": data["wall_h"],
        "door": data["door"],
        "door_w": data["door_w"],
        "door_h": data["door_h"],
        "floor": data["floor"],
        "floor_w": data["floor_w"],
        "floor_h": data["floor_h"],
        "object_atlas": data["object_atlas"],
        "object_atlas_w": data["object_atlas_w"],
        "object_atlas_h": data["object_atlas_h"],
        "floor_bow_sheet": data["floor_bow_sheet"],
        "floor_bow_sheet_w": data["floor_bow_sheet_w"],
        "floor_bow_sheet_h": data["floor_bow_sheet_h"],
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
