import config

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


class _RendererFallback:
    __slots__ = ("stage",)

    def __init__(self):
        self.stage = None

    def set_stage(self, stage_data):
        self.stage = stage_data

    def init(self):
        return

    def clear_region(self, x, y, w, h, color):
        return

    def draw_tilemap(self, camera_x, camera_y):
        return

    def draw_player(self, player_obj):
        return

    def draw_enemy(self, enemy_obj):
        return

    def draw_bullet(self, bullet_obj):
        return

    def draw_entities(self, entities, count):
        return

    def draw_ui(self, game_state):
        return

    def present(self):
        return


class _FallbackPlayer:
    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "active",
        "swappable",
        "entity_type",
        "hitbox",
        "affected_by_gravity",
        "on_ground",
        "facing",
        "hp",
    )

    def __init__(self, x, y):
        self.x = int(x)
        self.y = int(y)
        self.vx = 0
        self.vy = 0
        self.active = True
        self.swappable = False
        self.entity_type = "player"
        self.hitbox = [0, 0, 12, 16]
        self.affected_by_gravity = True
        self.on_ground = False
        self.facing = 1
        self.hp = 5

    def apply_input(self, x_axis):
        if x_axis > 20:
            self.vx = config.PLAYER_SPEED_X
            self.facing = 1
        elif x_axis < -20:
            self.vx = -config.PLAYER_SPEED_X
            self.facing = -1
        else:
            self.vx = 0


class BulletPool:
    __slots__ = ("size", "spawn_requests", "spawn_success", "reuse_count", "active_count_peak")

    def __init__(self, size, max_frames=24):
        self.size = int(size)
        self.spawn_requests = 0
        self.spawn_success = 0
        self.reuse_count = 0
        self.active_count_peak = 0

    def spawn(self, x, y, vx, vy):
        self.spawn_requests += 1
        return None

    def update_all(self, now_ms, stage_data):
        return

    def draw_all(self, renderer_mod):
        return

    def has_reuse(self):
        return False


class EntityManager:
    __slots__ = ()

    def __init__(self, max_entities):
        pass


class Entity:
    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "active",
        "visible",
        "swappable",
        "entity_type",
        "hitbox",
        "affected_by_gravity",
        "on_ground",
    )

    def __init__(self, x=0, y=0, w=8, h=8, entity_type="entity"):
        self.x = int(x)
        self.y = int(y)
        self.vx = 0
        self.vy = 0
        self.active = True
        self.visible = True
        self.swappable = True
        self.entity_type = entity_type
        self.hitbox = [0, 0, int(w), int(h)]
        self.affected_by_gravity = True
        self.on_ground = False

    def update(self, now_ms, stage_data, bullet_pool=None):
        return


def _fallback_create_player(x, y):
    return _FallbackPlayer(x, y)


def _fallback_create_enemy_basic(x, y, patrol_w=32, patrol_speed=1):
    return None


def _fallback_create_enemy_shooter(x, y, interval_frames=24, facing=-1, bullet_speed=4):
    return None


def _fallback_load_phase5_test_stage():
    width = 20
    height = 15
    tile_size = int(config.TILE_SIZE)
    tiles = []
    y = 0
    while y < height:
        tiles.append([0] * width)
        y += 1
    x = 0
    while x < width:
        tiles[height - 1][x] = 1
        x += 1
    return {
        "width": width,
        "height": height,
        "tile_size": tile_size,
        "tile_layers": [tiles],
        "solid_tiles": [1],
        "player_spawn": {"x": 32, "y": (height - 2) * tile_size},
    }


def _fallback_step_entity(entity, stage_data):
    if entity is None or (not getattr(entity, "active", False)):
        return None
    if hasattr(entity, "x") and hasattr(entity, "vx"):
        entity.x = int(entity.x) + int(entity.vx)
    if hasattr(entity, "y") and hasattr(entity, "vy"):
        entity.y = int(entity.y) + int(entity.vy)
    return None


renderer = _RendererFallback()
load_phase5_test_stage = _fallback_load_phase5_test_stage
step_entity = _fallback_step_entity
create_player = _fallback_create_player
create_enemy_basic = _fallback_create_enemy_basic
create_enemy_shooter = _fallback_create_enemy_shooter
skills = None
ui = None
save_system = None


def _ensure_renderer_loaded():
    global renderer
    if renderer is not None and (not isinstance(renderer, _RendererFallback)):
        return
    try:
        from engine import renderer as _renderer

        renderer = _renderer
    except Exception:
        renderer = _RendererFallback()


def _ensure_phase5_loader_loaded():
    global load_phase5_test_stage
    if load_phase5_test_stage is not None and load_phase5_test_stage is not _fallback_load_phase5_test_stage:
        return
    try:
        from engine.map_loader import load_phase5_test_stage as _loader

        load_phase5_test_stage = _loader
    except Exception:
        load_phase5_test_stage = _fallback_load_phase5_test_stage


def _ensure_step_entity_loaded():
    global step_entity
    if step_entity is not None and step_entity is not _fallback_step_entity:
        return
    try:
        from engine.physics import step_entity as _step

        step_entity = _step
    except Exception:
        step_entity = _fallback_step_entity


def _ensure_player_loaded():
    global create_player
    if create_player is not None and create_player is not _fallback_create_player:
        return
    try:
        from actors.player import create_player as _create_player

        create_player = _create_player
    except Exception:
        create_player = _fallback_create_player


def _ensure_enemy_loaded():
    global create_enemy_basic, create_enemy_shooter, BulletPool
    if create_enemy_basic is _fallback_create_enemy_basic:
        try:
            from actors.enemy_basic import create_enemy_basic as _create_enemy_basic

            create_enemy_basic = _create_enemy_basic
        except Exception:
            create_enemy_basic = _fallback_create_enemy_basic
    if create_enemy_shooter is _fallback_create_enemy_shooter:
        try:
            from actors.enemy_shooter import create_enemy_shooter as _create_enemy_shooter

            create_enemy_shooter = _create_enemy_shooter
        except Exception:
            create_enemy_shooter = _fallback_create_enemy_shooter
    if BulletPool.__module__ == __name__:
        try:
            from actors.bullet import BulletPool as _BulletPool

            BulletPool = _BulletPool
        except Exception:
            pass


def _ensure_entity_manager_loaded():
    global EntityManager, Entity
    if EntityManager.__module__ == __name__:
        try:
            from engine.entity_manager import EntityManager as _EntityManager

            EntityManager = _EntityManager
        except Exception:
            pass
    if Entity.__module__ == __name__:
        try:
            from engine.entity import Entity as _Entity

            Entity = _Entity
        except Exception:
            pass


def _ensure_skills_loaded():
    global skills
    if skills is not None:
        return
    try:
        from engine import skills as _skills

        skills = _skills
    except Exception:
        skills = None


def _ensure_ui_loaded():
    global ui
    if ui is not None:
        return
    try:
        from engine import ui as _ui

        ui = _ui
    except Exception:
        ui = None


def _ensure_save_system_loaded():
    global save_system
    if save_system is not None:
        return
    try:
        from engine import save_system as _save_system

        save_system = _save_system
    except Exception:
        save_system = None


def _ensure_phase_dependencies(stage):
    _ensure_renderer_loaded()
    _ensure_player_loaded()
    _ensure_step_entity_loaded()

    if stage == "PHASE5":
        _ensure_phase5_loader_loaded()
        return

    _ensure_enemy_loaded()
    _ensure_entity_manager_loaded()

    if stage == "PHASE7" or stage == "PHASE8":
        _ensure_skills_loaded()

    if stage == "PHASE8":
        _ensure_ui_loaded()
        _ensure_save_system_loaded()

_boot_source_tag = "UNKNOWN"


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _scripted_x_axis(frame_index):
    if frame_index < 20:
        return 0
    if frame_index < 90:
        return 80
    if frame_index < 160:
        return -80
    return 0


def _scripted_x_axis_phase6(frame_index):
    if frame_index < 20:
        return 0
    if frame_index < 70:
        return 70
    if frame_index < 120:
        return -70
    if frame_index < 160:
        return 70
    return 0


