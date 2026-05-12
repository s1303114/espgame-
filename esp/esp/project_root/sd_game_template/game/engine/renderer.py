import config

try:
    import lgfx
except Exception:
    lgfx = None

_stage = None
_floor_rgb_fp = None
_floor_mask_fp = None
_floor_ready = False


def _resolve_asset_path(path):
    p = str(path)
    if p.startswith("/"):
        return p
    if p.startswith("sd/"):
        return "/" + p
    return "/sd/" + p


def _load_floor_assets():
    global _floor_rgb_fp, _floor_mask_fp, _floor_ready
    if _floor_ready:
        return

    _floor_ready = True
    _floor_rgb_fp = None
    _floor_mask_fp = None
    try:
        rgb_path = _resolve_asset_path(config.FLOOR_LAYER_RGB565_PATH)
        mask_path = _resolve_asset_path(config.FLOOR_LAYER_MASK_PATH)
        _floor_rgb_fp = open(rgb_path, "rb")
        _floor_mask_fp = open(mask_path, "rb")
    except Exception:
        _floor_rgb_fp = None
        _floor_mask_fp = None


def set_stage(stage_data):
    global _stage
    _stage = stage_data


def init():
    if lgfx is None:
        print("renderer: lgfx unavailable")
        return
    lgfx.init()
    lgfx.rotation(1)


def clear_region(x, y, w, h, color):
    if lgfx is None:
        return

    if hasattr(lgfx, "fill_rect"):
        lgfx.fill_rect(int(x), int(y), int(w), int(h), int(color))
        return

    # Fallback for Phase 1: only full-screen clear is possible with lgfx.fill.
    if x <= 0 and y <= 0 and w >= config.SCREEN_W and h >= config.SCREEN_H:
        lgfx.fill(int(color))


