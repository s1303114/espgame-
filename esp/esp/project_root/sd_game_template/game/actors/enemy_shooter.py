import assets
from engine.entity import Entity


class EnemyShooter(Entity):
    __slots__ = ("shoot_interval_frames", "shoot_timer", "bullet_speed", "fired_count")

    def __init__(self, x, y, interval_frames=24, facing=-1, bullet_speed=2):
        super().__init__(x, y, assets.ENEMY_W, assets.ENEMY_H, entity_type="enemy_shooter")
        self.shoot_interval_frames = int(interval_frames)
        if self.shoot_interval_frames < 4:
            self.shoot_interval_frames = 4
        self.shoot_timer = 0
        self.facing = -1 if int(facing) < 0 else 1
        self.bullet_speed = int(bullet_speed)
        if self.bullet_speed < 1:
            self.bullet_speed = 1
        self.fired_count = 0
        self.vx = 0
        self.affected_by_gravity = True
        self.swappable = True
        self.state = "idle"

    def _spawn_bullet(self, bullet_pool):
        if bullet_pool is None:
            return False

        bw = int(getattr(assets, "BULLET_W", 4))
        bh = int(getattr(assets, "BULLET_H", 4))

        if self.facing > 0:
            bx = int(self.x + self.hitbox[2])
        else:
            bx = int(self.x - bw)
        by = int(self.y + (self.hitbox[3] // 2) - (bh // 2))

        vx = self.bullet_speed * self.facing
        spawned = bullet_pool.spawn(bx, by, vx, 0)
        if spawned is not None:
            self.fired_count += 1
            return True
        return False

    def update(self, now_ms, stage_data, bullet_pool=None):
        if not self.active:
            return

        self.vx = 0
        self.shoot_timer += 1
        if self.shoot_timer < self.shoot_interval_frames:
            return

        self.shoot_timer = 0
        self._spawn_bullet(bullet_pool)


def create_enemy_shooter(x, y, interval_frames=24, facing=-1, bullet_speed=2):
    return EnemyShooter(
        x,
        y,
        interval_frames=interval_frames,
        facing=facing,
        bullet_speed=bullet_speed,
    )