def _select_phase_stage():
    stage = str(getattr(config, "PHASE_ACCEPTANCE_STAGE", "PHASE8")).upper()
    if stage == "PHASE8":
        return "PHASE8"
    if stage == "PHASE7":
        return "PHASE7"
    if stage == "PHASE5":
        return "PHASE5"
    return "PHASE6"


def _select_phase6_mode(max_frames):
    configured = str(getattr(config, "PHASE6_ACCEPTANCE_MODE", "AUTO")).upper()
    if configured in ("DRAW_MIN", "MIN_DRAW", "DRAW_ONLY"):
        return "DRAW_MIN"
    if configured == "MANUAL":
        return "MANUAL"
    if configured == "TEST":
        return "TEST"
    return "TEST" if max_frames is not None else "MANUAL"


def _select_phase7_mode(max_frames):
    configured = str(getattr(config, "PHASE7_ACCEPTANCE_MODE", "AUTO")).upper()
    if configured == "MANUAL":
        return "MANUAL"
    if configured == "TEST":
        return "TEST"
    return "TEST" if max_frames is not None else "MANUAL"


def _select_phase8_mode(max_frames):
    configured = str(getattr(config, "PHASE8_ACCEPTANCE_MODE", "AUTO")).upper()
    if configured == "MANUAL":
        return "MANUAL"
    if configured == "TEST":
        return "TEST"
    return "TEST" if max_frames is not None else "MANUAL"


def _load_phase6_test_stage():
    width = 20
    height = 15
    tile_size = int(config.TILE_SIZE)

    tiles = []
    y = 0
    while y < height:
        tiles.append([0] * width)
        y += 1

    # Minimal deterministic scene: single ground row + one wall.
    x = 0
    while x < width:
        tiles[height - 1][x] = 1
        x += 1

    y = 10
    while y <= 13:
        tiles[y][11] = 1
        y += 1

    floor_y = (height - 1) * tile_size
    spawn_y = floor_y - 16

    return {
        "width": width,
        "height": height,
        "tile_size": tile_size,
        "tile_layers": [tiles],
        "solid_tiles": [1],
        "player_spawn": {
            "x": 2 * tile_size,
            "y": spawn_y,
        },
        "enemy_spawns": [
            {
                "type": "enemy_basic",
                "x": 7 * tile_size,
                "y": spawn_y,
                "patrol_w": 24,
                "patrol_speed": 1,
            },
            {
                "type": "enemy_shooter",
                "x": 14 * tile_size,
                "y": spawn_y,
                "facing": -1,
                "interval_frames": int(getattr(config, "PHASE6_SHOOTER_INTERVAL_FRAMES", 12)),
                "bullet_speed": int(getattr(config, "PHASE6_BULLET_SPEED", 4)),
            },
        ],
        "stage_goal": {
            "x": 0,
            "y": 0,
            "w": 0,
            "h": 0,
        },
    }


def _load_phase7_test_stage(mode):
    width = 20
    height = 15
    tile_size = int(config.TILE_SIZE)

    tiles = []
    y = 0
    while y < height:
        tiles.append([0] * width)
        y += 1

    x = 0
    while x < width:
        tiles[height - 1][x] = 1
        x += 1

    y = 10
    while y <= 13:
        tiles[y][11] = 1
        y += 1

    floor_y = (height - 1) * tile_size
    spawn_y = floor_y - 16

    if mode == "TEST":
        shooter_interval = int(getattr(config, "PHASE7_TEST_SHOOTER_INTERVAL_FRAMES", 600))
    else:
        shooter_interval = int(getattr(config, "PHASE7_SHOOTER_INTERVAL_FRAMES", 12))

    return {
        "width": width,
        "height": height,
        "tile_size": tile_size,
        "tile_layers": [tiles],
        "solid_tiles": [1],
        "player_spawn": {
            "x": 2 * tile_size,
            "y": spawn_y,
        },
        "enemy_spawns": [
            {
                "type": "enemy_basic",
                "x": 6 * tile_size,
                "y": spawn_y,
                "patrol_w": 24,
                "patrol_speed": 1,
            },
            {
                "type": "enemy_shooter",
                "x": 14 * tile_size,
                "y": spawn_y,
                "facing": -1,
                "interval_frames": shooter_interval,
                "bullet_speed": int(getattr(config, "PHASE6_BULLET_SPEED", 4)),
            },
        ],
        "phase7_air_dummy": {
            "x": 10 * tile_size,
            "y": spawn_y - (4 * tile_size),
            "w": 12,
            "h": 16,
        },
        "stage_goal": {
            "x": 0,
            "y": 0,
            "w": 0,
            "h": 0,
        },
    }


def _load_phase8_test_stage(mode):
    # Phase 8 keeps gameplay baseline from Phase 7 and focuses on HUD/save/startup.
    return _load_phase7_test_stage(mode)


def _select_phase5_mode(max_frames):
    configured = str(getattr(config, "PHASE5_ACCEPTANCE_MODE", "AUTO")).upper()

    if configured in ("LEFT_EDGE_STATIC", "LEFT_EDGE", "EDGE_STATIC"):
        return "LEFT_EDGE_STATIC"
    if configured == "MANUAL":
        return "MANUAL"
    if configured == "TEST":
        return "TEST"
    return "TEST" if max_frames is not None else "MANUAL"


def _run_left_edge_static_test(max_frames):
    if not hasattr(_lgfx, "fill_rect"):
        raise RuntimeError("PHASE5_EDGE_FAIL_NO_FILL_RECT")

    print("PHASE5_LEFT_EDGE_STATIC_MODE")

    renderer.init()
    renderer.clear_region(0, 0, config.SCREEN_W, config.SCREEN_H, config.COLOR_BG)

    block_w = int(getattr(config, "PHASE5_LEFT_EDGE_BLOCK_W", 16))
    block_h = int(getattr(config, "PHASE5_LEFT_EDGE_BLOCK_H", 16))
    block_y = int(getattr(config, "PHASE5_LEFT_EDGE_BLOCK_Y", 72))

    # A/B/C are fixed reference blocks for left-edge clipping diagnosis.
    _lgfx.fill_rect(0, block_y, block_w, block_h, 0xF800)
    _lgfx.fill_rect(4, block_y + block_h + 8, block_w, block_h, 0x07E0)
    _lgfx.fill_rect(8, block_y + (block_h + 8) * 2, block_w, block_h, 0x001F)
    renderer.present()

    print("PHASE5_LEFT_EDGE_BLOCK_A_X=0")
    print("PHASE5_LEFT_EDGE_BLOCK_B_X=4")
    print("PHASE5_LEFT_EDGE_BLOCK_C_X=8")

    if max_frames is None:
        frame_limit = int(getattr(config, "PHASE5_LEFT_EDGE_TEST_FRAMES", 900))
    else:
        frame_limit = int(max_frames)

    if frame_limit < 1:
        frame_limit = 1

    last_tick = ticks_ms()
    frames = 0
    while frames < frame_limit:
        now = ticks_ms()
        elapsed = ticks_diff(now, last_tick)
        if elapsed < config.FRAME_MS:
            sleep_ms(config.FRAME_MS - elapsed)
            continue
        last_tick = now
        frames += 1

    print("PHASE5_LEFT_EDGE_STATIC_DONE")


