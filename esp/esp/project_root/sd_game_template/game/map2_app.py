import config
import map2_elevator

try:
    import asset_cache
except Exception:
    asset_cache = None

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
    import lgfx as _lgfx
except Exception:
    _lgfx = None

try:
    from time import ticks_diff, ticks_ms, sleep_ms
except Exception:
    from time import sleep as _sleep
    import time as _time

    def ticks_ms():
        return int(_time.time() * 1000)

    def ticks_diff(a, b):
        return a - b

    def sleep_ms(ms):
        _sleep(ms / 1000)

try:
    from engine.input import InputSystem
except Exception:
    InputSystem = None

_boot_source_tag = "ROOT"
_stage_switch_from_previous = False
_joy_centers_from_previous = None


def _load_player_frames(sprite_w, sprite_h):
    if asset_cache is not None:
        try:
            frames = asset_cache.get_player_frames(sprite_w, sprite_h)
            if frames is not None:
                return frames
        except Exception:
            pass
    path = str(getattr(config, "CAMERA_PLAYER_SPRITESHEET_PATH", "/sd/game/picture/player/player_wire.rgb565"))
    sheet = None
    if asset_cache is not None:
        try:
            sheet = asset_cache.get_blob(path, 128 * (int(sprite_h) * 2) * 2)
        except Exception:
            sheet = None
    if sheet is None:
        with open(path, "rb") as fp:
            sheet = fp.read()
    sheet_w = 128
    frames_right = []
    frames_left = []
    for row, out in ((0, frames_right), (1, frames_left)):
        for col in range(4):
            buf = bytearray(sprite_w * sprite_h * 2)
            di = 0
            y = 0
            while y < sprite_h:
                src_y = row * sprite_h + y
                src_x = col * sprite_w
                off = ((src_y * sheet_w) + src_x) * 2
                end = off + sprite_w * 2
                buf[di:di + sprite_w * 2] = sheet[off:end]
                di += sprite_w * 2
                y += 1
            out.append(bytes(buf))
    return frames_right, frames_left


