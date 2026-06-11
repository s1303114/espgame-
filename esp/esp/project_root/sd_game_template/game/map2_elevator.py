import config

try:
    import asset_cache
except Exception:
    asset_cache = None


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
    far = _load_blob(_resolve(getattr(config, "MAP2_FAR_RGB565_PATH", "")), screen_w * screen_h * 2)
    wall = _load_blob(_resolve(getattr(config, "MAP2_WALL_RGB565_PATH", "")), wall_w * wall_h * 2)
    door = _load_blob(_resolve(getattr(config, "MAP2_DOOR_RGB565_PATH", "")), door_w * door_h * 2)
    floor = _load_blob(_resolve(getattr(config, "MAP2_FLOOR_RGB565_PATH", "")), floor_w * floor_h * 2)
    object_atlas = _load_blob(
        _resolve(getattr(config, "MAP2_OBJECT_ATLAS_RGB565_PATH", getattr(config, "OBJECTS_ATLAS_RGB565_PATH", ""))),
        object_atlas_w * object_atlas_h * 2,
    )
    if far is None or wall is None or door is None or floor is None or object_atlas is None:
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


def enter(player_h):
    player_x = int(getattr(config, "MAP2_RESPAWN_X", getattr(config, "MAP2_PLAYER_START_X", 154)))
    default_y = int(getattr(config, "MAP2_PLAYER_START_Y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h)))
    player_y = int(getattr(config, "MAP2_RESPAWN_Y", default_y))
    return player_x, player_y, 0, 0


def _aabb_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def _reset_platforms(runtime):
    floor_y = int(getattr(config, "MAP2_FLOOR_Y", 208))
    runtime["floor_left_y"] = floor_y
    runtime["floor_right_y"] = floor_y
    runtime["player_platform_slot"] = 1
    runtime["player_airborne"] = False
    runtime["player_vel_y"] = 0


def _respawn_player(runtime, player_h):
    _reset_platforms(runtime)
    player_x = int(getattr(config, "MAP2_RESPAWN_X", getattr(config, "MAP2_PLAYER_START_X", 154)))
    player_y = int(getattr(config, "MAP2_RESPAWN_Y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h)))
    print("MAP2_PLAYER_FALL_DEATH")
    return player_x, player_y


def _runtime_int(runtime, key, default):
    value = runtime.get(key, default)
    if value is None:
        return int(default)
    return int(value)


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


def update(input_lr, speed, player_x, player_w, player_h, runtime, btn_a_pressed, screen_h=240):
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
            runtime["lever_on"] = True
            running = not bool(runtime.get("lever_running", False))
            runtime["lever_running"] = running
            print("MAP2_LEVER_%s x=%d y=%d" % ("RUN" if running else "STOP", int(player_x), int(player_y)))
    if bool(runtime.get("lever_running", False)):
        wall_h = int(runtime.get("wall_h", 240) or 240)
        scroll_y = int(runtime.get("wall_scroll_y", 0) or 0) + int(getattr(config, "MAP2_WALL_SCROLL_SPEED", 1))
        if wall_h > 0:
            scroll_y %= wall_h
        runtime["wall_scroll_y"] = scroll_y
        floor_y = int(getattr(config, "MAP2_FLOOR_Y", 208))
        floor_h = int(getattr(config, "MAP2_FLOOR_H", 32))
        platform_speed = int(getattr(config, "MAP2_FLOOR_PLATFORM_SPEED", 5))
        slot = current_slot if not airborne else -1
        left_y = _runtime_int(runtime, "floor_left_y", floor_y) + platform_speed
        if slot == 0 and left_y >= int(screen_h):
            return _respawn_player(runtime, player_h)
        if left_y > int(screen_h):
            left_y = -floor_h
        right_y = _runtime_int(runtime, "floor_right_y", floor_y) - platform_speed
        if slot == 2 and right_y < 0:
            return _respawn_player(runtime, player_h)
        if right_y + floor_h < 0:
            right_y = int(screen_h)
        runtime["floor_left_y"] = left_y
        runtime["floor_right_y"] = right_y
        if runtime.get("door_enabled", False):
            door_y = int(runtime.get("door_y", int(getattr(config, "MAP2_DOOR_START_Y", 128))) or 0)
            door_y += int(getattr(config, "MAP2_DOOR_SCROLL_SPEED", 1))
            runtime["door_y"] = door_y
            if door_y >= int(getattr(config, "SCREEN_H", 240)):
                runtime["door_enabled"] = False
        if not airborne:
            player_y = _current_platform_y(runtime, current_slot, player_h, screen_h)
            if player_y is None:
                runtime["player_airborne"] = True
                runtime["player_vel_y"] = 0
                airborne = True
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
    if int(player_y) > int(getattr(config, "MAP2_PLAYER_DEATH_Y", 272)):
        return _respawn_player(runtime, player_h)
    return player_x, player_y


def submit(lgfx, scene_buf, scene_buf_back, screen_w, screen_h, band_h, runtime, sprite_left, sprite_right, anim_idx, facing, sprite_w, sprite_h, player_x, draw_off_x, player_y, draw_off_y):
    spr_x = int(player_x) + int(draw_off_x)
    spr_y = int(player_y) + int(draw_off_y)
    spr_rgb = sprite_left[anim_idx] if int(facing) < 0 else sprite_right[anim_idx]
    player_key = _swap16(int(getattr(config, "CAMERA_PLAYER_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
    layer_key = _swap16(int(getattr(config, "MAP2_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
    lever_running = bool(runtime.get("lever_running", False))
    lever_src_x = int(getattr(config, "MAP2_LEVER_ON_SRC_X", 64) if lever_running else getattr(config, "MAP2_LEVER_OFF_SRC_X", 32))
    lever_src_y = int(getattr(config, "MAP2_LEVER_ON_SRC_Y", 138) if lever_running else getattr(config, "MAP2_LEVER_OFF_SRC_Y", 138))
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
        False,
    )


def step(lgfx, scene_buf, scene_buf_back, screen_w, screen_h, band_h, runtime, input_lr, speed, player_x, player_w, player_h, btn_a_pressed, sprite_left, sprite_right, anim_counter, anim_idx, facing, sprite_w, sprite_h, draw_off_x, draw_off_y, tail_inflight):
    player_x, player_y = update(input_lr, speed, player_x, player_w, player_h, runtime, btn_a_pressed, screen_h)
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
            pass
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
    )
    return player_x, player_y, anim_counter, anim_idx, False