def _draw_stage_region(stage, x, y, w, h):
    if _lgfx is None or not hasattr(_lgfx, "fill_rect"):
        return False

    x = int(x)
    y = int(y)
    w = int(w)
    h = int(h)
    if w <= 0 or h <= 0:
        return True

    x0 = _clamp(x, 0, config.SCREEN_W)
    y0 = _clamp(y, 0, config.SCREEN_H)
    x1 = _clamp(x + w, 0, config.SCREEN_W)
    y1 = _clamp(y + h, 0, config.SCREEN_H)
    if x1 <= x0 or y1 <= y0:
        return True

    rw = x1 - x0
    rh = y1 - y0
    _lgfx.fill_rect(x0, y0, rw, rh, config.COLOR_BG)

    layers = stage.get("tile_layers", [])
    if not layers:
        return True

    tiles = layers[0]
    tile_size = int(stage.get("tile_size", config.TILE_SIZE))
    world_w = int(stage.get("width", 0))
    world_h = int(stage.get("height", 0))

    tx0 = _clamp(x0 // tile_size, 0, world_w - 1)
    ty0 = _clamp(y0 // tile_size, 0, world_h - 1)
    tx1 = _clamp((x1 - 1) // tile_size, 0, world_w - 1)
    ty1 = _clamp((y1 - 1) // tile_size, 0, world_h - 1)

    ty = ty0
    while ty <= ty1:
        row = tiles[ty]
        py = ty * tile_size
        tx = tx0
        while tx <= tx1:
            px = tx * tile_size
            cx0 = px if px > x0 else x0
            cy0 = py if py > y0 else y0
            cx1 = (px + tile_size) if (px + tile_size) < x1 else x1
            cy1 = (py + tile_size) if (py + tile_size) < y1 else y1
            cw = cx1 - cx0
            ch = cy1 - cy0
            if cw > 0 and ch > 0 and row[tx] != 0:
                _lgfx.fill_rect(cx0, cy0, cw, ch, config.COLOR_TILE_SOLID)
            tx += 1
        ty += 1
    return True


def _rect_union(x0, y0, w0, h0, x1, y1, w1, h1):
    # Convert both rectangles to inclusive bounds first to avoid off-by-one drift.
    a_l = int(x0)
    a_t = int(y0)
    a_r = a_l + int(w0) - 1
    a_b = a_t + int(h0) - 1

    b_l = int(x1)
    b_t = int(y1)
    b_r = b_l + int(w1) - 1
    b_b = b_t + int(h1) - 1

    u_l = a_l if a_l < b_l else b_l
    u_t = a_t if a_t < b_t else b_t
    u_r = a_r if a_r > b_r else b_r
    u_b = a_b if a_b > b_b else b_b
    return u_l, u_t, (u_r - u_l + 1), (u_b - u_t + 1)


def _clip_rect_screen(x, y, w, h):
    x0 = _clamp(int(x), 0, config.SCREEN_W)
    y0 = _clamp(int(y), 0, config.SCREEN_H)
    x1 = _clamp(int(x + w), 0, config.SCREEN_W)
    y1 = _clamp(int(y + h), 0, config.SCREEN_H)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, (x1 - x0), (y1 - y0)


def _fill_buffer_color565(buf, pixel_count, color):
    lo = int(color) & 0xFF
    hi = (int(color) >> 8) & 0xFF
    i = 0
    idx = 0
    while i < pixel_count:
        buf[idx] = lo
        buf[idx + 1] = hi
        idx += 2
        i += 1


def _fill_buffer_rect565(buf, buf_w, x, y, w, h, color):
    lo = int(color) & 0xFF
    hi = (int(color) >> 8) & 0xFF
    row = 0
    while row < h:
        base = ((y + row) * buf_w + x) * 2
        col = 0
        while col < w:
            pos = base + (col * 2)
            buf[pos] = lo
            buf[pos + 1] = hi
            col += 1
        row += 1


def _compose_stage_tiles_buffer(stage, ux, uy, uw, uh, buf):
    layers = stage.get("tile_layers", [])
    world_w = int(stage.get("width", 0))
    world_h = int(stage.get("height", 0))
    tile_size = int(stage.get("tile_size", config.TILE_SIZE))

    if layers and world_w > 0 and world_h > 0:
        tiles = layers[0]
        tx0 = ux // tile_size
        ty0 = uy // tile_size
        tx1 = (ux + uw - 1) // tile_size
        ty1 = (uy + uh - 1) // tile_size

        if not (tx1 < 0 or ty1 < 0 or tx0 >= world_w or ty0 >= world_h):
            if tx0 < 0:
                tx0 = 0
            if ty0 < 0:
                ty0 = 0
            if tx1 >= world_w:
                tx1 = world_w - 1
            if ty1 >= world_h:
                ty1 = world_h - 1

            ty = ty0
            while ty <= ty1:
                row = tiles[ty]
                tile_y0 = ty * tile_size
                tile_y1 = tile_y0 + tile_size
                draw_y0 = tile_y0 if tile_y0 > uy else uy
                draw_y1 = tile_y1 if tile_y1 < (uy + uh) else (uy + uh)
                if draw_y1 > draw_y0:
                    tx = tx0
                    while tx <= tx1:
                        if row[tx] != 0:
                            tile_x0 = tx * tile_size
                            tile_x1 = tile_x0 + tile_size
                            draw_x0 = tile_x0 if tile_x0 > ux else ux
                            draw_x1 = tile_x1 if tile_x1 < (ux + uw) else (ux + uw)
                            if draw_x1 > draw_x0:
                                _fill_buffer_rect565(
                                    buf,
                                    uw,
                                    draw_x0 - ux,
                                    draw_y0 - uy,
                                    draw_x1 - draw_x0,
                                    draw_y1 - draw_y0,
                                    config.COLOR_TILE_SOLID,
                                )
                        tx += 1
                ty += 1


def _compose_rects_buffer(ux, uy, uw, uh, rects, buf):
    i = 0
    while i < len(rects):
        rx, ry, rw, rh, color = rects[i]
        x0 = rx if rx > ux else ux
        y0 = ry if ry > uy else uy
        x1 = (rx + rw) if (rx + rw) < (ux + uw) else (ux + uw)
        y1 = (ry + rh) if (ry + rh) < (uy + uh) else (uy + uh)
        if x1 > x0 and y1 > y0:
            _fill_buffer_rect565(
                buf,
                uw,
                x0 - ux,
                y0 - uy,
                x1 - x0,
                y1 - y0,
                color,
            )
        i += 1


def _compose_union_buffer(stage, ux, uy, uw, uh, player_x, player_y, pw, ph, buf):
    _fill_buffer_color565(buf, uw * uh, config.COLOR_BG)
    _compose_stage_tiles_buffer(stage, ux, uy, uw, uh, buf)
    _compose_rects_buffer(
        ux,
        uy,
        uw,
        uh,
        [(player_x, player_y, pw, ph, config.COLOR_PLAYER)],
        buf,
    )


def _compose_phase6_union_buffer(stage, ux, uy, uw, uh, drawables, buf):
    _fill_buffer_color565(buf, uw * uh, config.COLOR_BG)
    _compose_stage_tiles_buffer(stage, ux, uy, uw, uh, buf)
    _compose_rects_buffer(ux, uy, uw, uh, drawables, buf)


class _RectScratch:
    __slots__ = ("buf", "size")

    def __init__(self):
        self.buf = None
        self.size = 0

    def ensure(self, need_bytes):
        if self.buf is None or self.size < need_bytes:
            self.buf = bytearray(need_bytes)
            self.size = need_bytes


def _draw_rect_to_buffer(buf, buf_w, clip_x, clip_y, rx, ry, rw, rh, color):
    x0 = rx if rx > clip_x else clip_x
    y0 = ry if ry > clip_y else clip_y
    x1 = (rx + rw) if (rx + rw) < (clip_x + buf_w) else (clip_x + buf_w)
    y1 = (ry + rh) if (ry + rh) < (clip_y + ((len(buf) // 2) // buf_w)) else (clip_y + ((len(buf) // 2) // buf_w))

    if x1 > x0 and y1 > y0:
        _fill_buffer_rect565(
            buf,
            buf_w,
            x0 - clip_x,
            y0 - clip_y,
            x1 - x0,
            y1 - y0,
            color,
        )


def _compose_diag_scene(buf, clip_x, clip_y, clip_w, clip_h, bg_color, rects):
    _fill_buffer_color565(buf, clip_w * clip_h, bg_color)
    i = 0
    while i < len(rects):
        r = rects[i]
        _draw_rect_to_buffer(buf, clip_w, clip_x, clip_y, r[0], r[1], r[2], r[3], r[4])
        i += 1


def _diag_blit_rect(scratch, x, y, w, h, bg_color, rects):
    clipped = _clip_rect_screen(x, y, w, h)
    if clipped is None:
        return

    cx, cy, cw, ch = clipped
    need = cw * ch * 2
    scratch.ensure(need)
    view = memoryview(scratch.buf)[:need]
    _compose_diag_scene(view, cx, cy, cw, ch, bg_color, rects)
    _lgfx.blit_rect565(cx, cy, cw, ch, view)


def _diag_wait_next_frame(last_tick):
    while True:
        now = ticks_ms()
        elapsed = ticks_diff(now, last_tick)
        if elapsed >= config.FRAME_MS:
            return now
        sleep_ms(config.FRAME_MS - elapsed)


def _diag_clear_screen():
    renderer.clear_region(0, 0, config.SCREEN_W, config.SCREEN_H, config.COLOR_BG)
    renderer.present()


def _run_blit_diagnostics(mode, max_frames):
    if _lgfx is None or not hasattr(_lgfx, "blit_rect565"):
        raise RuntimeError("PHASE5_DIAG_FAIL_NO_BLIT")

    print("PHASE5_BLIT_DIAG_MODE")
    renderer.init()
    _diag_clear_screen()

    scratch = _RectScratch()
    last_tick = ticks_ms()

    run_t1 = mode in ("DIAG", "DIAG1")
    run_t2 = mode in ("DIAG", "DIAG2")
    run_t3 = mode in ("DIAG", "DIAG3")

    # Test 1: static 2x2 color-order patch.
    if run_t1:
        print("PHASE5_BLIT_TEST1_START")
        print("PHASE5_BLIT_TEST1_EXPECT=TL_RED,TR_GREEN,BL_BLUE,BR_WHITE")

        _diag_clear_screen()

        cell = 24
        tx = 24
        ty = 24
        tw = cell * 2
        th = cell * 2
        rects = [
            (tx, ty, cell, cell, 0xF800),
            (tx + cell, ty, cell, cell, 0x07E0),
            (tx, ty + cell, cell, cell, 0x001F),
            (tx + cell, ty + cell, cell, cell, 0xFFFF),
        ]
        _diag_blit_rect(scratch, tx, ty, tw, th, config.COLOR_BG, rects)

        hold = 90
        i = 0
        while i < hold:
            last_tick = _diag_wait_next_frame(last_tick)
            i += 1

        print("PHASE5_BLIT_TEST1_DONE")

    # Test 2: moving solid green block on plain black background.
    if run_t2:
        print("PHASE5_BLIT_TEST2_START")
        print("PHASE5_BLIT_TEST2_EXPECT=GREEN_STABLE_NO_INTERNAL_BLACK_DIAGONAL")

        _diag_clear_screen()

        bw = 30
        bh = 20
        bx = 16
        by = 90
        vx = 3

        frames = 220 if max_frames is None else max(120, int(max_frames) // 2)
        i = 0
        while i < frames:
            last_tick = _diag_wait_next_frame(last_tick)

            old_x = bx
            old_y = by

            bx += vx
            if bx < 8:
                bx = 8
                vx = 3
            if bx + bw > config.SCREEN_W - 8:
                bx = config.SCREEN_W - 8 - bw
                vx = -3

            ux, uy, uw, uh = _rect_union(old_x, old_y, bw, bh, bx, by, bw, bh)
            rects = [(bx, by, bw, bh, 0x07E0)]
            _diag_blit_rect(scratch, ux, uy, uw, uh, config.COLOR_BG, rects)

            i += 1

        print("PHASE5_BLIT_TEST2_DONE")

    # Test 3: moving green block over static gray platform (controlled no physics).
    if run_t3:
        print("PHASE5_BLIT_TEST3_START")
        print("PHASE5_BLIT_TEST3_EXPECT=NO_WHITE_DOT_PLATFORM_CORNER")

        _diag_clear_screen()

        platform = (40, 160, 240, 20, 0x7BEF)
        bw = 30
        bh = 20
        bx = 56
        by = 96

        # Draw only minimal baseline bounds (avoid large temporary buffer).
        base_x = platform[0] if platform[0] < bx else bx
        base_y = platform[1] if platform[1] < by else by
        p_right = platform[0] + platform[2]
        b_right = bx + bw
        p_bottom = platform[1] + platform[3]
        b_bottom = by + bh
        base_w = (p_right if p_right > b_right else b_right) - base_x
        base_h = (p_bottom if p_bottom > b_bottom else b_bottom) - base_y

        _diag_blit_rect(
            scratch,
            base_x,
            base_y,
            base_w,
            base_h,
            config.COLOR_BG,
            [platform, (bx, by, bw, bh, 0x07E0)],
        )

        frames = 240 if max_frames is None else max(140, int(max_frames) // 2)
        i = 0
        while i < frames:
            last_tick = _diag_wait_next_frame(last_tick)

            old_x = bx
            old_y = by

            if i < 70:
                bx += 2
            elif i < 120:
                by += 2
            else:
                if i % 20 < 10:
                    bx += 1
                else:
                    bx -= 1

            top_y = platform[1] - bh
            if by > top_y:
                by = top_y

            if bx < 40:
                bx = 40
            if bx + bw > 280:
                bx = 280 - bw

            ux, uy, uw, uh = _rect_union(old_x, old_y, bw, bh, bx, by, bw, bh)
            rects = [platform, (bx, by, bw, bh, 0x07E0)]
            _diag_blit_rect(scratch, ux, uy, uw, uh, config.COLOR_BG, rects)

            i += 1

        print("PHASE5_BLIT_TEST3_DONE")

    print("PHASE5_BLIT_DIAG_DONE")


def _entity_draw_rect(ent):
    hb = ent.hitbox
    return (
        int(ent.x + hb[0]),
        int(ent.y + hb[1]),
        int(hb[2]),
        int(hb[3]),
    )


def _merge_dirty_rect(rect0, rect1):
    if rect1 is None:
        return rect0

    x1, y1, w1, h1 = rect1
    if w1 <= 0 or h1 <= 0:
        return rect0

    if rect0 is None:
        return int(x1), int(y1), int(w1), int(h1)

    x0, y0, w0, h0 = rect0
    return _rect_union(x0, y0, w0, h0, x1, y1, w1, h1)


def _expand_rect(rect, pad):
    if rect is None:
        return None

    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None

    p = int(pad)
    if p <= 0:
        return int(x), int(y), int(w), int(h)

    return int(x - p), int(y - p), int(w + (p * 2)), int(h + (p * 2))


def _compute_dirty_from_rect_maps(prev_rects, current_rects):
    dirty = None

    for key in current_rects:
        new_rect = current_rects[key]
        old_rect = prev_rects.get(key)
        if old_rect is None:
            dirty = _merge_dirty_rect(dirty, new_rect)
        elif old_rect != new_rect:
            dirty = _merge_dirty_rect(
                dirty,
                _rect_union(
                    old_rect[0],
                    old_rect[1],
                    old_rect[2],
                    old_rect[3],
                    new_rect[0],
                    new_rect[1],
                    new_rect[2],
                    new_rect[3],
                ),
            )

    for key in prev_rects:
        if key not in current_rects:
            dirty = _merge_dirty_rect(dirty, prev_rects[key])

    return dirty


def _aabb_overlap(a, b):
    return not (
        (a[0] + a[2]) <= b[0]
        or (b[0] + b[2]) <= a[0]
        or (a[1] + a[3]) <= b[1]
        or (b[1] + b[3]) <= a[1]
    )


class _Phase8Runtime:
    __slots__ = (
        "mode",
        "stage",
        "player",
        "input_system",
        "manager",
        "bullet_pool",
        "frame",
        "draw_count",
        "drawn_once",
        "prev_world_rects",
        "prev_hud_rects",
        "collision_dirty_region",
        "swap_dirty_region",
        "backbuffer",
        "backbuffer_bytes",
        "backbuffer_alt",
        "backbuffer_alt_bytes",
        "submit_violation",
        "ui_dirty_violation",
        "composed_drawables",
        "hud_drawables",
        "hud_rects",
        "target_buffer",
        "save_status",
        "save_status_ttl_frames",
        "save_status_ttl_default",
        "debug_enabled",
        "fps_estimate",
        "last_update_ms",
        "debug_line_interval",
        "ui_ok",
        "save_ok",
        "draw_ok",
        "save_boot_ok",
        "save_written",
        "save_loaded",
        "save_fallback_ok",
        "current_stage",
        "highest_stage",
        "prev_btn_a_down",
        "prev_btn_y_down",
        "draw_trace_frames",
        "draw_smoke_enabled",
        "draw_smoke_fill_done",
        "draw_smoke_rect_done",
    )

    def __init__(self, mode):
        self.mode = mode
        self.stage = _load_phase8_test_stage(mode)

        self.input_system = None
        if self.mode == "MANUAL":
            try:
                from engine.input import InputSystem

                self.input_system = InputSystem()
            except Exception:
                self.input_system = None

        spawn = self.stage.get("player_spawn", {"x": 32, "y": 32})
        self.player = create_player(int(spawn.get("x", 32)), int(spawn.get("y", 32)))

        max_entities = int(getattr(config, "MAX_ENTITIES", 32))
        self.manager = EntityManager(max_entities)

        pool_size = int(getattr(config, "PHASE6_BULLET_POOL_SIZE", 6))
        max_frames = int(getattr(config, "PHASE6_BULLET_MAX_FRAMES", 24))
        self.bullet_pool = BulletPool(pool_size, max_frames=max_frames)
        if hasattr(self.manager, "set_bullet_pool"):
            self.manager.set_bullet_pool(self.bullet_pool)

        self._spawn_enemies()

        self.frame = 0
        self.draw_count = 0
        self.drawn_once = False
        self.prev_world_rects = {}
        self.prev_hud_rects = {}
        self.collision_dirty_region = None
        self.swap_dirty_region = None
        self.backbuffer = None
        self.backbuffer_bytes = 0
        self.backbuffer_alt = None
        self.backbuffer_alt_bytes = 0
        self.submit_violation = False
        self.ui_dirty_violation = False
        self.composed_drawables = []

        self.hud_drawables = []
        self.hud_rects = {}
        self.target_buffer = []

        self.save_status = "neutral"
        self.save_status_ttl_frames = 0
        self.save_status_ttl_default = int(getattr(config, "PHASE8_SAVE_STATUS_TTL_FRAMES", 45))
        if self.save_status_ttl_default < 30:
            self.save_status_ttl_default = 30
        if self.save_status_ttl_default > 60:
            self.save_status_ttl_default = 60

        self.debug_enabled = False
        self.fps_estimate = 0
        self.last_update_ms = 0
        self.debug_line_interval = 15

        self.ui_ok = False
        self.save_ok = False
        self.draw_ok = False
        self.save_boot_ok = False
        self.save_written = False
        self.save_loaded = False
        self.save_fallback_ok = False

        self.current_stage = "stage01"
        self.highest_stage = "stage01"
        self.prev_btn_a_down = False
        self.prev_btn_y_down = False
        self.draw_trace_frames = int(getattr(config, "PHASE8_DRAW_TRACE_FRAMES", 120))
        if self.draw_trace_frames < 1:
            self.draw_trace_frames = 1
        self.draw_smoke_enabled = bool(getattr(config, "PHASE8_DRAW_SMOKE_TEST", False))
        self.draw_smoke_fill_done = False
        self.draw_smoke_rect_done = False

        self._init_save()
        if self.mode == "TEST":
            self.debug_enabled = False

        renderer.set_stage(self.stage)

    def _should_trace_draw(self):
        return self.frame < self.draw_trace_frames

    def _draw_trace(self, message):
        if self._should_trace_draw():
            print(message)

    def _run_manual_fill_smoke_once(self):
        if self.mode != "MANUAL" or (not self.draw_smoke_enabled) or self.draw_smoke_fill_done:
            return
        if _lgfx is None:
            self.draw_smoke_fill_done = True
            return
        if hasattr(_lgfx, "fill"):
            print("PHASE8_SMOKE_FILL_RED")
            _lgfx.fill(0xF800)
            sleep_ms(40)
        self.draw_smoke_fill_done = True

    def _run_manual_rect_submit_smoke_once(self):
        if self.mode != "MANUAL" or (not self.draw_smoke_enabled) or self.draw_smoke_rect_done:
            return
        x = 24
        y = 24
        w = 20
        h = 20
        drawables = [(x, y, w, h, 0x07E0)]
        self._draw_trace("PHASE8_DRAW_SUBMIT smoke_rect=%d,%d,%d,%d" % (x, y, w, h))
        self._blit_composed_region(x, y, w, h, drawables, [])
        self._draw_trace("PHASE8_SMOKE_RECT_OK")
        self.draw_smoke_rect_done = True

    def _spawn_enemies(self):
        spawns = self.stage.get("enemy_spawns", [])
        i = 0
        while i < len(spawns):
            spawn = spawns[i]
            ent_type = str(spawn.get("type", "")).lower()

            ent = None
            if ent_type == "enemy_basic":
                ent = create_enemy_basic(
                    int(spawn.get("x", 0)),
                    int(spawn.get("y", 0)),
                    patrol_w=int(spawn.get("patrol_w", 32)),
                    patrol_speed=int(spawn.get("patrol_speed", 1)),
                )
            elif ent_type == "enemy_shooter":
                ent = create_enemy_shooter(
                    int(spawn.get("x", 0)),
                    int(spawn.get("y", 0)),
                    interval_frames=int(spawn.get("interval_frames", 24)),
                    facing=int(spawn.get("facing", -1)),
                    bullet_speed=int(spawn.get("bullet_speed", 4)),
                )

            if ent is not None and hasattr(self.manager, "spawn_enemy"):
                self.manager.spawn_enemy(ent)

            i += 1

    def _is_valid_save_data(self, data):
        if not isinstance(data, dict):
            return False
        player = data.get("player")
        settings = data.get("settings")
        return isinstance(player, dict) and isinstance(settings, dict)

    def _init_save(self):
        if save_system is None:
            self.save_boot_ok = False
            self.save_ok = False
            return

        data = save_system.ensure_default_save()
        self.save_boot_ok = self._is_valid_save_data(data)
        if self.save_boot_ok:
            player = data.get("player", {})
            settings = data.get("settings", {})
            self.player.hp = int(player.get("hp", getattr(self.player, "hp", 5)))
            self.debug_enabled = bool(settings.get("debug", False))
            self.highest_stage = str(data.get("highest_stage", "stage01"))
            self.current_stage = str(data.get("current_stage", self.highest_stage))
        self._refresh_save_ok()

    def to_save_dict(self):
        return {
            "highest_stage": str(self.highest_stage),
            "current_stage": str(self.current_stage),
            "player": {
                "hp": int(getattr(self.player, "hp", 5)),
                "x": int(getattr(self.player, "x", 0)),
                "y": int(getattr(self.player, "y", 0)),
            },
            "settings": {
                "debug": bool(self.debug_enabled),
                "audio": True,
            },
        }

    def _refresh_save_ok(self):
        self.save_ok = self.save_boot_ok and self.save_written and self.save_loaded and self.save_fallback_ok

    def _set_save_status(self, status):
        self.save_status = status
        self.save_status_ttl_frames = int(self.save_status_ttl_default)

    def _tick_save_status(self):
        if self.save_status_ttl_frames <= 0:
            return
        self.save_status_ttl_frames -= 1
        if self.save_status_ttl_frames <= 0:
            self.save_status = "neutral"

    def _trigger_save(self, reason):
        if save_system is None:
            self._set_save_status("fail")
            return False

        ok = save_system.save_game(self, reason)
        if ok:
            self._set_save_status("ok")
            self.save_written = True
        else:
            self._set_save_status("fail")
        self._refresh_save_ok()
        return ok

    def _run_save_load_check(self):
        if save_system is None:
            return

        data = save_system.load_save()
        self.save_loaded = self._is_valid_save_data(data)
        fallback = save_system.load_save("/sd/game/save/__phase8_missing__.json")
        self.save_fallback_ok = self._is_valid_save_data(fallback)
        self._refresh_save_ok()

    def _count_active_entities(self):
        total = 0
        if hasattr(self.manager, "get_active_entities"):
            entities, count = self.manager.get_active_entities()
            i = 0
            while i < count:
                ent = entities[i]
                if ent is not None and ent.active:
                    total += 1
                i += 1
        return total

    def _count_active_bullets(self):
        total = 0
        pool = getattr(self.bullet_pool, "pool", None)
        if pool is None:
            return 0
        i = 0
        while i < len(pool):
            bullet = pool[i]
            if bullet is not None and bullet.active:
                total += 1
            i += 1
        return total

    def _print_debug_line(self):
        if not self.debug_enabled:
            return
        if (self.frame % self.debug_line_interval) != 0:
            return
        print(
            "PHASE8_DBG frame=%d fps=%d px=%d py=%d ent=%d bullet=%d mode=%s"
            % (
                int(self.frame),
                int(self.fps_estimate),
                int(self.player.x),
                int(self.player.y),
                int(self._count_active_entities()),
                int(self._count_active_bullets()),
                self.mode,
            )
        )

    def _set_debug_enabled(self, enabled):
        target = bool(enabled)
        if self.debug_enabled == target:
            return
        self.debug_enabled = target
        if self.debug_enabled:
            print("PHASE8_DEBUG_ON")
        else:
            print("PHASE8_DEBUG_OFF")

    def _read_test_input(self):
        frame_debug_on = int(getattr(config, "PHASE8_TEST_DEBUG_ON_FRAME", 8))
        frame_save = int(getattr(config, "PHASE8_TEST_SAVE_FRAME", 22))
        frame_debug_off = int(getattr(config, "PHASE8_TEST_DEBUG_OFF_FRAME", 44))
        frame_near = int(getattr(config, "PHASE8_TEST_NEAR_FRAME", 70))
        frame_far = int(getattr(config, "PHASE8_TEST_FAR_FRAME", 96))
        frame_save_load = int(getattr(config, "PHASE8_TEST_SAVE_LOAD_FRAME", 128))

        return {
            "x_axis": 0,
            "btn_x_pressed": self.frame == frame_near,
            "btn_b_pressed": self.frame == frame_far,
            "btn_a_pressed": self.frame == frame_save,
            "btn_y_pressed": (self.frame == frame_debug_on) or (self.frame == frame_debug_off),
            "save_reason": "deterministic",
            "run_save_load_check": self.frame == frame_save_load,
        }

    def _read_manual_input(self, now_ms):
        if self.input_system is None:
            return {
                "x_axis": 0,
                "btn_x_pressed": False,
                "btn_b_pressed": False,
                "btn_a_pressed": False,
                "btn_y_pressed": False,
                "btn_a_down": False,
                "btn_y_down": False,
                "save_reason": "manual",
                "run_save_load_check": False,
            }

        self.input_system.update(now_ms)
        return {
            "x_axis": int(self.input_system.joy_x_axis),
            "btn_x_pressed": bool(self.input_system.btn_x_pressed),
            "btn_b_pressed": bool(self.input_system.btn_b_pressed),
            "btn_a_pressed": bool(self.input_system.btn_a_pressed),
            "btn_y_pressed": bool(self.input_system.btn_y_pressed),
            "btn_a_down": bool(self.input_system.btn_a_down),
            "btn_y_down": bool(self.input_system.btn_y_down),
            "save_reason": "manual",
            "run_save_load_check": False,
        }

    def _add_collision_dirty(self, rect):
        if rect is None:
            return

        pad = int(getattr(config, "PHASE8_COLLISION_DIRTY_PAD", 1))
        if pad < 0:
            pad = 0
        padded = _expand_rect(rect, pad)
        self.collision_dirty_region = _merge_dirty_rect(self.collision_dirty_region, padded)

    def _merge_swap_dirty(self, swap_info):
        if swap_info is None:
            return

        self.swap_dirty_region = _merge_dirty_rect(self.swap_dirty_region, swap_info.get("player_old_rect"))
        self.swap_dirty_region = _merge_dirty_rect(self.swap_dirty_region, swap_info.get("player_new_rect"))
        self.swap_dirty_region = _merge_dirty_rect(self.swap_dirty_region, swap_info.get("target_old_rect"))
        self.swap_dirty_region = _merge_dirty_rect(self.swap_dirty_region, swap_info.get("target_new_rect"))

    def _collect_collision_dirty_hints(self):
        self._add_collision_dirty(getattr(self.player, "last_collision_dirty_rect", None))

        if hasattr(self.manager, "get_active_entities"):
            entities, count = self.manager.get_active_entities()
            i = 0
            while i < count:
                ent = entities[i]
                if ent is not None and ent.active:
                    self._add_collision_dirty(getattr(ent, "last_collision_dirty_rect", None))
                i += 1

        pool = getattr(self.bullet_pool, "pool", None)
        if pool is not None:
            i = 0
            while i < len(pool):
                bullet = pool[i]
                if bullet is not None:
                    hint = getattr(bullet, "deactivate_dirty_rect", None)
                    if hint is not None:
                        self._add_collision_dirty(hint)
                        bullet.deactivate_dirty_rect = None
                i += 1

    def _resolve_player_enemy_overlap(self):
        if not hasattr(self.manager, "get_active_entities"):
            return None

        entities, count = self.manager.get_active_entities()
        player_rect = _entity_draw_rect(self.player)
        dirty = None
        i = 0
        while i < count:
            ent = entities[i]
            if ent is None or not ent.active:
                i += 1
                continue

            if ent.entity_type != "enemy_basic" and ent.entity_type != "enemy_shooter":
                i += 1
                continue

            enemy_rect = _entity_draw_rect(ent)
            left = player_rect[0] if player_rect[0] > enemy_rect[0] else enemy_rect[0]
            top = player_rect[1] if player_rect[1] > enemy_rect[1] else enemy_rect[1]
            right = (player_rect[0] + player_rect[2]) if (player_rect[0] + player_rect[2]) < (enemy_rect[0] + enemy_rect[2]) else (enemy_rect[0] + enemy_rect[2])
            bottom = (player_rect[1] + player_rect[3]) if (player_rect[1] + player_rect[3]) < (enemy_rect[1] + enemy_rect[3]) else (enemy_rect[1] + enemy_rect[3])

            if right > left and bottom > top:
                overlap_w = right - left
                overlap_h = bottom - top
                before_rect = player_rect

                player_cx = player_rect[0] + (player_rect[2] // 2)
                player_cy = player_rect[1] + (player_rect[3] // 2)
                enemy_cx = enemy_rect[0] + (enemy_rect[2] // 2)
                enemy_cy = enemy_rect[1] + (enemy_rect[3] // 2)

                if overlap_w <= overlap_h:
                    if player_cx < enemy_cx:
                        self.player.x -= overlap_w
                    else:
                        self.player.x += overlap_w
                    self.player.vx = 0
                else:
                    if player_cy < enemy_cy:
                        self.player.y -= overlap_h
                        if hasattr(self.player, "on_ground"):
                            self.player.on_ground = True
                    else:
                        self.player.y += overlap_h
                    self.player.vy = 0

                player_rect = _entity_draw_rect(self.player)
                if before_rect != player_rect:
                    dirty = _merge_dirty_rect(
                        dirty,
                        _rect_union(
                            before_rect[0],
                            before_rect[1],
                            before_rect[2],
                            before_rect[3],
                            player_rect[0],
                            player_rect[1],
                            player_rect[2],
                            player_rect[3],
                        ),
                    )

            i += 1

        return dirty

    def _collect_skill_targets(self):
        if hasattr(self.manager, "get_skill_query_sources"):
            entities, count, bullet_pool = self.manager.get_skill_query_sources()
        else:
            entities, count = self.manager.get_active_entities()
            bullet_pool = self.bullet_pool

        return skills.collect_swappable_targets(
            self.player,
            entities,
            count,
            bullet_pool,
            0,
            0,
            config.SCREEN_W,
            config.SCREEN_H,
            out_targets=self.target_buffer,
        )

    def _execute_skill(self, which):
        if skills is None:
            return False

        targets = self._collect_skill_targets()
        if which == "NEAR":
            target = skills.find_nearest_swappable(self.player, targets)
        else:
            target = skills.find_farthest_swappable(self.player, targets)

        if target is None:
            return False

        swap_info = skills.execute_swap(self.player, target)
        self._merge_swap_dirty(swap_info)
        skills.post_swap_revalidate(self.player, self.stage)
        skills.post_swap_revalidate(target, self.stage)
        return True

    def _ensure_backbuffer(self, need_bytes, slot):
        if slot == 0:
            if self.backbuffer is None or self.backbuffer_bytes < need_bytes:
                self.backbuffer = bytearray(need_bytes)
                self.backbuffer_bytes = need_bytes
            return memoryview(self.backbuffer)[:need_bytes]

        if self.backbuffer_alt is None or self.backbuffer_alt_bytes < need_bytes:
            self.backbuffer_alt = bytearray(need_bytes)
            self.backbuffer_alt_bytes = need_bytes
        return memoryview(self.backbuffer_alt)[:need_bytes]

    def _count_non_bg_pixels(self, buf_view, pixel_count):
        bg_lo = int(config.COLOR_BG) & 0xFF
        bg_hi = (int(config.COLOR_BG) >> 8) & 0xFF
        idx = 0
        i = 0
        non_bg = 0
        while i < pixel_count:
            if buf_view[idx] != bg_lo or buf_view[idx + 1] != bg_hi:
                non_bg += 1
            idx += 2
            i += 1
        return non_bg

    def _blit_composed_region(self, cx, cy, cw, ch, world_drawables, hud_drawables):
        row_bytes = cw * 2
        if row_bytes <= 0:
            return

        max_bytes = int(getattr(config, "PHASE8_BACKBUFFER_MAX_BYTES", 32768))
        if max_bytes < row_bytes:
            max_bytes = row_bytes
        strip_h = max_bytes // row_bytes
        if strip_h < 1:
            strip_h = 1
        strip_h_limit = int(getattr(config, "PHASE8_STRIP_HEIGHT_LIMIT", 16))
        if strip_h_limit > 0 and strip_h > strip_h_limit:
            strip_h = strip_h_limit

        trace = self._should_trace_draw()
        geom_test = bool(getattr(config, "PHASE8_STRIP_GEOM_TEST", False))
        geom_band_h = int(getattr(config, "PHASE8_STRIP_GEOM_BAND_H", 16))
        if geom_band_h < 1:
            geom_band_h = 1
        if trace:
            print("PHASE8_COMPOSE_BG_OK %d,%d,%d,%d" % (cx, cy, cw, ch))
            print("PHASE8_COMPOSE_WORLD_OK count=%d" % len(world_drawables))
            print("PHASE8_COMPOSE_UI_OK count=%d" % len(hud_drawables))
            print("PHASE8_STRIP_GEOM_TEST=%d" % (1 if geom_test else 0))

        total_non_bg = 0
        total_pixels = 0
        remaining = ch
        sy = cy
        strip_index = 0
        expected_y = cy
        coverage_ok = True
        while remaining > 0:
            sh = strip_h if remaining > strip_h else remaining
            need = cw * sh * 2
            pixel_count = cw * sh
            slot = strip_index & 1
            view = self._ensure_backbuffer(need, slot)

            _fill_buffer_color565(view, pixel_count, config.COLOR_BG)
            if geom_test:
                row = 0
                while row < sh:
                    world_y = sy + row
                    band = (world_y // geom_band_h) & 1
                    color = 0xFFFF if band == 0 else 0x0000
                    _fill_buffer_rect565(view, cw, 0, row, cw, 1, color)
                    row += 1
            else:
                _compose_stage_tiles_buffer(self.stage, cx, sy, cw, sh, view)
                _compose_rects_buffer(cx, sy, cw, sh, world_drawables, view)
                _compose_rects_buffer(cx, sy, cw, sh, hud_drawables, view)

            if trace:
                y0 = sy
                y1 = sy + sh - 1
                idx_last = ((sh - 1) * cw + (cw - 1)) * 2 + 1
                if sy != expected_y:
                    coverage_ok = False
                print(
                    "PHASE8_STRIP idx=%d x=%d y=%d w=%d h=%d stride=%d buf=%d slot=%d cover=%d..%d idx_last=%d"
                    % (strip_index, cx, sy, cw, sh, row_bytes, need, slot, y0, y1, idx_last)
                )
                if idx_last != (need - 1):
                    print("PHASE8_STRIP_INDEX_FAIL idx=%d idx_last=%d need_last=%d" % (strip_index, idx_last, need - 1))
                    coverage_ok = False

            strip_test = bool(getattr(config, "PHASE8_STRIP_TEST_BARS", False))
            if strip_test:
                colors = (0xF800, 0x07E0, 0x001F, 0xFFE0)
                test_color = colors[strip_index & 3]
                _fill_buffer_rect565(view, cw, 0, 0, cw, sh, test_color)

            if trace:
                total_non_bg += self._count_non_bg_pixels(view, pixel_count)
                total_pixels += pixel_count

            _lgfx.blit_rect565(cx, sy, cw, sh, view)
            remaining -= sh
            sy += sh
            expected_y += sh
            strip_index += 1

        if trace:
            if expected_y != (cy + ch):
                coverage_ok = False
            print("PHASE8_STRIP_DONE count=%d full_h=%d" % (strip_index, ch))
            print(
                "PHASE8_STRIP_COVERAGE start=%d end=%d expected_end=%d ok=%d"
                % (cy, expected_y - 1, cy + ch - 1, 1 if coverage_ok else 0)
            )
        if trace and total_pixels > 0:
            print("PHASE8_COMPOSE_NON_BG=%d/%d" % (total_non_bg, total_pixels))

    def _collect_world_draw_rects(self):
        player_rect = _entity_draw_rect(self.player)
        rects = {"player": player_rect}
        drawables = [
            (
                player_rect[0],
                player_rect[1],
                player_rect[2],
                player_rect[3],
                config.COLOR_PLAYER,
            )
        ]

        if hasattr(self.manager, "get_active_entities"):
            entities, count = self.manager.get_active_entities()
            i = 0
            while i < count:
                ent = entities[i]
                if ent is not None and ent.active and ent.visible:
                    rect = _entity_draw_rect(ent)
                    rects[id(ent)] = rect
                    color = config.COLOR_ENEMY_BASIC
                    if ent.entity_type == "enemy_shooter":
                        color = config.COLOR_ENEMY_SHOOTER
                    drawables.append((rect[0], rect[1], rect[2], rect[3], color))
                i += 1

        pool = getattr(self.bullet_pool, "pool", None)
        if pool is not None:
            i = 0
            while i < len(pool):
                bullet = pool[i]
                if bullet is not None and bullet.active and getattr(bullet, "visible", True):
                    key = ("bullet", int(getattr(bullet, "pool_index", i)))
                    rect = _entity_draw_rect(bullet)
                    rects[key] = rect
                    drawables.append((rect[0], rect[1], rect[2], rect[3], config.COLOR_BULLET))
                i += 1

        return rects, drawables

    def _sync_prev_rect_map(self, prev_map, cur_map):
        prev_map.clear()
        for key in cur_map:
            prev_map[key] = cur_map[key]

    def _update_hud(self):
        if ui is None:
            self.ui_ok = False
            return

        snapshot = ui.build_snapshot(
            int(getattr(self.player, "hp", 5)),
            5,
            self.debug_enabled,
            self.save_status,
        )
        ui.compose_hud(snapshot, self.hud_drawables, self.hud_rects)
        required = ("hud_bg", "hp_box", "hp_fill", "hint_x", "hint_b", "save_status", "debug_status")
        ok = True
        i = 0
        while i < len(required):
            if required[i] not in self.hud_rects:
                ok = False
                break
            i += 1
        self.ui_ok = ok

    def _validate_ui_only_dirty(self, dirty):
        if dirty is None:
            return True
        if ui is None:
            return False
        hud_rect = ui.get_hud_rect()
        hx, hy, hw, hh = hud_rect
        dx, dy, dw, dh = dirty
        if dx < hx or dy < hy:
            return False
        if (dx + dw) > (hx + hw):
            return False
        if (dy + dh) > (hy + hh):
            return False
        return True

    def update(self, now_ms):
        if self.last_update_ms != 0:
            delta = ticks_diff(now_ms, self.last_update_ms)
            if delta > 0:
                self.fps_estimate = 1000 // delta
        self.last_update_ms = now_ms

        self.collision_dirty_region = None
        self.swap_dirty_region = None

        if self.mode == "TEST":
            input_state = self._read_test_input()
        else:
            input_state = self._read_manual_input(now_ms)
            # Manual fallback edge detection based on stable down-state.
            a_down = bool(input_state.get("btn_a_down", False))
            y_down = bool(input_state.get("btn_y_down", False))
            if a_down and (not self.prev_btn_a_down):
                input_state["btn_a_pressed"] = True
            if y_down and (not self.prev_btn_y_down):
                input_state["btn_y_pressed"] = True
            self.prev_btn_a_down = a_down
            self.prev_btn_y_down = y_down

        if input_state["btn_y_pressed"]:
            print("PHASE8_BTN_Y_EDGE")
            self._set_debug_enabled(not self.debug_enabled)

        if input_state["btn_a_pressed"]:
            print("PHASE8_BTN_A_EDGE")
            if self._trigger_save(input_state["save_reason"]):
                print("PHASE8_SAVE_TRIGGERED")

        if input_state["btn_x_pressed"]:
            self._execute_skill("NEAR")
        if input_state["btn_b_pressed"]:
            self._execute_skill("FAR")

        self.player.apply_input(int(input_state["x_axis"]))
        player_dirty = step_entity(self.player, self.stage)
        self._add_collision_dirty(player_dirty)

        if hasattr(self.manager, "update_all"):
            self.manager.update_all(now_ms, self.stage, step_entity)
        overlap_dirty = self._resolve_player_enemy_overlap()
        self._add_collision_dirty(overlap_dirty)
        self._collect_collision_dirty_hints()
        if hasattr(self.manager, "cleanup"):
            self.manager.cleanup()

        if input_state["run_save_load_check"]:
            self._run_save_load_check()

        self._tick_save_status()
        self._print_debug_line()
        self.frame += 1

    def draw(self):
        self._draw_trace("PHASE8_DRAW_ENTER frame=%d drawn_once=%d" % (int(self.frame), 1 if self.drawn_once else 0))
        self._run_manual_fill_smoke_once()

        world_rects, world_drawables = self._collect_world_draw_rects()
        self._update_hud()

        if not self.drawn_once:
            self._run_manual_rect_submit_smoke_once()

            self._draw_trace("PHASE8_DRAW_DIRTY=FIRST_FRAME_FULL")
            self._draw_trace("PHASE8_DRAW_SUBMIT first_frame=compose_blit")
            self._blit_composed_region(0, 0, config.SCREEN_W, config.SCREEN_H, world_drawables, self.hud_drawables)

            self._draw_trace("PHASE8_DRAW_OK")

            self.drawn_once = True
            self._sync_prev_rect_map(self.prev_world_rects, world_rects)
            self._sync_prev_rect_map(self.prev_hud_rects, self.hud_rects)
            self.draw_count += 1
            if self.draw_count >= 3:
                self.draw_ok = True
            return

        world_dirty = _compute_dirty_from_rect_maps(self.prev_world_rects, world_rects)
        world_dirty = _merge_dirty_rect(world_dirty, self.collision_dirty_region)
        world_dirty = _merge_dirty_rect(world_dirty, self.swap_dirty_region)

        ui_dirty = _compute_dirty_from_rect_maps(self.prev_hud_rects, self.hud_rects)
        if world_dirty is None and ui_dirty is not None:
            if not self._validate_ui_only_dirty(ui_dirty):
                self.ui_dirty_violation = True

        dirty = _merge_dirty_rect(world_dirty, ui_dirty)
        self._draw_trace(
            "PHASE8_DRAW_DIRTY=world:%s ui:%s merged:%s"
            % (str(world_dirty), str(ui_dirty), str(dirty))
        )

        self.collision_dirty_region = None
        self.swap_dirty_region = None
        self._sync_prev_rect_map(self.prev_world_rects, world_rects)
        self._sync_prev_rect_map(self.prev_hud_rects, self.hud_rects)

        if dirty is None:
            return

        clipped = _clip_rect_screen(dirty[0], dirty[1], dirty[2], dirty[3])
        if clipped is None:
            return

        del self.composed_drawables[:]
        i = 0
        while i < len(world_drawables):
            self.composed_drawables.append(world_drawables[i])
            i += 1
        i = 0
        while i < len(self.hud_drawables):
            self.composed_drawables.append(self.hud_drawables[i])
            i += 1

        cx, cy, cw, ch = clipped
        self._draw_trace("PHASE8_DRAW_SUBMIT %d,%d,%d,%d" % (cx, cy, cw, ch))
        self._blit_composed_region(cx, cy, cw, ch, world_drawables, self.hud_drawables)
        self._draw_trace("PHASE8_DRAW_OK")

        self.draw_count += 1
        if self.draw_count >= 3:
            self.draw_ok = True


def _phase8_fail(tag):
    print(tag)
    raise RuntimeError(tag)


def _validate_phase8_results(runtime):
    if (not runtime.ui_ok) or runtime.ui_dirty_violation:
        _phase8_fail("PHASE8_FAIL_UI")
    if not runtime.save_ok:
        _phase8_fail("PHASE8_FAIL_SAVE")
    if runtime.submit_violation or (not runtime.draw_ok):
        _phase8_fail("PHASE8_FAIL_DRAW")

    print("PHASE8_UI_OK")
    print("PHASE8_SAVE_OK")
    print("PHASE8_DRAW_OK")


def _run_phase8(max_frames):
    print("APP_RUN_START_PHASE8")

    if _lgfx is None:
        raise RuntimeError("PHASE8_FAIL_NO_LGFX")
    if not hasattr(_lgfx, "blit_rect565"):
        raise RuntimeError("PHASE8_FAIL_NO_BLIT")
    if skills is None:
        raise RuntimeError("PHASE8_FAIL_NO_SKILLS")
    if ui is None:
        raise RuntimeError("PHASE8_FAIL_UI")
    if save_system is None:
        raise RuntimeError("PHASE8_FAIL_SAVE")

    mode = _select_phase8_mode(max_frames)
    runtime = _Phase8Runtime(mode)
    boot_source = str(_boot_source_tag)
    if boot_source not in ("ROOT", "SD"):
        try:
            path = str(getattr(__import__(__name__), "__file__", ""))
        except Exception:
            path = ""
        boot_source = "SD" if path.startswith("/sd/") else "ROOT"
    print("PHASE8_BOOT_SOURCE=%s" % boot_source)
    print("PHASE8_MODE=%s" % mode)
    if mode == "TEST":
        print("PHASE8_INPUT_SOURCE=DETERMINISTIC")
    else:
        print("PHASE8_INPUT_SOURCE=REAL_INPUT")
        if runtime.input_system is None:
            raise RuntimeError("PHASE8_FAIL_INPUT_INIT")

    renderer.init()
    runtime.draw()

    if mode == "TEST":
        if max_frames is None:
            frame_limit = int(getattr(config, "PHASE8_TEST_FRAMES", 360))
        else:
            frame_limit = int(max_frames)
    else:
        frame_limit = int(getattr(config, "PHASE8_MANUAL_FRAMES", 900))

    if frame_limit < 1:
        frame_limit = 1

    last_tick = ticks_ms()

    while True:
        now = ticks_ms()
        elapsed = ticks_diff(now, last_tick)
        if elapsed < config.FRAME_MS:
            sleep_ms(config.FRAME_MS - elapsed)
            continue
        last_tick = now

        runtime.update(now)
        runtime.draw()

        if runtime.frame >= frame_limit:
            break

    if mode == "TEST":
        _validate_phase8_results(runtime)
    print("APP_RUN_END_PHASE8")



def run(max_frames=None):
    _ensure_phase_dependencies("PHASE8")
    _run_phase8(max_frames)
