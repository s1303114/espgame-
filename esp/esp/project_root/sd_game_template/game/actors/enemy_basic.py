import assets
from engine import collision
from engine.entity import Entity


class EnemyBasic(Entity):
    __slots__ = ("left_bound", "right_bound", "patrol_speed")

    def __init__(self, x, y, patrol_w=32, patrol_speed=1):
        super().__init__(x, y, assets.ENEMY_W, assets.ENEMY_H, entity_type="enemy_basic")
        self.left_bound = int(x) - int(patrol_w)
        self.right_bound = int(x) + int(patrol_w)
        self.patrol_speed = int(patrol_speed)
        if self.patrol_speed < 1:
            self.patrol_speed = 1
        self.facing = 1
        self.vx = self.patrol_speed
        self.affected_by_gravity = True
        self.swappable = True
        self.state = "patrol"

    def _turn_around(self):
        self.facing = -1 if self.facing > 0 else 1
        self.vx = self.patrol_speed * self.facing

    def update(self, now_ms, stage_data, bullet_pool=None):
        if not self.active:
            return

        if self.x <= self.left_bound:
            self.x = self.left_bound
            if self.facing < 0:
                self._turn_around()
        elif self.x >= self.right_bound:
            self.x = self.right_bound
            if self.facing > 0:
                self._turn_around()

        hb = self.hitbox
        front_x = int(self.x + hb[0] + (hb[2] if self.facing > 0 else -1))
        center_y = int(self.y + hb[1] + (hb[3] // 2))
        floor_y = int(self.y + hb[1] + hb[3])

        if collision.is_solid_at_pixel(stage_data, front_x, center_y):
            self._turn_around()
        elif not collision.is_solid_at_pixel(stage_data, front_x, floor_y + 1):
            self._turn_around()

        self.vx = self.patrol_speed * self.facing


def create_enemy_basic(x, y, patrol_w=32, patrol_speed=1):
    return EnemyBasic(x, y, patrol_w=patrol_w, patrol_speed=patrol_speed)
