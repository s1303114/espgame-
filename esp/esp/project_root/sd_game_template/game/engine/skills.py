def squared_distance(ax, ay, bx, by):
    dx = int(ax) - int(bx)
    dy = int(ay) - int(by)
    return dx * dx + dy * dy


def _entity_draw_rect(ent):
    hb = ent.hitbox
    return (
        int(ent.x + hb[0]),
        int(ent.y + hb[1]),
        int(hb[2]),
        int(hb[3]),
    )


def is_entity_in_view(ent, camera_x, camera_y, view_w, view_h):
    if ent is None:
        return False

    rx, ry, rw, rh = _entity_draw_rect(ent)
    vx0 = int(camera_x)
    vy0 = int(camera_y)
    vx1 = vx0 + int(view_w)
    vy1 = vy0 + int(view_h)

    ex0 = rx
    ey0 = ry
    ex1 = rx + rw
    ey1 = ry + rh

    if ex1 <= vx0 or ey1 <= vy0:
        return False
    if ex0 >= vx1 or ey0 >= vy1:
        return False
    return True


def _append_if_swappable(player, ent, camera_x, camera_y, view_w, view_h, targets):
    if ent is None:
        return
    if ent is player:
        return
    if not getattr(ent, "active", False):
        return
    if not getattr(ent, "visible", True):
        return
    if not getattr(ent, "swappable", False):
        return
    if not is_entity_in_view(ent, camera_x, camera_y, view_w, view_h):
        return
    targets.append(ent)


def collect_swappable_targets(
    player,
    entities,
    entity_count,
    bullet_pool,
    camera_x,
    camera_y,
    view_w,
    view_h,
    out_targets=None,
):
    if out_targets is None:
        targets = []
    else:
        targets = out_targets
        del targets[:]

    count = int(entity_count)
    i = 0
    while i < count:
        _append_if_swappable(player, entities[i], camera_x, camera_y, view_w, view_h, targets)
        i += 1

    pool = getattr(bullet_pool, "pool", None)
    if pool is not None:
        i = 0
        while i < len(pool):
            _append_if_swappable(player, pool[i], camera_x, camera_y, view_w, view_h, targets)
            i += 1

    return targets


def find_nearest_swappable(player, targets):
    best = None
    best_d2 = 0

    px = int(player.x)
    py = int(player.y)

    i = 0
    while i < len(targets):
        ent = targets[i]
        d2 = squared_distance(px, py, int(ent.x), int(ent.y))
        if best is None or d2 < best_d2:
            best = ent
            best_d2 = d2
        i += 1

    return best


def find_farthest_swappable(player, targets):
    best = None
    best_d2 = 0

    px = int(player.x)
    py = int(player.y)

    i = 0
    while i < len(targets):
        ent = targets[i]
        d2 = squared_distance(px, py, int(ent.x), int(ent.y))
        if best is None or d2 > best_d2:
            best = ent
            best_d2 = d2
        i += 1

    return best


def execute_swap(player, target):
    if player is None or target is None:
        return None

    player_old_rect = _entity_draw_rect(player)
    target_old_rect = _entity_draw_rect(target)

    px = int(player.x)
    py = int(player.y)
    player.x = int(target.x)
    player.y = int(target.y)
    target.x = px
    target.y = py

    return {
        "player_old_rect": player_old_rect,
        "player_new_rect": _entity_draw_rect(player),
        "target_old_rect": target_old_rect,
        "target_new_rect": _entity_draw_rect(target),
    }


def post_swap_revalidate(ent, stage_data):
    if ent is None or stage_data is None:
        return
    if not getattr(ent, "active", False):
        return

    if not getattr(ent, "affected_by_gravity", False):
        if hasattr(ent, "on_ground"):
            ent.on_ground = False
        return

    try:
        from engine import collision
    except Exception:
        if hasattr(ent, "on_ground"):
            ent.on_ground = False
        return

    on_ground = collision.is_on_ground(ent, stage_data)
    if hasattr(ent, "on_ground"):
        ent.on_ground = bool(on_ground)

    if on_ground:
        if hasattr(ent, "vy") and int(ent.vy) > 0:
            ent.vy = 0
        return

    # If swapped into air, force immediate falling state.
    if hasattr(ent, "vy") and int(ent.vy) <= 0:
        ent.vy = 1
