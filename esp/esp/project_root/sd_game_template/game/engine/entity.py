class Entity:
    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "width",
        "height",
        "active",
        "visible",
        "swappable",
        "entity_type",
        "hitbox",
        "affected_by_gravity",
        "on_ground",
        "facing",
        "remove_requested",
        "hp",
        "state",
        "last_collision_dirty_rect",
    )

    def __init__(self, x=0, y=0, w=8, h=8, entity_type="entity"):
        self.x = int(x)
        self.y = int(y)
        self.vx = 0
        self.vy = 0
        self.width = int(w)
        self.height = int(h)
        self.active = True
        self.visible = True
        self.swappable = True
        self.entity_type = entity_type
        self.hitbox = [0, 0, self.width, self.height]
        self.affected_by_gravity = True
        self.on_ground = False
        self.facing = 1
        self.remove_requested = False
        self.hp = 1
        self.state = "idle"
        self.last_collision_dirty_rect = None

    def set_pos(self, x, y):
        self.x = int(x)
        self.y = int(y)

    def reset(self, x=None, y=None, active=True):
        if x is not None:
            self.x = int(x)
        if y is not None:
            self.y = int(y)
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.remove_requested = False
        self.active = bool(active)
        self.visible = bool(active)
        self.last_collision_dirty_rect = None

    def update(self, now_ms, stage_data):
        return

    def draw(self, renderer_mod):
        return

    def deactivate(self):
        self.active = False
        self.visible = False
        self.remove_requested = True
        self.last_collision_dirty_rect = None
