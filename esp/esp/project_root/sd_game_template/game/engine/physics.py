import config
from engine import collision


def _draw_rect(ent):
    hb = ent.hitbox
    return (
        int(ent.x + hb[0]),
        int(ent.y + hb[1]),
        int(hb[2]),
        int(hb[3]),
    )


def _merge_rect(rect0, rect1):
    if rect1 is None:
        return rect0
    x1, y1, w1, h1 = rect1
    if w1 <= 0 or h1 <= 0:
        return rect0

    if rect0 is None:
        return int(x1), int(y1), int(w1), int(h1)

    x0, y0, w0, h0 = rect0
    l = x0 if x0 < x1 else x1
    t = y0 if y0 < y1 else y1
    r0 = x0 + w0
    r1 = x1 + w1
    b0 = y0 + h0
    b1 = y1 + h1
    r = r0 if r0 > r1 else r1
    b = b0 if b0 > b1 else b1
    return l, t, (r - l), (b - t)


def apply_gravity(ent):
    if not ent.affected_by_gravity:
        return
    ent.vy += config.GRAVITY
    if ent.vy > config.MAX_FALL_SPEED:
        ent.vy = config.MAX_FALL_SPEED


def integrate_x(ent):
    ent.x += ent.vx


def integrate_y(ent):
    ent.y += ent.vy


def step_entity(ent, stage_data):
    ent.last_collision_dirty_rect = None
    pre_rect = _draw_rect(ent)

    apply_gravity(ent)
    integrate_x(ent)
    x_integrated_rect = _draw_rect(ent)
    hit_x = collision.resolve_x_collision(ent, stage_data)
    x_resolved_rect = _draw_rect(ent)

    integrate_y(ent)
    y_integrated_rect = _draw_rect(ent)
    hit_y = collision.resolve_y_collision(ent, stage_data)
    y_resolved_rect = _draw_rect(ent)

    clamped_x, clamped_y = collision.clamp_entity_to_world(ent, stage_data)
    if clamped_x:
        ent.vx = 0
    if clamped_y:
        ent.vy = 0
        ent.on_ground = collision.is_on_ground(ent, stage_data)

    final_rect = _draw_rect(ent)
    if hit_x or hit_y or clamped_x or clamped_y:
        dirty = None
        dirty = _merge_rect(dirty, pre_rect)
        dirty = _merge_rect(dirty, x_integrated_rect)
        dirty = _merge_rect(dirty, x_resolved_rect)
        dirty = _merge_rect(dirty, y_integrated_rect)
        dirty = _merge_rect(dirty, y_resolved_rect)
        dirty = _merge_rect(dirty, final_rect)
        ent.last_collision_dirty_rect = dirty

    return ent.last_collision_dirty_rect
