def is_solid_tile(stage_data, tx, ty):
    width = int(stage_data.get("width", 0))
    height = int(stage_data.get("height", 0))
    if tx < 0 or ty < 0 or tx >= width or ty >= height:
        return True

    layers = stage_data.get("tile_layers", [])
    if not layers:
        return False

    tile = layers[0][ty][tx]
    solids = stage_data.get("solid_tiles", [1])
    return tile in solids


def is_solid_at_pixel(stage_data, px, py):
    tile_size = int(stage_data.get("tile_size", 16))
    tx = int(px // tile_size)
    ty = int(py // tile_size)
    return is_solid_tile(stage_data, tx, ty)


def clamp_entity_to_world(ent, stage_data):
    hb = ent.hitbox
    width = int(stage_data.get("width", 0))
    height = int(stage_data.get("height", 0))
    tile_size = int(stage_data.get("tile_size", 16))

    world_w = width * tile_size
    world_h = height * tile_size

    min_x = -int(hb[0])
    max_x = world_w - int(hb[0]) - int(hb[2])
    min_y = -int(hb[1])
    max_y = world_h - int(hb[1]) - int(hb[3])

    if max_x < min_x:
        max_x = min_x
    if max_y < min_y:
        max_y = min_y

    old_x = int(ent.x)
    old_y = int(ent.y)

    if ent.x < min_x:
        ent.x = min_x
    elif ent.x > max_x:
        ent.x = max_x

    if ent.y < min_y:
        ent.y = min_y
    elif ent.y > max_y:
        ent.y = max_y

    return (old_x != int(ent.x)), (old_y != int(ent.y))


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _entity_rect(ent):
    hb = ent.hitbox
    left = int(ent.x + hb[0])
    top = int(ent.y + hb[1])
    right = left + int(hb[2]) - 1
    bottom = top + int(hb[3]) - 1
    return left, top, right, bottom


def _tile_span_for_rect(stage_data, left, top, right, bottom):
    tile_size = int(stage_data.get("tile_size", 16))
    width = int(stage_data.get("width", 0))
    height = int(stage_data.get("height", 0))

    tx0 = int(left // tile_size)
    ty0 = int(top // tile_size)
    tx1 = int(right // tile_size)
    ty1 = int(bottom // tile_size)

    tx0 = _clamp(tx0, 0, width - 1)
    ty0 = _clamp(ty0, 0, height - 1)
    tx1 = _clamp(tx1, 0, width - 1)
    ty1 = _clamp(ty1, 0, height - 1)
    return tx0, ty0, tx1, ty1


def _rect_hits_solid(stage_data, left, top, right, bottom):
    width = int(stage_data.get("width", 0))
    height = int(stage_data.get("height", 0))

    # Outside map bounds is considered solid.
    if left < 0 or top < 0:
        return True

    tile_size = int(stage_data.get("tile_size", 16))
    world_w = width * tile_size
    world_h = height * tile_size
    if right >= world_w or bottom >= world_h:
        return True

    layers = stage_data.get("tile_layers", [])
    if not layers:
        return False
    tiles = layers[0]
    solids = stage_data.get("solid_tiles", [1])

    tx0, ty0, tx1, ty1 = _tile_span_for_rect(stage_data, left, top, right, bottom)
    ty = ty0
    while ty <= ty1:
        row = tiles[ty]
        tx = tx0
        while tx <= tx1:
            if row[tx] in solids:
                return True
            tx += 1
        ty += 1
    return False


def is_on_ground(ent, stage_data):
    left, top, right, bottom = _entity_rect(ent)
    return _rect_hits_solid(stage_data, left, bottom + 1, right, bottom + 1)


def resolve_x_collision(ent, stage_data):
    vx = int(ent.vx)
    if vx == 0:
        return False

    left, top, right, bottom = _entity_rect(ent)
    if not _rect_hits_solid(stage_data, left, top, right, bottom):
        return False

    moved = 0
    step = -1 if vx > 0 else 1
    limit = abs(vx) + int(stage_data.get("tile_size", 16)) + 2

    while moved < limit:
        ent.x += step
        moved += 1
        left, top, right, bottom = _entity_rect(ent)
        if not _rect_hits_solid(stage_data, left, top, right, bottom):
            ent.vx = 0
            return True

    ent.vx = 0
    return True


def resolve_y_collision(ent, stage_data):
    vy = int(ent.vy)

    left, top, right, bottom = _entity_rect(ent)
    colliding = _rect_hits_solid(stage_data, left, top, right, bottom)

    if colliding and vy > 0:
        moved = 0
        limit = abs(vy) + int(stage_data.get("tile_size", 16)) + 2
        while moved < limit and colliding:
            ent.y -= 1
            moved += 1
            left, top, right, bottom = _entity_rect(ent)
            colliding = _rect_hits_solid(stage_data, left, top, right, bottom)
        ent.vy = 0
        ent.on_ground = True
        return True

    if colliding and vy < 0:
        moved = 0
        limit = abs(vy) + int(stage_data.get("tile_size", 16)) + 2
        while moved < limit and colliding:
            ent.y += 1
            moved += 1
            left, top, right, bottom = _entity_rect(ent)
            colliding = _rect_hits_solid(stage_data, left, top, right, bottom)
        ent.vy = 0

    ent.on_ground = is_on_ground(ent, stage_data)
    return colliding
