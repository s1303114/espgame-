import assets
import config
from engine.entity import Entity


class Player(Entity):
    __slots__ = ("input_x_axis",)

    def __init__(self, x, y):
        super().__init__(x, y, assets.PLAYER_W, assets.PLAYER_H, entity_type="player")
        self.input_x_axis = 0
        self.facing = 1
        self.hp = 5
        self.affected_by_gravity = True
        self.swappable = False

    def apply_input(self, input_state):
        if isinstance(input_state, int):
            x_axis = int(input_state)
        else:
            x_axis = int(getattr(input_state, "joy_x_axis", 0))

        self.input_x_axis = x_axis
        if x_axis > 20:
            self.vx = config.PLAYER_SPEED_X
            self.facing = 1
        elif x_axis < -20:
            self.vx = -config.PLAYER_SPEED_X
            self.facing = -1
        else:
            self.vx = 0

    def update(self, now_ms, stage_data, bullet_pool=None):
        return

    def get_draw_rect(self):
        return int(self.x), int(self.y), int(self.hitbox[2]), int(self.hitbox[3])


def create_player(x, y):
    return Player(x, y)
