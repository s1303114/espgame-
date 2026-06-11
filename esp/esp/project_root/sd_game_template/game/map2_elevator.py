import config


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
    wall_w = int(getattr(config, "MAP2_WALL_W", 64))
    wall_h = int(getattr(config, "MAP2_WALL_H", screen_h))
    door_w = int(getattr(config, "MAP2_DOOR_W", 256))
    door_h = int(getattr(config, "MAP2_DOOR_H", 112))
    floor_w = int(getattr(config, "MAP2_FLOOR_W", 256))
    floor_h = int(getattr(config, "MAP2_FLOOR_H", 32))
    far = _load_blob(_resolve(getattr(config, "MAP2_FAR_RGB565_PATH", "")), screen_w * screen_h * 2)
    wall = _load_blob(_resolve(getattr(config, "MAP2_WALL_RGB565_PATH", "")), wall_w * wall_h * 2)
    door = _load_blob(_resolve(getattr(config, "MAP2_DOOR_RGB565_PATH", "")), door_w * door_h * 2)
    floor = _load_blob(_resolve(getattr(config, "MAP2_FLOOR_RGB565_PATH", "")), floor_w * floor_h * 2)
    if far is None or wall is None or door is None or floor is None:
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
        "wall_scroll_y": 0,
        "door_y": int(getattr(config, "MAP2_DOOR_START_Y", 128)),
        "door_enabled": True,
    }


def enter(player_h):
    player_x = int(getattr(config, "MAP2_PLAYER_START_X", 154))
    player_y = int(getattr(config, "MAP2_PLAYER_START_Y", int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h)))
    return player_x, player_y, 0, 0


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


def update(input_lr, speed, player_x, player_h, runtime):
    move_x = 0
    if input_lr > 20:
        move_x = speed
    elif input_lr < -20:
        move_x = -speed
    min_x = int(getattr(config, "MAP2_PLAYER_MIN_X", 32))
    max_x = int(getattr(config, "MAP2_PLAYER_MAX_X", 276))
    if max_x < min_x:
        max_x = min_x
    player_x = max(min_x, min(max_x, int(player_x) + int(move_x)))
    player_y = int(getattr(config, "MAP2_FLOOR_Y", 208)) - int(player_h)
    wall_h = int(runtime.get("wall_h", 240) or 240)
    scroll_y = int(runtime.get("wall_scroll_y", 0) or 0) + int(getattr(config, "MAP2_WALL_SCROLL_SPEED", 1))
    if wall_h > 0:
        scroll_y %= wall_h
    runtime["wall_scroll_y"] = scroll_y
    if runtime.get("door_enabled", False):
        door_y = int(runtime.get("door_y", int(getattr(config, "MAP2_DOOR_START_Y", 128))) or 0)
        door_y += int(getattr(config, "MAP2_DOOR_SCROLL_SPEED", 1))
        runtime["door_y"] = door_y
        if door_y >= int(getattr(config, "SCREEN_H", 240)):
            runtime["door_enabled"] = False
    return player_x, player_y


def submit(lgfx, scene_buf, scene_buf_back, screen_w, screen_h, band_h, runtime, sprite_left, sprite_right, anim_idx, facing, sprite_w, sprite_h, player_x, draw_off_x, player_y, draw_off_y):
    spr_x = int(player_x) + int(draw_off_x)
    spr_y = int(player_y) + int(draw_off_y)
    spr_rgb = sprite_left[anim_idx] if int(facing) < 0 else sprite_right[anim_idx]
    player_key = _swap16(int(getattr(config, "CAMERA_PLAYER_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
    layer_key = _swap16(int(getattr(config, "MAP2_COLORKEY_RGB565", 0xF81F)) & 0xFFFF)
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


def step(lgfx, scene_buf, scene_buf_back, screen_w, screen_h, band_h, runtime, input_lr, speed, player_x, player_h, sprite_left, sprite_right, anim_counter, anim_idx, facing, sprite_w, sprite_h, draw_off_x, draw_off_y, tail_inflight):
    player_x, player_y = update(input_lr, speed, player_x, player_h, runtime)
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