def draw_tilemap(camera_x, camera_y):
    if _stage is None:
        return

    layer = _stage.get("tile_layers", [])
    if not layer:
        return

    if not hasattr(lgfx, "fill_rect"):
        # No partial primitive yet; keep Phase 1 safe and cheap.
        return

    if bool(getattr(config, "FLOOR_LAYER_ENABLED", False)):
        _draw_floor_layer(camera_x)

    tiles = layer[0]
    tile_size = int(_stage.get("tile_size", config.TILE_SIZE))
    world_w = int(_stage.get("width", 0))
    world_h = int(_stage.get("height", 0))

    start_tx = int(camera_x // tile_size)
    start_ty = int(camera_y // tile_size)
    end_tx = start_tx + (config.SCREEN_W // tile_size) + 2
    end_ty = start_ty + (config.SCREEN_H // tile_size) + 2

    if end_tx > world_w:
        end_tx = world_w
    if end_ty > world_h:
        end_ty = world_h

    for ty in range(start_ty, end_ty):
        row = tiles[ty]
        py = ty * tile_size - camera_y
        for tx in range(start_tx, end_tx):
            if row[tx] != 0:
                px = tx * tile_size - camera_x
                lgfx.fill_rect(px, py, tile_size, tile_size, config.COLOR_TILE_SOLID)


def _draw_floor_layer(camera_x):
    if lgfx is None:
        return
    if not hasattr(lgfx, "blit_rect565"):
        return

    _load_floor_assets()
    if _floor_rgb_fp is None or _floor_mask_fp is None:
        return

    sw = int(config.SCREEN_W)
    sh = int(config.SCREEN_H)
    fw = int(getattr(config, "FLOOR_LAYER_W", 0))
    fh = int(getattr(config, "FLOOR_LAYER_H", 0))
    if fw <= 0 or fh <= 0:
        return

    dst_y = int(getattr(config, "FLOOR_LAYER_SCREEN_Y", sh - fh))
    draw_y0 = 0 if dst_y >= 0 else -dst_y
    draw_y1 = fh if (dst_y + fh) <= sh else (sh - dst_y)
    if draw_y1 <= draw_y0:
        return

    row_px = sw
    row_rgb = bytearray(row_px * 2)
    row_mask_bytes = (row_px + 7) // 8
    row_mask = bytearray(row_mask_bytes)
    run_buf = bytearray(row_px * 2)
    floor_src_x = int(camera_x * float(getattr(config, "FLOOR_SCROLL_FACTOR", 1.0)))
    floor_row_mask_bytes = (fw + 7) // 8

    y = draw_y0
    while y < draw_y1:
        src_y = y
        dst_screen_y = dst_y + y
        src_x0 = floor_src_x
        src_x1 = floor_src_x + sw
        read_x0 = src_x0 if src_x0 > 0 else 0
        read_x1 = src_x1 if src_x1 < fw else fw

        if read_x1 <= read_x0:
            y += 1
            continue

        visible_w = read_x1 - read_x0
        dst_off_px = read_x0 - src_x0
        rgb_off = ((src_y * fw) + read_x0) * 2
        mask_off = (src_y * floor_row_mask_bytes) + (read_x0 // 8)
        bit_start = read_x0 & 7

        try:
            _floor_rgb_fp.seek(rgb_off)
            _floor_rgb_fp.readinto(memoryview(row_rgb)[: visible_w * 2])
            need_mask_bytes = (bit_start + visible_w + 7) // 8
            _floor_mask_fp.seek(mask_off)
            _floor_mask_fp.readinto(memoryview(row_mask)[:need_mask_bytes])
        except Exception:
            return

        i = 0
        while i < visible_w:
            mask_index = (bit_start + i) >> 3
            mask_bit = 7 - ((bit_start + i) & 7)
            opaque = ((row_mask[mask_index] >> mask_bit) & 1) != 0
            if not opaque:
                i += 1
                continue

            run_start = i
            i += 1
            while i < visible_w:
                mask_index = (bit_start + i) >> 3
                mask_bit = 7 - ((bit_start + i) & 7)
                if ((row_mask[mask_index] >> mask_bit) & 1) == 0:
                    break
                i += 1

            run_len = i - run_start
            s0 = run_start * 2
            s1 = s0 + (run_len * 2)
            run_buf[: run_len * 2] = row_rgb[s0:s1]
            lgfx.blit_rect565(
                dst_off_px + run_start,
                dst_screen_y,
                run_len,
                1,
                memoryview(run_buf)[: run_len * 2],
            )
        y += 1


def draw_player(player_obj):
    if lgfx is None or player_obj is None or not player_obj.active:
        return
    if not hasattr(lgfx, "fill_rect"):
        return
    lgfx.fill_rect(player_obj.x, player_obj.y, player_obj.hitbox[2], player_obj.hitbox[3], config.COLOR_PLAYER)


def draw_enemy(enemy_obj):
    if lgfx is None or enemy_obj is None or not enemy_obj.active:
        return
    if not hasattr(lgfx, "fill_rect"):
        return

    color = config.COLOR_ENEMY_BASIC
    if enemy_obj.entity_type == "enemy_shooter":
        color = config.COLOR_ENEMY_SHOOTER
    lgfx.fill_rect(enemy_obj.x, enemy_obj.y, enemy_obj.hitbox[2], enemy_obj.hitbox[3], color)


def draw_bullet(bullet_obj):
    if lgfx is None or bullet_obj is None or not bullet_obj.active:
        return
    if not hasattr(lgfx, "fill_rect"):
        return
    lgfx.fill_rect(bullet_obj.x, bullet_obj.y, bullet_obj.hitbox[2], bullet_obj.hitbox[3], config.COLOR_BULLET)


def draw_entities(entities, count):
    if lgfx is None or not hasattr(lgfx, "fill_rect"):
        return

    for i in range(count):
        ent = entities[i]
        if ent is None or not ent.active:
            continue
        if ent.entity_type == "bullet":
            draw_bullet(ent)
        else:
            draw_enemy(ent)


def draw_ui(game_state):
    # Phase 1 keeps UI minimal; text API may not exist yet.
    if lgfx is None:
        return
    if not hasattr(lgfx, "fill_rect"):
        return
    lgfx.fill_rect(0, 0, config.SCREEN_W, 12, config.COLOR_UI_BG)


def present():
    # ILI9341 path is immediate mode for now.
    return