def run(max_frames=None):
    if _lgfx is None:
        raise RuntimeError("MAP2_FAIL_NO_LGFX")
    if InputSystem is None:
        raise RuntimeError("MAP2_FAIL_NO_INPUT")
    if not hasattr(_lgfx, "render_elevator_scene_bands_rgb565"):
        raise RuntimeError("MAP2_FAIL_NO_NATIVE_RENDER")

    print("APP_RUN_START_STAGE02_ELEVATOR")
    print("CAMERA_TEST_BOOT_SOURCE=%s" % _boot_source_tag)
    if not bool(_stage_switch_from_previous):
        _lgfx.init()
    try:
        _lgfx.rotation(1)
    except Exception:
        pass

    sw = int(config.SCREEN_W)
    sh = int(config.SCREEN_H)
    band_h = int(getattr(config, "CAMERA_BAND_PIPELINE_H", 48))
    if band_h < 1 or band_h > sh:
        band_h = 48
    if band_h > sh:
        band_h = sh
    scene_buf = bytearray(sw * band_h * 2)
    scene_buf_back = bytearray(sw * band_h * 2)
    runtime = map2_elevator.load_runtime(sw, sh)
    if runtime is None:
        raise RuntimeError("MAP2_FAIL_ASSET_LOAD")
    print("MAP2_ASSET_READY")

    player_w = int(getattr(config, "CAMERA_TEST_PLAYER_W", 12))
    player_h = int(getattr(config, "CAMERA_TEST_PLAYER_H", 16))
    sprite_w = int(getattr(config, "CAMERA_TEST_PLAYER_SPRITE_W", 32))
    sprite_h = int(getattr(config, "CAMERA_TEST_PLAYER_SPRITE_H", 32))
    draw_off_x = int(getattr(config, "PLAYER_DRAW_OFFSET_X", -((32 - player_w) // 2)))
    draw_off_y = int(getattr(config, "PLAYER_DRAW_OFFSET_Y", -(32 - player_h)))
    sprite_right, sprite_left = _load_player_frames(sprite_w, sprite_h)
    print("MAP2_PLAYER_SPRITE_READY")

    player_x, player_y, _camera_x, _vel_y = map2_elevator.enter(player_h)
    if _joy_centers_from_previous is not None:
        try:
            input_system = InputSystem(_joy_centers_from_previous[0], _joy_centers_from_previous[1])
        except Exception:
            input_system = InputSystem()
    else:
        input_system = InputSystem()
    if _joy_centers_from_previous is not None:
        try:
            input_system.set_joy_centers(_joy_centers_from_previous[0], _joy_centers_from_previous[1])
        except Exception:
            pass
    speed = int(getattr(config, "PLAYER_SPEED_X", 2))
    facing = 1
    anim_counter = 0
    anim_idx = 0
    frame = 0
    drew_once = False
    lever_a_latched = False
    tail_inflight = False
    tail_overlap_enabled = bool(getattr(config, "CAMERA_BAND_TAIL_OVERLAP_UPDATE", False)) and hasattr(_lgfx, "band_pipeline_tail_wait")
    if tail_overlap_enabled:
        try:
            _lgfx.band_pipeline_tail_wait()
        except Exception:
            tail_overlap_enabled = False
    last_tick = ticks_ms() - int(getattr(config, "FRAME_MS", 16))

    while True:
        now = ticks_ms()
        elapsed = ticks_diff(now, last_tick)
        if elapsed < config.FRAME_MS:
            sleep_ms(config.FRAME_MS - elapsed)
            continue
        last_tick = now
        input_system.update(now)
        input_lr = int(getattr(input_system, "joy_x_axis", 0))
        btn_a_down = bool(getattr(input_system, "btn_a_down", False))
        btn_b_down = bool(getattr(input_system, "btn_b_down", False))
        btn_y_down = bool(getattr(input_system, "btn_y_down", False))
        if frame < int(getattr(config, "MAP2_INPUT_SETTLE_FRAMES", 8)):
            input_lr = 0
            btn_a_pressed = False
            btn_b_down = False
            btn_y_down = False
            if not btn_a_down:
                lever_a_latched = False
        else:
            btn_a_pressed = bool(getattr(input_system, "btn_a_pressed", False))
            if btn_a_down:
                if not lever_a_latched:
                    btn_a_pressed = True
                    lever_a_latched = True
            else:
                lever_a_latched = False
        if input_lr > 20:
            facing = 1
        elif input_lr < -20:
            facing = -1
        player_x, player_y, anim_counter, anim_idx, tail_inflight = map2_elevator.step(
            _lgfx,
            scene_buf,
            scene_buf_back,
            sw,
            sh,
            band_h,
            runtime,
            input_lr,
            speed,
            player_x,
            player_w,
            player_h,
            btn_a_pressed,
            sprite_left,
            sprite_right,
            anim_counter,
            anim_idx,
            facing,
            sprite_w,
            sprite_h,
            draw_off_x,
            draw_off_y,
            tail_inflight,
            btn_b_down,
            btn_y_down,
            tail_overlap_enabled,
        )
        if int(runtime.get("map2_respawn_reset_latch", 0)):
            runtime["map2_respawn_reset_latch"] = 0
            lever_a_latched = False
            anim_counter = 0
            anim_idx = 0
            facing = 1
            frame = 0
        if not drew_once:
            print("MAP2_STAGE_DRAW_OK door_y=%d wall_scroll_y=%d lever_on=%d player_x=%d player_y=%d" % (int(runtime.get("door_y", 0) or 0), int(runtime.get("wall_scroll_y", 0) or 0), 1 if bool(runtime.get("lever_on", False)) else 0, int(player_x), int(player_y)))
            drew_once = True
        frame += 1
        if max_frames is not None and frame >= int(max_frames):
            break
    if tail_inflight and hasattr(_lgfx, "band_pipeline_tail_wait"):
        try:
            _lgfx.band_pipeline_tail_wait()
        except Exception:
            pass
