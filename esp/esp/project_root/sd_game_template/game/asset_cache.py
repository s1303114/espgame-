_map2_blobs = None
_map2_key = None


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
    if data is None or len(data) != int(exp_bytes):
        return None
    return data


def preload_map2(config, screen_w=None, screen_h=None):
    global _map2_blobs, _map2_key
    if not bool(getattr(config, "MAP2_ENABLED", False)):
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
    key = (sw, sh, wall_w, wall_h, door_w, door_h, floor_w, floor_h, object_atlas_w, object_atlas_h)
    if _map2_blobs is not None and _map2_key == key:
        return True
    far = _load_blob(_resolve(getattr(config, "MAP2_FAR_RGB565_PATH", "")), sw * sh * 2)
    wall = _load_blob(_resolve(getattr(config, "MAP2_WALL_RGB565_PATH", "")), wall_w * wall_h * 2)
    door = _load_blob(_resolve(getattr(config, "MAP2_DOOR_RGB565_PATH", "")), door_w * door_h * 2)
    floor = _load_blob(_resolve(getattr(config, "MAP2_FLOOR_RGB565_PATH", "")), floor_w * floor_h * 2)
    object_atlas = _load_blob(
        _resolve(getattr(config, "MAP2_OBJECT_ATLAS_RGB565_PATH", getattr(config, "OBJECTS_ATLAS_RGB565_PATH", ""))),
        object_atlas_w * object_atlas_h * 2,
    )
    if far is None or wall is None or door is None or floor is None or object_atlas is None:
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
    }
    _map2_key = key
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
        "wall_scroll_y": 0,
        "door_y": int(getattr(config, "MAP2_DOOR_START_Y", 128)),
        "door_enabled": True,
        "lever_on": False,
        "lever_running": False,
        "floor_left_y": int(getattr(config, "MAP2_FLOOR_Y", 208)),
        "floor_right_y": int(getattr(config, "MAP2_FLOOR_Y", 208)),
        "player_platform_slot": 1,
        "player_airborne": False,
        "player_vel_y": 0,
    }
