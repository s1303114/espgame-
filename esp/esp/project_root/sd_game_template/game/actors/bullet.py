import assets
from engine import collision
from engine.entity import Entity


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


class Bullet(Entity):
    __slots__ = ("max_frames", "age_frames", "pool_index", "deactivate_dirty_rect")

    def __init__(self, pool_index, max_frames):
        super().__init__(0, 0, assets.BULLET_W, assets.BULLET_H, entity_type="bullet")
        self.active = False
        self.visible = False
        self.swappable = True
        self.affected_by_gravity = False
        self.max_frames = int(max_frames)
        if self.max_frames < 8:
            self.max_frames = 8
        self.age_frames = 0
        self.pool_index = int(pool_index)
        self.state = "idle"
        self.deactivate_dirty_rect = None

    def reset(self, x, y, vx, vy):
        self.x = int(x)
        self.y = int(y)
        self.vx = int(vx)
        self.vy = int(vy)
        self.age_frames = 0
        self.remove_requested = False
        self.active = True
        self.visible = True
        self.state = "flying"
        self.deactivate_dirty_rect = None

    def update(self, now_ms, stage_data):
        if not self.active:
            return

        old_rect = _draw_rect(self)
        self.x += self.vx
        self.y += self.vy
        self.age_frames += 1
        new_rect = _draw_rect(self)

        if self.age_frames >= self.max_frames:
            self._deactivate_with_dirty(old_rect, new_rect)
            return

        tile_size = int(stage_data.get("tile_size", 16))
        world_w = int(stage_data.get("width", 0)) * tile_size
        world_h = int(stage_data.get("height", 0)) * tile_size
        right = int(self.x + self.hitbox[2] - 1)
        bottom = int(self.y + self.hitbox[3] - 1)

        if self.x < 0 or self.y < 0 or right >= world_w or bottom >= world_h:
            self._deactivate_with_dirty(old_rect, new_rect)
            return

        center_x = int(self.x + (self.hitbox[2] // 2))
        center_y = int(self.y + (self.hitbox[3] // 2))
        if collision.is_solid_at_pixel(stage_data, center_x, center_y):
            self._deactivate_with_dirty(old_rect, new_rect)

    def _deactivate_with_dirty(self, old_rect, new_rect):
        self.deactivate_dirty_rect = _merge_rect(old_rect, new_rect)
        self.deactivate()

    def deactivate(self):
        if self.deactivate_dirty_rect is None:
            self.deactivate_dirty_rect = _draw_rect(self)
        super().deactivate()
        self.state = "idle"


class BulletPool:
    __slots__ = (
        "pool",
        "size",
        "max_frames",
        "spawn_requests",
        "spawn_success",
        "reuse_count",
        "active_count_peak",
        "_slot_ever_used",
    )

    def __init__(self, size, max_frames=36):
        self.size = int(size)
        if self.size < 1:
            self.size = 1

        self.max_frames = int(max_frames)
        if self.max_frames < 8:
            self.max_frames = 8

        self.pool = [Bullet(i, self.max_frames) for i in range(self.size)]
        self.spawn_requests = 0
        self.spawn_success = 0
        self.reuse_count = 0
        self.active_count_peak = 0
        self._slot_ever_used = [False] * self.size

    def spawn(self, x, y, vx, vy):
        self.spawn_requests += 1
        for i in range(self.size):
            b = self.pool[i]
            if not b.active:
                if self._slot_ever_used[i]:
                    self.reuse_count += 1
                else:
                    self._slot_ever_used[i] = True

                b.reset(x, y, vx, vy)
                self.spawn_success += 1
                return b
        return None

    def update_all(self, now_ms, stage_data):
        active_now = 0
        for i in range(self.size):
            b = self.pool[i]
            if b.active:
                b.update(now_ms, stage_data)
                if b.active:
                    active_now += 1

        if active_now > self.active_count_peak:
            self.active_count_peak = active_now

    def draw_all(self, renderer_mod):
        for i in range(self.size):
            b = self.pool[i]
            if b.active and b.visible:
                renderer_mod.draw_bullet(b)

    def get_active_count(self):
        active = 0
        for i in range(self.size):
            if self.pool[i].active:
                active += 1
        return active

    def has_reuse(self):
        return self.reuse_count > 0
